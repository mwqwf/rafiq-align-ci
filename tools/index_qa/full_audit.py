#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""الفحصُ الشاملُ لكلّ فهارس التوقيت المنشورة — قارئٌ محضٌ في مسحٍ واحد (أمرُ المالك 2026-10-02).

    python tools/index_qa/full_audit.py                       # كلُّ المنشور (180)
    python tools/index_qa/full_audit.py --only hafs/asim,qalun/akri_qalun
    python tools/index_qa/full_audit.py --phase struct        # البنود 1·2·3·5 بلا أحكام state/
    python tools/index_qa/full_audit.py --phase audio         # البند 4 وحده (أحكامُ الصوت والمطالع)
    python tools/index_qa/full_audit.py --self-test           # بلا شبكة

**البنود التي يقيسها لكلّ فهرسٍ في `timings/<رواية>/<قارئ>.jz`:**
1. **الهويّة:** بصمةُ الدلو = `timings/manifest.json` = العنوانُ العامّ (`r2.dev`) = `timings/frozen.txt` (الدلو) = `tools/index_qa/frozen.txt` (المرآة).
2. **البنية:** 6236 مدخلاً أو نقصٌ معلَنٌ بسببه · لا تكرارَ `ayahId` · `startMs<endMs` · لا تداخلَ بين مدخلين
   متتاليين في الملفّ نفسه · رتابةٌ داخل السورة · ملفٌّ واحدٌ لكلّ سورة ولا ملفٌّ لسورتين · رقمُ الملفّ يطابق
   السورة · بصماتُ الصوت 114 بلا تكرار (`run.structural` نفسُه، لا نسخةٌ موازية).
3. **قاعدةُ البتر (المالك 2026-10-02):** آيةٌ غائبةٌ **بين** حاضرتين في سورةٍ = خطأ؛ ونقصُ الطرف مقبولٌ إن أُعلن بسببه.
4. **الأحكامُ الصوتيّة:** عيّناتُ ملوحٍ على **البصمة المنشورة نفسها** (مجمَّعةً بقاعدة `promote.pooled_samples`)
   بحدٍّ أعلى للعطب الجسيم دون 5٪، وشاهدُ مطالعَ موثوقٌ كاملٌ بلا `swallowed`/`lateConfirmed` وبحقل `late`.
5. **مؤشّراتُ المدد:** آيةٌ مدّتها خارج 0.3×–3× المتوقَّع من حروفها ومعدّلِ القارئ في السورة، وفجوةُ صمتٍ >15ث
   بين آيتين متتاليتين في الملفّ نفسه — **تُسجَّل للمراجعة ولا تُحكم**.

⚖️ **لا يكتب في الدلو بايتاً ولا يمسّ حارساً ولا عتبة**: يقرأ، ويقارن، ويكتب تقريره في `ops/out/` وحدَه.
⛔ **ولا يحمل الفهرسُ طولَ ملفّه الصوتيّ** فلا يُقاس هنا «مدخلٌ يتجاوز طولَ ملفّه»؛ ذاك شأنُ حارس
   `run._eof_pad_ok` في الإحصاء الصوتيّ، ويُذكر في التقرير أنّه **غيرُ مقيسٍ هنا**.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import statistics
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tools" / "alignment"))

import run as _run                                                    # noqa: E402
import promote as _p                                                  # noqa: E402
from common import norm as _norm                                      # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                                 # noqa: BLE001
        pass

COUNTS = _run.COUNTS
DUR_LO, DUR_HI = 0.3, 3.0          # نطاقُ المدّة المقبولة نسبةً إلى المتوقَّع
MIN_CHARS = 8                      # دون هذا لا يُقاس الشذوذ (الحروفُ المقطّعة والآياتُ القصار تُمدّ بطبعها)
GAP_MS = 15_000                    # فجوةُ صمتٍ تُسجَّل
IMPOSSIBLE_MS = 400                # آيةٌ من ≥8 أحرفٍ دون 0.4ث (أو ≤0.1× المتوقَّع): لا تلاوةَ فيها
VERY_SHORT_MS = 1000               # 0.4–1ث: قصيرةٌ جدّاً — مؤشّرٌ لا حكم
IMPOSSIBLE_RATIO = 0.1
EXTREME_RATIO = 5.0                # ≥5× المتوقَّع
LONG_MS = 120_000                  # سقفُ run.structural للمدخل الطويل
OVERLAP_TOL_MS = 50                # سماحُ التداخل نفسُه الذي في `run.structural`
MAX_EXAMPLES = 12
SEVERE_CEILING = _p.SEVERE_CEILING


def _sa(aid: str):
    s, a = aid.split(":")
    return int(s), int(a)


def _file_nos(url: str):
    """رقمٌ صريح في أول الاسم أو بعد «سورة»؛ أرقامُ البصمات والتواريخ ليست أرقامَ سور."""
    from urllib.parse import unquote, urlsplit
    name = unquote(urlsplit(str(url or "")).path.rsplit("/", 1)[-1])
    if not re.search(r"\.(?:mp3|ogg|opus|m4a|wav)$", name, flags=re.I):
        return set()                   # لا اسمَ ملفٍّ صوتيّ (مرجعٌ مبتورٌ إلى مجلّد) — يُكشف في «ملفٌّ لسورتين»
    stem = re.sub(r"\.(?:mp3|ogg|opus|m4a|wav)$", "", name, flags=re.I)
    match = re.match(r"^(?:(?:surah|sura|سورة)[\s_.-]*)?(\d{1,3})(?=$|[\s_.-])",
                     stem, flags=re.I)
    return {int(match.group(1))} if match else set()


def _file_no(url: str):
    """رقمُ السورة من اسم الملفّ، أو None إن لم يُعرف (‏تُستعمل في المقابلة مع رقم السورة)."""
    nos = _file_nos(url)
    return min(nos) if len(nos) == 1 else None


def _registered_file_number(idx: dict, key: str, surah: int) -> bool:
    """يُفسَّر اختلافُ الاسم بالسجل المقيس فقط، وبحارس المصدر القائم دون استثناء قارئ."""
    match = re.fullmatch(r"(timings|timings-staging)/([^/]+)/([^/]+)\.jz", key)
    if not match:
        return False
    prefix, riwaya, reciter = match.groups()
    if prefix == "timings-staging":
        reciter = reciter.rsplit(".", 1)[0]
    if idx.get("riwaya") != riwaya or idx.get("reciterId") != reciter:
        return False
    valid, _evidence = _p.registered_source_remediation(idx, riwaya, reciter, surah)
    return valid


# ───────────────────────── البند 2: البنية ─────────────────────────
def check_structure(idx: dict, key: str, text=None) -> dict:
    E = idx.get("entries") or []
    out = {"entries": len(E), "errors": [], "examples": {}}
    ids = [e.get("ayahId") for e in E]
    dup = sorted({i for i in ids if ids.count(i) > 1}) if len(set(ids)) != len(ids) else []
    if dup:
        out["errors"].append(f"ayahId مكرّر: {len(dup)}")
        out["examples"]["dupIds"] = dup[:MAX_EXAMPLES]
    bad_ids = [i for i in ids if not (isinstance(i, str) and re.fullmatch(r"\d{1,3}:\d{1,3}", i)
                                      and 1 <= _sa(i)[0] <= 114 and 1 <= _sa(i)[1] <= COUNTS[_sa(i)[0] - 1])]
    if bad_ids:
        out["errors"].append(f"ayahId خارج المصحف: {len(bad_ids)}")
        out["examples"]["badIds"] = bad_ids[:MAX_EXAMPLES]
    # مدّةٌ غير صالحة
    inval = [e["ayahId"] for e in E if e.get("startMs") is None or e.get("endMs") is None
             or e["endMs"] <= e["startMs"] or e["startMs"] < 0]
    if inval:
        out["errors"].append(f"startMs/endMs غير صالح: {len(inval)}")
        out["examples"]["invalidDur"] = inval[:MAX_EXAMPLES]
    # الملفّ لكلّ سورة
    per: dict[int, list] = {}
    files_of: dict[int, set] = {}
    surahs_of_file: dict[str, set] = {}
    for e in E:
        if e.get("ayahId") in bad_ids:
            continue
        s, _a = _sa(e["ayahId"])
        per.setdefault(s, []).append(e)
        f = e.get("fileRef")
        files_of.setdefault(s, set()).add(f)
        surahs_of_file.setdefault(f, set()).add(s)
    multi = {s: sorted(map(str, fs)) for s, fs in files_of.items() if len(fs) > 1}
    if multi:
        out["errors"].append(f"سورةٌ بأكثر من ملفّ: {len(multi)}")
        out["examples"]["multiFileSurahs"] = dict(list(multi.items())[:MAX_EXAMPLES])
    shared = {str(f): sorted(ss) for f, ss in surahs_of_file.items() if len(ss) > 1}
    if shared:
        out["errors"].append(f"ملفٌّ واحدٌ لسورتين فأكثر: {len(shared)}")
        out["examples"]["sharedFiles"] = dict(list(shared.items())[:MAX_EXAMPLES])
    nofile = sorted(s for s, fs in files_of.items() if any(not f for f in fs))
    if nofile:
        out["errors"].append(f"مداخل بلا fileRef في {len(nofile)} سورة")
        out["examples"]["noFileRef"] = nofile[:MAX_EXAMPLES]
    # ⛔ مرجعٌ إلى مجلّدٍ بلا اسمِ ملفٍّ صوتيّ: التطبيقُ يطلب `fileRef` حرفاً (‏`remoteUrl = e.fileRef`
    #    في QuranViewModel/SurahPlayer) فلا يجد صوتاً — عطبُ تشغيلٍ لا نقصُ توقيت.
    noname = sorted(s for s, fs in files_of.items()
                    if any(f and not _run.AUDIO_EXT_RE.search(str(f)) for f in fs))
    if noname:
        out["errors"].append(f"fileRef بلا اسم ملفٍّ صوتيّ (مجلّدٌ لا ملفّ) في {len(noname)} سورة")
        out["examples"]["folderFileRef"] = {str(s): sorted(map(str, files_of[s]))[0] for s in noname[:MAX_EXAMPLES]}
    mism, registered = {}, {}
    for s, fs in files_of.items():
        for f in fs:
            nos = _file_nos(f)
            if nos and s not in nos:
                if _registered_file_number(idx, key, s):
                    registered[str(s)] = f
                else:
                    mism[s] = f
    if mism:
        out["errors"].append(f"رقمُ الملفّ لا يطابق السورة: {len(mism)}")
        out["examples"]["fileNoMismatch"] = {str(s): mism[s] for s in sorted(mism)[:MAX_EXAMPLES]}
    out["registeredFileNoMappings"] = registered
    unnum = sorted({s for s, fs in files_of.items() if any(f and not _file_nos(f) for f in fs)})
    out["fileNoUnparsed"] = len(unnum)
    # الرتابةُ داخل السورة والتداخلُ داخل الملفّ
    mono, overlap = [], []
    for s, lst in per.items():
        lst = sorted(lst, key=lambda e: _sa(e["ayahId"])[1])
        prev = None
        for e in lst:
            st, en = e.get("startMs"), e.get("endMs")
            if st is None or en is None:
                continue
            if prev is not None and st < prev[1] - OVERLAP_TOL_MS:
                mono.append(f"{e['ayahId']} يبدأ قبل نهاية {prev[0]} بـ{prev[1] - st}م.ث")
            prev = (e["ayahId"], en)
    for f, _ss in surahs_of_file.items():
        lst = sorted((e for e in E if e.get("fileRef") == f and e.get("startMs") is not None
                      and e.get("endMs") is not None), key=lambda e: (e["startMs"], e["endMs"]))
        for a, b in zip(lst, lst[1:]):
            if b["startMs"] < a["endMs"] - OVERLAP_TOL_MS:
                overlap.append(f"{a['ayahId']}→{b['ayahId']} تداخل {a['endMs'] - b['startMs']}م.ث")
    if mono:
        out["errors"].append(f"خرقُ الرتابة داخل السورة: {len(mono)}")
        out["examples"]["monotonic"] = mono[:MAX_EXAMPLES]
    if overlap:
        out["errors"].append(f"تداخلٌ بين مدخلين في الملفّ نفسه: {len(overlap)}")
        out["examples"]["overlap"] = overlap[:MAX_EXAMPLES]
    # فحصُ run.structural نفسُه (البصماتُ 114 وتكرارُها والإسقاطُ المعلَن والعتبات)
    try:
        fatal, warn, info = _run.structural(idx, key, allow_unmarked=True, txt_ref=text)
    except Exception as ex:                                           # noqa: BLE001
        fatal, warn, info = [f"تعذّر run.structural: {ex}"], [], {}
    out["structuralFatal"] = list(fatal)
    out["structuralWarn"] = list(warn)
    out["decision"] = list(info.get("decision") or [])
    out["engine"] = idx.get("engineVersion")
    out["audioSha"] = info.get("sha")
    out["bands"] = info.get("bands")
    sha = idx.get("audioSha256") or []
    served = set(per)
    exempt = {s for s in _run.declared_drops(idx) if s not in served}
    live = [(i + 1, x) for i, x in enumerate(sha) if (i + 1) not in exempt and x]
    seen: dict[str, list] = {}
    for s, d in live:
        seen.setdefault(d, []).append(s)
    dups = {d[:16]: ss for d, ss in seen.items() if len(ss) > 1}
    if dups:
        out["errors"].append(f"بصمةُ صوتٍ واحدةٌ لعدّة سور: {len(dups)}")
        out["examples"]["dupAudioSha"] = dups
    out["ok"] = not out["errors"] and not any(
        f for f in fatal if not f.startswith("لا أثر صقل"))
    return out


# ───────────────────────── البند 3: قاعدةُ البتر ─────────────────────────
def _declared(idx: dict) -> dict:
    tr = idx.get("transform") or {}
    mh = idx.get("missing") or {}
    by_reason = mh.get("byReason") if isinstance(mh.get("byReason"), dict) else {}
    ids = mh.get("ids") if isinstance(mh.get("ids"), list) else None
    return {"transformOp": tr.get("op"), "transformReason": tr.get("reason"),
            "reasonCode": tr.get("reasonCode"), "dropSurahs": _run.declared_drops(idx),
            "byReason": by_reason, "declaredCount": sum(int(v or 0) for v in by_reason.values()),
            "tagCount": mh.get("count"), "declaredIds": ids,
            "truncatedTail": tr.get("truncatedTail") or tr.get("ownerTruncatedTail")}


def check_gaps(idx: dict) -> dict:
    E = idx.get("entries") or []
    have: dict[int, set] = {}
    for e in E:
        try:
            s, a = _sa(e["ayahId"])
        except Exception:                                             # noqa: BLE001
            continue
        have.setdefault(s, set()).add(a)
    internal, head, tail, whole = [], [], [], []
    for s in range(1, 115):
        n = COUNTS[s - 1]
        hs = have.get(s, set())
        if not hs:
            whole.append(s)
            continue
        lo, hi = min(hs), max(hs)
        inner = [a for a in range(lo, hi + 1) if a not in hs]
        if inner:
            internal.append({"surah": s, "missing": inner[:40], "count": len(inner)})
        if lo > 1:
            head.append({"surah": s, "range": [1, lo - 1]})
        if hi < n:
            tail.append({"surah": s, "range": [hi + 1, n]})
    dec = _declared(idx)
    missing_total = 6236 - len({e.get("ayahId") for e in E})
    declared_ids = set(dec["declaredIds"] or [])
    undeclared_edge = []
    for r in head + tail:
        s = r["surah"]
        ids = {f"{s}:{a}" for a in range(r["range"][0], r["range"][1] + 1)}
        if s in dec["dropSurahs"]:
            continue
        if declared_ids and ids <= declared_ids:
            continue
        if not declared_ids and dec["declaredCount"] >= missing_total > 0:
            continue                     # إعلانٌ بالعدّ لا بالأرقام — يُقبل إذا غطّى النقصَ كلَّه
        undeclared_edge.append(r)
    undeclared_whole = [s for s in whole if s not in dec["dropSurahs"]
                        and not (declared_ids and {f"{s}:{a}" for a in range(1, COUNTS[s - 1] + 1)} <= declared_ids)]
    errors = []
    if internal:
        errors.append(f"فجوةٌ وسطيّة (آيةٌ غائبةٌ بين حاضرتين) في {len(internal)} سورة")
    if undeclared_edge:
        errors.append(f"نقصُ طرفٍ غيرُ معلَن في {len(undeclared_edge)} سورة")
    if undeclared_whole:
        errors.append(f"سورٌ غائبةٌ كليّاً بلا إعلان: {undeclared_whole}")
    if missing_total and dec["declaredCount"] and dec["declaredCount"] != missing_total and not declared_ids:
        errors.append(f"الإعلانُ {dec['declaredCount']} والغيابُ المحسوب {missing_total}")
    return {"missingTotal": missing_total, "internalGaps": internal, "headMissing": head,
            "tailMissing": tail, "wholeMissing": whole, "declared": dec,
            "undeclaredEdge": undeclared_edge, "errors": errors, "ok": not errors}


# ───────────────────────── البند 5: مؤشّراتُ المدد ─────────────────────────
def check_durations(idx: dict, text) -> dict:
    E = idx.get("entries") or []
    per: dict[int, list] = {}
    for e in E:
        try:
            s, a = _sa(e["ayahId"])
        except Exception:                                             # noqa: BLE001
            continue
        if e.get("startMs") is None or e.get("endMs") is None or e["endMs"] <= e["startMs"]:
            continue
        per.setdefault(s, []).append((a, e))
    outliers, gaps, rates = [], [], {}
    for s, lst in per.items():
        lst.sort(key=lambda x: x[0])
        chars = {}
        if text:
            for a, _e in lst:
                t = text[_run.flat(s, a)] if _run.flat(s, a) < len(text) else ""
                chars[a] = len(_norm(t).replace(" ", ""))
            rs = [(e["endMs"] - e["startMs"]) / chars[a] for a, e in lst if chars.get(a, 0) >= MIN_CHARS]
            rate = statistics.median(rs) if len(rs) >= 3 else None
            rates[s] = rate
            if rate:
                for a, e in lst:
                    c = chars.get(a, 0)
                    if c < MIN_CHARS:
                        continue
                    exp = c * rate
                    d = e["endMs"] - e["startMs"]
                    r = d / exp
                    if r < DUR_LO or r > DUR_HI:
                        outliers.append({"aid": f"{s}:{a}", "ms": d, "expMs": round(exp),
                                         "ratio": round(r, 2), "chars": c})
        for (a1, e1), (a2, e2) in zip(lst, lst[1:]):
            if a2 != a1 + 1 or e1.get("fileRef") != e2.get("fileRef"):
                continue
            g = e2["startMs"] - e1["endMs"]
            if g > GAP_MS:
                gaps.append({"from": f"{s}:{a1}", "to": f"{s}:{a2}", "gapMs": g})
    outliers.sort(key=lambda o: -abs(o["ratio"] - 1))
    gaps.sort(key=lambda g: -g["gapMs"])
    # ⛔ **مستحيلٌ بالبيانات وحدها** (لا يحتاج سمعاً): آيةٌ ≥ MIN_CHARS حرفاً مدّتُها دون ثانية — لا تلاوةَ فيها.
    impossible = [o for o in outliers if o["ms"] < IMPOSSIBLE_MS or o["ratio"] <= IMPOSSIBLE_RATIO]
    very_short = [o for o in outliers if o not in impossible and o["ms"] < VERY_SHORT_MS]
    # ⚠️ مفرطُ الطول: ≥5× المتوقَّع أو >120ث — يُسرد كاملاً للمراجعة (قد يكون ذيلَ ملفٍّ أو ابتلاعَ جاراتٍ أو مادّةً زائدة).
    extreme = [o for o in outliers if o["ratio"] >= EXTREME_RATIO or o["ms"] > LONG_MS]
    return {"durationOutliers": len(outliers), "durationExamples": outliers[:MAX_EXAMPLES],
            "impossibleShort": impossible, "veryShort": very_short, "extremeLong": extreme,
            "longOutliers": sum(1 for o in outliers if o["ratio"] > DUR_HI),
            "shortOutliers": sum(1 for o in outliers if o["ratio"] < DUR_LO),
            "silenceGaps": len(gaps), "silenceExamples": gaps[:MAX_EXAMPLES],
            "surahsWithRate": sum(1 for r in rates.values() if r)}


# ───────────────────────── البند 4: الأحكامُ الصوتيّة ─────────────────────────
def audio_status(sha: str, stem: str, reports: list) -> dict:
    """‏reports: قائمةُ (اسم، حكم) كما يُرجعها `promote.bucket_reports`."""
    on_sha = [r for _n, r in reports if r.get("sha256") == sha]
    samples = [r for r in on_sha if _p.has_audio_sample(r) and r.get("band") is None]
    openers = _p.openers_map([(n, r) for n, r in reports if r.get("sha256") == sha]).get(sha)
    out = {"audioReportsOnSha": len(samples), "openersOnSha": openers is not None, "errors": [], "notes": []}
    verdicts = []
    for r in sorted(samples, key=_p._when):
        rate, lo, hi = _p.severe_ci(r)
        sv = (r.get("sample") or {}).get("severe") or [None, None]
        verdicts.append({"salt": (r.get("sample") or {}).get("seedSalt"), "source": r.get("source"),
                         "engine": r.get("engine"), "verdict": r.get("verdict"),
                         "m": sv[0], "n": sv[1], "rate": rate, "hi": hi,
                         "fatal": len(r.get("fatal") or []), "ts": r.get("ts")})
    out["samples"] = verdicts
    pooled = _p.pooled_samples(samples) if len(samples) >= 2 else None
    out["pooled"] = ({k: pooled[k] for k in ("m", "n", "rate", "hi", "salts", "seeds", "engine", "rule")}
                     if pooled else None)
    accepted = [v for v in verdicts if v["verdict"] == _p.ACCEPTED and v["hi"] is not None]
    if pooled:
        out["severeHi"] = pooled["hi"]
    elif accepted:
        out["severeHi"] = min(v["hi"] for v in accepted)
    else:
        out["severeHi"] = None
    rejected = [v for v in verdicts if str(v["verdict"] or "").startswith("مرفوض")]
    fatals = [v for v in verdicts if v["fatal"]]
    if not samples:
        out["errors"].append("لا حكمَ صوتيٍّ بعيّنةٍ على البصمة المنشورة")
    else:
        if out["severeHi"] is None:
            out["errors"].append("لا حدَّ أعلى مقبولاً (لا تجميعَ ولا حكمَ مقبولاً)")
        elif out["severeHi"] >= SEVERE_CEILING:
            out["errors"].append(f"الحدُّ الأعلى للعطب الجسيم {out['severeHi']:.2%} ≥ 5%")
        if rejected and not pooled:
            out["errors"].append(f"حكمٌ مرفوضٌ على البصمة بلا تجميعٍ يفصله: {len(rejected)}")
        elif rejected:
            out["notes"].append(f"حكمٌ مرفوضٌ منفردٌ فُصل بالتجميع ({pooled['rule']}): {len(rejected)}")
        if fatals:
            out["notes"].append(f"أحكامٌ تحمل فواتل: {len(fatals)} (تُقرأ: أثرُ إسقاطٍ معلَن أم عطب؟)")
    if openers is None:
        out["errors"].append("لا شاهدَ مطالعَ على البصمة المنشورة")
    else:
        blob = openers.get("openers") if isinstance(openers.get("openers"), dict) else {}
        hard = list(blob.get("defects") or []) + list(openers.get("swallowed") or []) \
            + list(openers.get("lateConfirmed") or [])
        out["openers"] = {"commit": openers.get("commit"), "toolOk": _p.openers_tool_ok(openers),
                          "scope": openers.get("scope"), "checked": openers.get("checked"),
                          "hasLate": "late" in openers, "late": list(openers.get("late") or []),
                          "lateCtcRule": openers.get("lateCtcRule"),
                          "lateConfirmed": list(openers.get("lateConfirmed") or []),
                          "swallowed": list(openers.get("swallowed") or []),
                          "suspect": list(openers.get("suspect") or []),
                          "tail": list(openers.get("tail") or []),
                          "unknown": list(openers.get("unknown") or []),
                          "verdict": openers.get("openersVerdict") or openers.get("verdict")}
        if not out["openers"]["toolOk"]:
            out["errors"].append("شاهدُ المطالع من أداةٍ غير موثوقة (قبل إصلاح التبرئة الكاذبة)")
        if str(openers.get("scope") or "").lower() != "full":
            out["errors"].append(f"شاهدُ المطالع جزئيّ (scope={openers.get('scope')!r})")
        if "late" not in openers:
            out["errors"].append("شاهدُ المطالع بلا حقل late (قبل حارس التأخّر)")
        elif openers.get("late") and not openers.get("lateCtcRule"):
            out["errors"].append(f"مطالعُ متأخّرة {list(openers['late'])} بلا شاهد CTC الثاني")
        if hard:
            out["errors"].append(f"مطلعٌ مبتلعٌ/متأخّرٌ مؤكَّد: {hard[:6]}")
        if openers.get("suspect"):
            out["notes"].append(f"مطالعُ مشكوكٌ فيها بلا تحقّق (suspect): {list(openers['suspect'])[:8]}")
    # أحكامٌ على بصماتٍ أخرى للمفتاح نفسه — تُذكر إن كانت البصمةُ الحاليّة بلا حكم
    others = sorted({(r.get("sha256") or "")[:8] for _n, r in reports
                     if r.get("sha256") and r.get("sha256") != sha and _p.has_audio_sample(r)
                     and stem in str(r.get("key") or "")})
    out["otherShasWithSamples"] = others[:10]
    out["ok"] = not out["errors"]
    return out


# ───────────────────────── الهويّة (البند 1) ─────────────────────────
def _public_sha(key: str) -> str | None:
    req = urllib.request.Request(_p.PUBLIC.rstrip("/") + "/" + key,
                                 headers={"User-Agent": "rafiq-full-audit/1"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return hashlib.sha256(r.read()).hexdigest()
        except Exception:                                             # noqa: BLE001
            time.sleep(2 * (attempt + 1))
    return None


def check_identity(key: str, sha: str, n_entries: int, manifest: dict, frozen_bucket: dict,
                   frozen_repo: dict, public_sha, check_public: bool = True) -> dict:
    row = manifest.get(key)
    out = {"sha256": sha, "manifestSha": (row or {}).get("sha256"), "manifestEntries": (row or {}).get("entries"),
           "publicSha": public_sha, "frozenBucketSha": frozen_bucket.get(key), "frozenRepoSha": frozen_repo.get(key),
           "errors": []}
    if row is None:
        out["errors"].append("غائبٌ من manifest")
    else:
        if row.get("sha256") != sha:
            out["errors"].append("بصمةُ manifest ≠ الدلو")
        if row.get("entries") != n_entries:
            out["errors"].append(f"مداخلُ manifest {row.get('entries')} ≠ {n_entries}")
    if not check_public:
        pass
    elif public_sha is None:
        out["errors"].append("تعذّرت قراءةُ العنوان العامّ")
    elif public_sha != sha:
        out["errors"].append("بصمةُ العنوان العامّ ≠ الدلو")
    if frozen_bucket.get(key) != sha:
        out["errors"].append("غيرُ مجمَّدٍ على بصمته في الدلو" if key not in frozen_bucket else "تجميدُ الدلو على بصمةٍ أخرى")
    # ⚖️ قائمةُ الدلو هي الحقيقة (D-075)؛ ومرآةُ المستودع تُقاس وتُذكر تحذيراً لا خطأً في الفهرس.
    out["mirrorStale"] = frozen_repo.get(key) != sha
    out["ok"] = not out["errors"]
    return out


# ───────────────────────── التجميع والتقرير ─────────────────────────
def _texts():
    out = {}
    for riw in ("hafs", "warsh", "qalun", "douri", "shuba", "sousi"):
        p = _run.ASSETS / f"text_{riw}.jz"
        if p.exists():
            try:
                t = json.loads(gzip.decompress(p.read_bytes()).decode("utf-8"))
                if len(t) == 6236:
                    out[riw] = t
            except Exception:                                         # noqa: BLE001
                pass
    return out


def summarize(rows: list, phase: str) -> dict:
    n = len(rows)
    s = {"indexes": n, "phase": phase}
    for item in ("identity", "structure", "gaps", "audio"):
        s[item + "Ok"] = sum(1 for r in rows if (r.get(item) or {}).get("ok"))
        s[item + "Bad"] = [r["key"] for r in rows if r.get(item) and not r[item].get("ok")]
    s["durationOutliersTotal"] = sum((r.get("durations") or {}).get("durationOutliers", 0) for r in rows)
    s["impossibleShortTotal"] = sum(len((r.get("durations") or {}).get("impossibleShort") or []) for r in rows)
    s["indexesWithImpossibleShort"] = sum(1 for r in rows if (r.get("durations") or {}).get("impossibleShort"))
    s["veryShortTotal"] = sum(len((r.get("durations") or {}).get("veryShort") or []) for r in rows)
    s["extremeLongTotal"] = sum(len((r.get("durations") or {}).get("extremeLong") or []) for r in rows)
    s["indexesWithExtremeLong"] = sum(1 for r in rows if (r.get("durations") or {}).get("extremeLong"))
    s["mirrorStale"] = sum(1 for r in rows if (r.get("identity") or {}).get("mirrorStale"))
    s["silenceGapsTotal"] = sum((r.get("durations") or {}).get("silenceGaps", 0) for r in rows)
    s["indexesWithDurationOutliers"] = sum(1 for r in rows if (r.get("durations") or {}).get("durationOutliers"))
    s["indexesWithSilenceGaps"] = sum(1 for r in rows if (r.get("durations") or {}).get("silenceGaps"))
    s["entriesTotal"] = sum((r.get("structure") or {}).get("entries", 0) for r in rows)
    s["missingTotal"] = sum((r.get("gaps") or {}).get("missingTotal", 0) for r in rows)
    return s


def to_markdown(report: dict) -> str:
    s = report["summary"]
    L = [f"# الفحصُ الشاملُ لفهارس التوقيت المنشورة — {report['date']}", "",
         f"- الزمن: {report['timestampUtc']} · المرحلة: `{s['phase']}` · الفهارس: **{s['indexes']}** · "
         f"المداخل: {s['entriesTotal']} · الغياب: {s['missingTotal']}",
         "", "## الحصيلة بالبنود", "", "| البند | سليم | فيه خطأ |", "|---|---|---|"]
    names = {"identity": "1 الهويّة (دلو=manifest=عامّ=تجميد)", "structure": "2 البنية",
             "gaps": "3 قاعدة البتر (لا فجوة وسطيّة · الطرف معلَن)", "audio": "4 الأحكام الصوتيّة على البصمة المنشورة"}
    for k, nm in names.items():
        if f"{k}Ok" in s and (s[f"{k}Ok"] or s[f"{k}Bad"]):
            L.append(f"| {nm} | {s[f'{k}Ok']} | {len(s[f'{k}Bad'])} |")
    L += [f"| 5 مؤشّرات المدد (لا حكم) | فهارس بشذوذ مدّة: {s['indexesWithDurationOutliers']} "
          f"(آيات {s['durationOutliersTotal']}) | فهارس بفجوة صمت >15ث: {s['indexesWithSilenceGaps']} "
          f"(مواضع {s['silenceGapsTotal']}) |", ""]
    L += [f"- مرآةُ `tools/index_qa/frozen.txt` في المستودع متقادمةٌ عن قائمة الدلو في {s.get('mirrorStale', 0)} فهرساً "
          "(قائمةُ الدلو هي الحقيقة — D-075؛ تحذيرٌ لا خطأُ فهرس).", ""]
    L += [f"## آياتٌ مستحيلةُ المدّة (≥8 أحرف ودون 0.4ث أو ≤0.1× المتوقَّع) — خطأٌ بالبيانات وحدها "
          f"({s.get('impossibleShortTotal', 0)} آية · وقصيرةٌ جدّاً 0.4–1ث للمراجعة: {s.get('veryShortTotal', 0)})", ""]
    n_imp = 0
    for r in report["rows"]:
        imp = (r.get("durations") or {}).get("impossibleShort") or []
        if imp:
            n_imp += len(imp)
            L.append(f"- {r['key']}: " + "، ".join(f"{o['aid']} ({o['ms']}م.ث من ~{o['expMs'] / 1000:.0f}ث)" for o in imp))
    if not n_imp:
        L.append("- لا شيء.")
    L += ["", "## مداخلُ مفرطةُ الطول (≥5× المتوقَّع أو >120ث) — للمراجعة الصوتيّة", ""]
    for r in report["rows"]:
        ex = (r.get("durations") or {}).get("extremeLong") or []
        ex = [o for o in ex if o["ratio"] >= 2.5]
        if ex:
            L.append(f"- {r['key']}: " + "، ".join(f"{o['aid']} {o['ms'] / 1000:.0f}ث (×{o['ratio']})" for o in ex[:15])
                     + (f" … و{len(ex) - 15} غيرها" if len(ex) > 15 else ""))
    L += ["", "## الأخطاء المؤكَّدة (بند 1–4)", ""]
    any_err = False
    for r in report["rows"]:
        errs = []
        for item in ("identity", "structure", "gaps", "audio"):
            d = r.get(item) or {}
            if d and not d.get("ok"):
                errs += [f"[{item}] {e}" for e in d.get("errors") or []]
                errs += [f"[{item}/structural] {e}" for e in d.get("structuralFatal") or []
                         if not str(e).startswith("لا أثر صقل")]
        if errs:
            any_err = True
            L.append(f"- **{r['key']}** `{r['sha256'][:8]}`: " + " · ".join(errs))
            g = r.get("gaps") or {}
            for ig in g.get("internalGaps") or []:
                L.append(f"    - سورة {ig['surah']}: غائبة {ig['missing'][:20]}{' …' if ig['count'] > 20 else ''}")
            for ue in g.get("undeclaredEdge") or []:
                L.append(f"    - سورة {ue['surah']}: طرفٌ غيرُ معلَن {ue['range']}")
    if not any_err:
        L.append("- لا خطأَ مؤكَّداً في البنود المقيسة.")
    L += ["", "## المؤشّرات المشكوك فيها (بند 5 — للمراجعة لا للحكم)", ""]
    rows5 = sorted(report["rows"], key=lambda r: -((r.get("durations") or {}).get("durationOutliers", 0)
                                                    + (r.get("durations") or {}).get("silenceGaps", 0)))
    for r in rows5:
        d = r.get("durations") or {}
        if not d.get("durationOutliers") and not d.get("silenceGaps"):
            continue
        ex = "، ".join(f"{o['aid']} {o['ms'] / 1000:.1f}ث (×{o['ratio']})" for o in d.get("durationExamples", [])[:4])
        gx = "، ".join(f"{g['from']}→{g['to']} {g['gapMs'] / 1000:.0f}ث" for g in d.get("silenceExamples", [])[:3])
        L.append(f"- {r['key']}: شذوذُ مدّة {d['durationOutliers']} (طويل {d['longOutliers']} · قصير {d['shortOutliers']})"
                 + (f" — مثل {ex}" if ex else "") + f" · فجواتُ صمت {d['silenceGaps']}" + (f" — {gx}" if gx else ""))
    notes = []
    for r in report["rows"]:
        a = r.get("audio") or {}
        for nt in a.get("notes") or []:
            notes.append(f"- {r['key']}: {nt}")
        g = r.get("gaps") or {}
        if g.get("missingTotal"):
            notes.append(f"- {r['key']}: غيابٌ {g['missingTotal']} — معلَن {g['declared'].get('declaredCount')} "
                         f"({g['declared'].get('byReason') or g['declared'].get('transformOp')})")
    if notes:
        L += ["", "## ملاحظاتٌ لا تمنع", ""] + notes
    L += ["", "## ما لم يُقَس هنا", "",
          "- «مدخلٌ يتجاوز طولَ ملفّه الصوتيّ»: الفهرسُ لا يحمل طولَ الملفّ؛ يُقاس في الإحصاء الصوتيّ (`run._eof_pad_ok`) لا هنا.",
          "- صحّةُ التوقيت سمعاً: الأحكامُ الصوتيّة عيّناتُ ملوحٍ ومطالعُ (بند 4)، لا سماعٌ لكلّ آية."]
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="الفحصُ الشاملُ للفهارس المنشورة — قارئٌ محض")
    ap.add_argument("--only", default=None, help="مفاتيحُ بفاصلة مثل hafs/asim,qalun/akri_qalun")
    ap.add_argument("--phase", choices=["all", "struct", "audio"], default="all")
    ap.add_argument("--no-public", action="store_true", help="بلا قراءة العنوان العامّ")
    ap.add_argument("--date", default=time.strftime("%Y%m%d", time.gmtime()))
    ap.add_argument("--out", default=None, help="ملفُّ JSON في ops/out (الافتراض full-audit-<date>.json)")
    ap.add_argument("--md", default=None)
    ap.add_argument("--budget-sec", type=int, default=1500, help="سقفٌ زمنيٌّ يُكتب عنده ما تمّ")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        import subprocess
        return subprocess.call([sys.executable, "-m", "unittest", "-v", "tools/index_qa/test_full_audit.py"], cwd=str(ROOT))
    out_json = ROOT / (a.out or f"ops/out/full-audit-{a.date}.json")
    out_md = ROOT / (a.md or f"ops/out/full-audit-{a.date}.md")
    if out_json.parent != ROOT / "ops" / "out":
        ap.error("المخرَج يجب أن يكون في ops/out")
    t0 = time.time()
    cl, bucket = _run.s3()
    keys = []
    for pg in cl.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix="timings/"):
        for o in pg.get("Contents", []):
            k = o["Key"]
            if k.endswith(".jz") and k.count("/") == 2:
                keys.append(k)
    keys.sort()
    if a.only:
        want = {x.strip() for x in a.only.split(",") if x.strip()}
        keys = [k for k in keys if k[len("timings/"):-3] in want or k in want]
        # ⭐ (2026-10-02 · fixS2) مرشّحٌ في المسرح يُسمّى بمفتاحه الكامل فيُفحص بالبنود 2 و3 و5 نفسِها
        #    قبل ترقيته (لا هويّةَ له في manifest بعدُ فتُتخطّى بإعلان) — ويُكتب بـ--out مستقلّ لا فوق تقرير اليوم.
        keys += sorted(k for k in want if k.startswith("timings-staging/") and k.endswith(".jz") and k not in keys)
        # ⭐ 2026-10-02: مرشّحٌ في المسرح يُسمّى بمفتاحه الكامل `timings-staging/<riw>/<id>.<sha8>.jz`
        #    فتُفحص بنيتُه ومددُه وأحكامُه قبل الترقية (‏الهويّةُ لا تُقاس له: ليس في manifest ولا التجميد).
        keys += sorted(x for x in want if x.startswith("timings-staging/") and x.endswith(".jz") and x.count("/") == 2
                       and x not in keys)   # قد تكون في القائمة أصلاً (بادئةُ timings/ تشمل timings-staging/)
    print(f"فهارسُ منشورة: {len(keys)} · المرحلة {a.phase}")
    manifest = {}
    try:
        for row in json.loads(cl.get_object(Bucket=bucket, Key="timings/manifest.json")["Body"].read())["indexes"]:
            manifest[f"timings/{row['riwaya']}/{row['reciterId']}.jz"] = row
    except Exception as ex:                                           # noqa: BLE001
        print(f"⚠️ تعذّرت قراءة manifest: {ex}")
    frozen_bucket, _t, _e = _p.load_frozen(cl, bucket)
    frozen_repo = _p.frozen_keys()
    texts = _texts()

    def _fetch(k):
        for attempt in range(3):
            try:
                raw = cl.get_object(Bucket=bucket, Key=k)["Body"].read()
                return k, raw, None
            except Exception as ex:                                   # noqa: BLE001
                err = ex
                time.sleep(1.5 * (attempt + 1))
        return k, None, str(err)

    with ThreadPoolExecutor(max_workers=8) as pool:
        fetched = dict((k, (raw, err)) for k, raw, err in pool.map(_fetch, keys))
        pub = {}
        if not a.no_public and a.phase != "audio":
            pub_keys = [k for k in keys if not k.startswith("timings-staging/")]
            pub = dict(zip(pub_keys, pool.map(_public_sha, pub_keys)))
    reports = []
    if a.phase in ("all", "audio"):
        reports = _p.bucket_reports(cl, bucket)
        print(f"أحكامُ state/ المقروءة: {len(reports)}")
    rows = []
    for k in keys:
        raw, err = fetched[k]
        if raw is None:
            rows.append({"key": k, "sha256": "", "fetchError": err})
            continue
        sha = hashlib.sha256(raw).hexdigest()
        idx = json.loads(gzip.decompress(raw).decode("utf-8"))
        riw = k.split("/")[1]
        stem = k.split("/")[2][:-3]
        staging = k.startswith("timings-staging/")
        if staging:
            stem = stem.rsplit(".", 1)[0]
        row = {"key": k, "sha256": sha, "riwaya": riw, "reciterId": stem, "bytes": len(raw),
               "engine": idx.get("engineVersion"), "transformOp": (idx.get("transform") or {}).get("op")}
        if staging:
            row["staging"] = True
        if a.phase in ("all", "struct"):
            row["identity"] = ({"sha256": sha, "staging": True, "errors": [], "ok": True} if staging else
                               check_identity(k, sha, len(idx.get("entries") or []), manifest,
                                              frozen_bucket, frozen_repo, pub.get(k), check_public=bool(pub)))
            row["structure"] = check_structure(idx, k, texts.get(riw))
            row["gaps"] = check_gaps(idx)
            row["durations"] = check_durations(idx, texts.get(riw))
        if a.phase in ("all", "audio"):
            row["audio"] = audio_status(sha, stem, reports)
        rows.append(row)
        if time.time() - t0 > a.budget_sec:
            print(f"⏱ بلغ السقفَ الزمنيَّ عند {len(rows)}/{len(keys)} — يُكتب ما تمّ")
            break
    report = {"schema": 1, "tool": "full_audit-1.0", "date": a.date,
              "timestampUtc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "elapsedSec": round(time.time() - t0, 1), "phase": a.phase,
              "manifestIndexes": len(manifest), "frozenBucket": len(frozen_bucket),
              "reportsRead": len(reports), "rows": rows}
    report["summary"] = summarize(rows, a.phase)
    if a.phase == "audio" and out_json.exists():
        # دمجُ البند 4 في تقريرٍ بنيويٍّ سابقٍ لليوم نفسه (بالبصمة نفسِها فقط)
        try:
            prev = json.loads(out_json.read_text(encoding="utf-8"))
            by = {r["key"]: r for r in prev.get("rows", [])}
            for r in rows:
                p = by.get(r["key"])
                if p and p.get("sha256") == r["sha256"]:
                    p["audio"] = r["audio"]
                else:
                    by[r["key"]] = r
            prev["rows"] = [by[k] for k in sorted(by)]
            prev["summary"] = summarize(prev["rows"], "all")
            prev["audioTimestampUtc"] = report["timestampUtc"]
            prev["reportsRead"] = len(reports)
            report = prev
        except Exception as ex:                                       # noqa: BLE001
            print(f"⚠️ تعذّر الدمجُ مع التقرير السابق: {ex}")
    elif a.phase == "struct" and out_json.exists():
        try:
            prev = json.loads(out_json.read_text(encoding="utf-8"))
            by = {r["key"]: r for r in prev.get("rows", [])}
            for r in rows:
                p = by.get(r["key"])
                if p and p.get("sha256") == r["sha256"] and p.get("audio"):
                    r["audio"] = p["audio"]
            report["summary"] = summarize(rows, "all" if any(r.get("audio") for r in rows) else a.phase)
        except Exception:                                             # noqa: BLE001
            pass
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    md = to_markdown(report)
    out_md.write_text(md, encoding="utf-8")
    print(md[:60000])
    print(f"\n⇒ كُتب {out_json.relative_to(ROOT)} و{out_md.relative_to(ROOT)} · {report['elapsedSec']}ث")
    return 0


if __name__ == "__main__":
    sys.exit(main())
