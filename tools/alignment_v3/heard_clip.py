#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""قصُّ نافذة كلّ آيةٍ على **أداءٍ مسموعٍ واحدٍ تامّ** — لقارئٍ يكرّر الآيات (‏maroush_qalun · قرار القائد 2026-11-09).

⭐ **السبب (مقيس):** مخرَجُ `ctc_heard_map` لقارئٍ يعيد الآيات تُبنى نوافذُه من مِرساةٍ إلى مِرساة، فتضمّ التكرارَ
وكلامَ التعليم؛ فرُدّت كلُّ سور maroush في `entry_window_census` بـ«زيادة · عددُ كلمات النافذة 203 فوق الحدّ 62» ونحوه
(‏47 سورةً من 47)، وجاءت المحاذاةُ الكاملةُ بـCTC (‏mode=full) أسوأَ فضغطت السورةَ في جزءٍ من الصوت.

## القاعدة (‏كما قرّر القائد)
1. **أداءٌ تامٌّ** = موضعٌ في خريطة السماع بتشابه ≥ `MIN_SIM` يبدأ ببداية الآية وينتهي بنهايتها،
   **ويثبته شاهدُ Whisper float32 في موضعه نفسِه**: أوّلُ ثلاث كلماتٍ وآخرُ ثلاثٍ تطابقان نصَّ الرواية كلمةً بكلمة،
   وعددُ الكلمات بين الطرفين ضمن 0.7–1.3 من كلمات الآية، وثقةُ الكلمات الطرفيّة ≥0.5 ومتوسّطُها ≥0.7،
   وبدءُ أوّل كلمةٍ ونهايةُ آخرِ كلمةٍ عند Whisper يوافقان حدَّي الأداء المسموع **بفرقٍ ≤ 300م.ث**.
2. إن تعدّد الأداءُ التامّ فالمأخوذُ **آخرُه** (‏fixV)، بشرط أن يتّسق مع جارتيه: نهايتُه ≤ بدء تاليتها،
   والفجوةُ إلى بدء تاليتها ≤ `MAX_GAP_MS` (‏حارسٌ إضافيّ: لا تُقبل آيةٌ على بُعد دقائق من جارتها).
3. **ما لم يثبت له أداءٌ تامٌّ واحد لا يُقصّ تخميناً**: تُرجع الأداةُ سورتَه «غيرَ محلولة» بسببٍ مكتوب،
   فتبقى السورةُ محجوبةً معلَنةً كما هي في الأب (‏`splice_surah --skip-unresolved`) ولا تُرقّى.
4. **الدليلُ يُسجَّل لكلّ آية**: أيُّ أداءٍ اختير (‏k من n) وحدّاه وتشابهُه وبدءُ Whisper ونهايتُه وثقتُه،
   في `heardClip` بترويسة السورة، وتُنقل إلى ترويسة الفهرس (‏`inject_header`).

⛔ لا حارسَ يُخفَّف ولا عتبةَ تُخفَّض: القصُّ يُنتج مرشّحاً يمرّ بعدها بالبنية وبوّابة السماع
وإحصاء نوافذ المداخل والملوح كما هي. والتفريغُ مرشّحٌ للتوقيت وحده، ولا يُكتب منه نصٌّ في أيّ فهرس.

    python tools/alignment_v3/heard_clip.py clip --batch-dir D --surah 31 --url <mp3> --riwaya qalun
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tools" / "alignment"))

ENGINE = "heard-clip-1"
MIN_SIM = 0.7            # أدنى تشابهٍ لأداءٍ في الخريطة (‏= heard_gate.REPEAT_SIM)
TOL_MS = 300             # أقصى فرقٍ بين حدَّي الأداء وحدَّي Whisper (‏أمرُ القائد)
W_K = 3                  # كلماتُ الطرف المطابَقة كلمةً بكلمة
W_MIN_WORD_P = 0.5       # ثقةُ كلّ كلمةٍ طرفيّة (‏كما في pin_heard)
W_MEAN_WORD_P = 0.7
W_LEN_LO, W_LEN_HI = 0.7, 1.3
PAD_MS = 1500            # هامشُ نافذة الشاهد حول الأداء
MAX_WINDOW_MS = 120_000  # حدُّ whisper_witness للنافذة الواحدة
MAX_GAP_MS = 30_000      # أقصى فجوةٍ بين نهاية أداءٍ وبدء أداء تاليتها
MAX_ROUNDS = 6           # جولاتُ الشاهد: كلُّ جولةٍ الأداءُ التالي الأقدمُ للآيات غير المحلولة


def performances(hmap, ayah):
    """أداءاتُ الآية في الخريطة بتشابه ≥ MIN_SIM مرتّبةً بالبدء بلا تكرار: [(بدء، نهاية، تشابه)]."""
    rec = (hmap.get("heardMap") or {}).get(str(ayah)) or {}
    seen, out = set(), []
    cand = [tuple(o[:3]) for o in rec.get("occurrences") or []]
    if rec.get("anchorMs") and rec.get("anchorQuality") is not None:
        cand.append((rec["anchorMs"][0], rec["anchorMs"][1], float(rec["anchorQuality"])))
    for s, e, q in cand:
        s, e, q = int(s), int(e), float(q)
        if q < MIN_SIM or not (0 <= s < e) or (s, e) in seen:
            continue
        seen.add((s, e))
        out.append((s, e, q))
    return sorted(out)


def norm_tokens(words, norm):
    """كلماتُ Whisper مطبَّعةً: [(رمز، بدء، نهاية، ثقة)]؛ الكلمةُ المتشظّية ترث زمنَها وثقتَها."""
    out = []
    for w in words or []:
        for t in norm(str(w.get("w", ""))).split():
            out.append((t, int(w["s"]), int(w.get("e", w["s"])), float(w["p"])))
    return out


def verify(words, ref, perf, norm):
    """يُرجع (دليلٌ dict, None) إن ثبت الأداءُ `perf=(s,e,sim)` بشاهد Whisper، وإلا (None, سببُ الردّ)."""
    n = len(ref)
    if n == 0:
        return None, "لا نصَّ مرجعيَّ للآية"
    toks = norm_tokens(words, norm)
    k = min(W_K, n)
    head, tail = ref[:k], ref[-k:]
    lo, hi = max(k, int(W_LEN_LO * n)), int(W_LEN_HI * n) + 1
    why = "أوّلُ كلماتِ الآية لا يطابق تفريغَ النافذة"
    best = None
    for i in range(len(toks) - k + 1):
        if [t[0] for t in toks[i:i + k]] != head:
            continue
        ends = [j for j in range(i + k - 1, len(toks))
                if [t[0] for t in toks[j - k + 1:j + 1]] == tail and lo <= j - i + 1 <= hi]
        if not ends:
            why = "آخرُ كلماتِ الآية لا يطابق التفريغ أو عددُ كلماته خارج المدى"
            continue
        j = min(ends, key=lambda e: abs((e - i + 1) - n))
        edge = toks[i:i + k] + toks[j - k + 1:j + 1]
        low = min(t[3] for t in edge)
        mean = sum(t[3] for t in edge) / len(edge)
        if low < W_MIN_WORD_P or mean < W_MEAN_WORD_P:
            why = f"ثقةُ الكلمات الطرفيّة دون العتبة (أدناها {low:.2f}، متوسّطُها {mean:.2f})"
            continue
        ws, we = toks[i][1], toks[j][2]
        ds, de = abs(ws - perf[0]), abs(we - perf[1])
        if ds > TOL_MS or de > TOL_MS:
            why = f"حدّا Whisper ({ws}-{we}) يبعدان عن حدّي الأداء ({perf[0]}-{perf[1]}) بـ{ds}/{de}م.ث (>{TOL_MS})"
            continue
        cand = {"ws": ws, "we": we, "pmin": round(low, 3), "pmean": round(mean, 3), "ds": ds, "de": de}
        if best is None or ds + de < best["ds"] + best["de"]:
            best = cand
    if best is None:
        return None, why
    return best, None


def select(verified, n_ayahs):
    """يختار لكلّ آيةٍ **آخرَ أداءٍ ثابتٍ** متّسقٍ مع جارتيه (‏من الأخيرة إلى الأولى).

    `verified`: {آية: [dict(s, e, sim, k, n, ws, we, …)]}. يُرجع ({آية: dict}، [آياتٌ بلا اختيار])."""
    chosen, missing = {}, []
    nxt = None
    for a in range(n_ayahs, 0, -1):
        pick = None
        for v in sorted(verified.get(a, []), key=lambda v: v["s"], reverse=True):
            if nxt is not None:
                # الحدُّ الأعلى لنهاية الأداء بدءُ تاليته (‏مع سماح الشاهد TOL_MS لتماسّ الحدّين)
                if v["e"] > nxt["s"] + 0:
                    continue
                if nxt["s"] - v["e"] > MAX_GAP_MS:
                    continue
            pick = v
            break
        if pick is None:
            missing.append(a)
            nxt = None          # الغيابُ يقطع السلسلة: لا قيدَ على السابقة من غائبة
        else:
            chosen[a] = pick
            nxt = pick
    return chosen, sorted(missing)


def next_windows(hmap, n_ayahs, verified, tried, unresolved):
    """نوافذُ الجولة التالية للشاهد: لكلّ آيةٍ غير محلولةٍ أحدثُ أداءٍ لم يُجرَّب. {a*1000+k: (بدء، نهاية)} + خريطةُ الأداءات."""
    wins, owners = {}, {}
    for a in unresolved:
        perfs = performances(hmap, a)
        for idx in range(len(perfs) - 1, -1, -1):
            if idx in tried.setdefault(a, set()):
                continue
            tried[a].add(idx)
            s, e, q = perfs[idx]
            lo, hi = max(0, s - PAD_MS), e + PAD_MS
            if hi - lo > MAX_WINDOW_MS:
                continue        # لا يُقاس بنافذةٍ واحدة: يُجرَّب الأقدمُ
            key = a * 1000 + (idx + 1)
            wins[key] = (lo, hi)
            owners[key] = (a, idx + 1, len(perfs), (s, e, q))
            break
    return wins, owners


def clip_surah(hmap, ref_words, n_ayahs, witness_runner, norm):
    """يقصّ سورةً واحدة. `witness_runner(wins)` ⇒ {مفتاح: {"words": [...]}}.

    يُرجع dict: ok، entries (‏صيغة batch_run)، evidence، unresolved {آية: سبب}، rounds."""
    verified, tried, reasons = {}, {}, {}
    chosen, missing = {}, list(range(1, n_ayahs + 1))
    rounds = 0
    for rounds in range(1, MAX_ROUNDS + 1):
        wins, owners = next_windows(hmap, n_ayahs, verified, tried, missing)
        if not wins:
            break
        got = witness_runner(wins)
        for key, (a, k, n, perf) in owners.items():
            rec = got.get(str(key)) or got.get(key)
            if not rec:
                reasons[a] = "لا تفريغَ للنافذة في الشاهد"
                continue
            ev, why = verify(rec.get("words"), ref_words(a), perf, norm)
            if ev is None:
                reasons[a] = f"الأداء {k}/{n} [{perf[0]}-{perf[1]}]: {why}"
                continue
            verified.setdefault(a, []).append({"s": perf[0], "e": perf[1], "sim": round(perf[2], 3),
                                               "k": k, "n": n, **ev})
        chosen, missing = select(verified, n_ayahs)
        if not missing:
            break
    unresolved = {}
    for a in missing:
        if not performances(hmap, a):
            unresolved[a] = "لا أداءَ مسموعاً بتشابه ≥ %.2f في الخريطة" % MIN_SIM
        elif verified.get(a):
            unresolved[a] = "أداءاتُها الثابتةُ لا تتّسق مع جارتيها (ترتيبٌ أو فجوةٌ >%d ث)" % (MAX_GAP_MS // 1000)
        else:
            unresolved[a] = reasons.get(a, "لم يثبت أداءٌ تامٌّ بشاهد Whisper")
    if unresolved:
        return {"ok": False, "entries": [], "evidence": {}, "unresolved": unresolved, "rounds": rounds}
    entries, evidence = [], {}
    order = sorted(chosen)
    for a in order:
        v = chosen[a]
        st, en = min(v["s"], v["ws"]), max(v["e"], v["we"])
        entries.append({"ayahIdx": a - 1, "startMs": st, "endMs": en,
                        "conf": min(float(v["sim"]), 0.74), "snapped": False, "matched": 0,
                        "total": 0, "heard": True, "boundary": "clip"})
        evidence[str(a)] = {"performance": [v["s"], v["e"]], "k": v["k"], "of": v["n"], "sim": v["sim"],
                            "whisper": [v["ws"], v["we"]], "diffMs": [v["ds"], v["de"]],
                            "pMin": v["pmin"], "pMean": v["pmean"]}
    for i in range(len(entries) - 1):
        if entries[i]["endMs"] > entries[i + 1]["startMs"]:
            entries[i]["endMs"] = entries[i + 1]["startMs"]       # تماسُّ الحدّين لا تداخل
    return {"ok": True, "entries": entries, "evidence": evidence, "unresolved": {}, "rounds": rounds}


def apply_to_surah_json(rec, result):
    """يُرجع ملفَّ السورة بعد القصّ: المداخلُ المقصوصة + `heardClip` (‏الدليل لكلّ آية) و`engine` كما هو."""
    out = dict(rec)
    out["entries"] = result["entries"]
    out["heardClip"] = {"engine": ENGINE, "tolMs": TOL_MS, "minSim": MIN_SIM, "rounds": result["rounds"],
                        "rule": "آخرُ أداءٍ تامٍّ مثبَتٍ بشاهد Whisper ضمن 300م.ث (‏fixV)",
                        "ayahs": result["evidence"]}
    return out


def inject_header(idx, surah_recs):
    """ينقل `heardClip` من ملفّات السور المأخوذة إلى ترويسة الفهرس: {«س:آ»: دليل}."""
    block = dict(idx.get("heardClip") or {}) if isinstance(idx.get("heardClip"), dict) else {}
    ev = dict(block.get("ayahs") or {})
    for s, rec in surah_recs.items():
        hc = rec.get("heardClip") if isinstance(rec, dict) else None
        if not hc:
            continue
        for a, d in (hc.get("ayahs") or {}).items():
            ev[f"{int(s)}:{int(a)}"] = d
        block.update({"engine": hc.get("engine"), "tolMs": hc.get("tolMs"), "minSim": hc.get("minSim"),
                      "rule": hc.get("rule")})
    if ev:
        block["ayahs"] = dict(sorted(ev.items(), key=lambda kv: tuple(int(x) for x in kv[0].split(":"))))
        idx = dict(idx)
        idx["heardClip"] = block
    return idx


# ───────────────────────────── التشغيل ─────────────────────────────
def subprocess_witness(url, surah, riwaya, model):
    def run(wins):
        spec = ",".join(f"{k}:{s}-{e}" for k, (s, e) in sorted(wins.items()))
        out = tempfile.mkdtemp(prefix="hc_wit_")
        subprocess.run([sys.executable, str(ROOT / "tools" / "index_qa" / "whisper_witness.py"), "--url", url,
                        "--surah", str(surah), "--riwaya", riwaya, "--ayahs", spec, "--model", model,
                        "--out", out], check=True)
        data = json.load(open(os.path.join(out, f"whisper_s{surah:03d}.json"), encoding="utf-8"))
        if data.get("sha256") and data.get("sha256") != run.sha:
            raise SystemExit(f"⛔ بصمةُ صوت الشاهد {str(data.get('sha256'))[:8]} غيرُ بصمة الخريطة {str(run.sha)[:8]}")
        return data.get("ayahs") or {}
    run.sha = None
    return run


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("clip")
    c.add_argument("--batch-dir", required=True)
    c.add_argument("--surah", type=int, required=True)
    c.add_argument("--url", required=True)
    c.add_argument("--riwaya", required=True)
    c.add_argument("--model", default="small", choices=("small", "medium"))
    a = ap.parse_args()
    from common import load_index, load_text, norm, surah_slice                 # noqa: PLC0415
    path = Path(a.batch_dir) / f"s{a.surah:03d}.json"
    if not path.exists():
        print(f"⛔ لا ملفَّ خريطةٍ للسورة {a.surah}: {path}")
        return 0
    rec = json.load(open(path, encoding="utf-8"))
    start, _end, info = surah_slice(load_index(), a.surah)
    texts = load_text(a.riwaya)
    n = int(info["ayahs"])
    ref = lambda ay: norm(texts[start + ay - 1]).split()                       # noqa: E731
    runner = subprocess_witness(a.url, a.surah, a.riwaya, a.model)
    runner.sha = rec.get("sha256")
    res = clip_surah(rec, ref, n, runner, norm)
    if not res["ok"]:
        # ⛔ لا قصَّ بالتخمين: السورةُ تبقى بلا مداخل (‏يُنقل الملفُّ جانباً فلا يدمجه الدمج) ويُكتب السببُ.
        report = Path(a.batch_dir) / f"clip_s{a.surah:03d}.unresolved.json"
        json.dump({"surah": a.surah, "unresolved": res["unresolved"], "rounds": res["rounds"]},
                  open(report, "w", encoding="utf-8"), ensure_ascii=False)
        path.rename(Path(a.batch_dir) / f"s{a.surah:03d}.json.unclipped")
        print(f"⛔ س{a.surah}: لم يثبت أداءٌ تامٌّ لـ{len(res['unresolved'])} آية — تبقى محجوبةً معلَنة")
        for ay, why in sorted(res["unresolved"].items())[:12]:
            print(f"   {a.surah}:{ay} — {why}")
        return 0
    out = apply_to_surah_json(rec, res)
    json.dump(out, open(str(path) + ".part", "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(str(path) + ".part", path)
    print(f"✅ س{a.surah}: قُصّت {len(res['entries'])} آيةً على أدائها الثابت ({res['rounds']} جولة)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
