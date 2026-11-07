#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""إحصاءُ نوافذ المداخل — يسمع نافذةَ كلّ مدخلٍ ويحكم أفيها نصُّ الآية وحدَه (‏2026-11-07 · القرار ٢ البند ٥).

    python tools/index_qa/entry_window_census.py repeats --maps DIR --riwaya qalun --surahs 67,78
    python tools/index_qa/entry_window_census.py run --key timings-staging/qalun/maroush_qalun.3ff9b67d.jz \\
        --surahs 67,78 --model small --out out

⭐ **سببُه (قرار القائد 2026-11-07):** بوّابةُ السماع تقيس **بدءَ** الآية وحدَه، فلا ترى مدخلاً يحمل صوتَ آيةٍ
أخرى (‏تكرارُ الكتلة عند maroush: 18:17–23). فلا تُرقّى سورةٌ فيها **تكرارٌ مقيس** إلا بإحصاءٍ يسمع نافذةَ كلّ مدخلٍ
[startMs, endMs] من صوت السورة نفسِه (‏بصمةُ `audioSha256` تُفحص قبل التفريغ)، فيجد فيها نصَّ الآية وحدَه
بعددِ كلماتٍ ضمن حدود `pin_heard`.

**التكرارُ المقيس:** أداءان منفصلان أو أكثر للآية نفسها بتشابه ≥ 0.7 في خريطة السماع، في غير الآيات المتشابهة نصّاً
(‏أداءٌ يقع على موضعِ آيةٍ أخرى تشبه نصَّها ≥ 0.7 ليس تكراراً: هو المتشابهات).

**حكمُ المدخل** (‏Whisper float32 على النافذة · الثوابتُ من `pin_heard` لا نسخةً منها) — **ثلاثةُ أمورٍ مجتمعة**
(‏أمر القائد 2026-11-07 18:58Z، تحلُّ محلّ مطابقة الطرفين والتثليث):
 ١. **توحيدُ الكتابة في الطرفين قبل أيّ مقارنة** بدالّة المستودع `common.norm` (‏تنزع الحركات والألفَ الخنجريّة
    وعلاماتِ المصحف والوقف والتطويل، وتوحّد الهمزات أ إ آ ٱ ؤ ئ ء والألفَ والياء ا ى) — لا نسخةً ثانية منها.
 ٢. **يمرّ المدخلُ إن كانت الآيةُ المتوقَّعة الأقربَ نصّاً إلى التفريغ** من بين نفسها وجاراتها الأربع (±2)، وبهامشٍ
    `NEAREST_MARGIN` ثابتٍ في الشيفرة (‏تشابهُها − تشابهُ أقرب جارة ≥ الهامش؛ وعِلّةُ قيمته عند الثابت).
 ٣. **اختبارُ التحوّر**: مدخلٌ يحمل نصَّ جارته يُردّ حتماً («آية أخرى»)، ومدخلٌ يحمل نصَّ آيتين يُردّ («زيادة»).
 ثمّ **حدودُ عدد الكلمات** (`W_FUZZ_LEN_*`) و**ثوابتُ الثقة** (`W_MIN_WORD_P` · `W_MEAN_WORD_P` على الكلمات الطرفيّة
 للتفريغ) مستورَدةً من `pin_heard` كما هي.
- يُردّ «آية أخرى»: جارةٌ أقربُ من الآية، أو لا هامشَ بينها وبين الآية. (‏وما ظهر في تفريغٍ مردودٍ بالعدد من نصّ آيةٍ
  أخرى — ثلاثُ كلماتٍ متتالية — يُسجَّل في `containsAyah` للتقرير وحدَه، ولا يغيّر الحكم ولا السبب.)
- يُردّ «زيادة»: كلماتُ النافذة فوق الحدّ (‏ويشمل أداءَ الآية نفسِها مرّتين أو آيتين).
- يُردّ «نقص»: لا تفريغَ، أو الكلماتُ دون الحدّ، أو الثقةُ دون العتبة.

⛔ لا يُرقّي ولا يكتب في `timings/` ولا يُعدّل عتبةً ولا حارساً: قارئٌ محض (‏يقرأ المرشّح من الدلو ويكتب JSON محلّياً).
والتفريغُ مرشّحٌ للحكم وحدَه: لا يُكتب منه نصٌّ في أيّ فهرس، والنصُّ المرجعيُّ من `text_<الرواية>.jz` في المستودع.
"""
from __future__ import annotations

import argparse
import difflib
import glob
import gzip
import hashlib
import json
import math
import os
import sys
import tempfile
import wave
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                 # noqa: BLE001
        pass

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import heard_gate                                                    # noqa: E402
import pin_heard as PH                                               # noqa: E402

VERSION = "entry-window-census-2"
SR = 16000
# ثوابتُ الحكم كلُّها من `pin_heard` / `heard_gate` (‏مصدرٌ واحد — لا تُنسخ هنا ولا تُقرأ من البيئة).
K = PH.W_K
MIN_WORD_P = PH.W_MIN_WORD_P
MEAN_WORD_P = PH.W_MEAN_WORD_P
LEN_LO, LEN_HI = PH.W_LEN_LO, PH.W_LEN_HI                    # حدودُ المسار التامّ (‏للمرجع في التقرير)
# ⭐ الحكمُ هنا بمسار `pin_heard` **المشابه** (‏`--witness-fuzzy`): نصُّ المصحف المرجعيّ في روايات ورش/قالون رسمُه
#    بلا ألف الخنجريّة (‏«تبرك» «السما» «اصحب») وWhisper يخرج بالإملاء المعتاد («تبارك» «السماء» «اصحاب»)، فالتطابقُ
#    التامّ يردّ آياتٍ سليمةً (‏قِيس: 24 من 30 في س67 بالتامّ، والتشابهُ ≥ 0.9 في أغلبها). فيُقبل تشابهُ حروف الكلمات
#    الطرفيّة ≥ W_FUZZ_SIM، **وحدودُ عدد الكلمات أضيقُ** (‏W_FUZZ_LEN_*) فلا تنجو نافذةٌ مدموجةٌ أو مبتورة.
FUZZ_SIM = PH.W_FUZZ_SIM
FUZZ_LO, FUZZ_HI = PH.W_FUZZ_LEN_LO, PH.W_FUZZ_LEN_HI
REPEAT_SIM = heard_gate.REPEAT_SIM          # 0.7
MIN_ANCHOR_Q = heard_gate.MIN_Q             # 0.5
SIMILAR_VERSE = 0.7                         # آيتان متشابهتان نصّاً بهذا التشابه فأعلى
# ⭐ هامشُ «الأقرب» (‏أمر القائد 2026-11-07): تشابهُ الآية المتوقَّعة بالتفريغ − تشابهُ أقرب جاراتها (±2) ≥ هذا.
#    عِلّةُ 0.10 (‏من تفريغات small الفعليّة لسورتي 67 و78 على مرشّحَين، `difflib` على النصّ الموحَّد): الفجوةُ لمداخلَ
#    **سليمةٍ** بجاراتٍ متشابهةٍ فعلاً (‏78:4 و78:5 تشابهُهما 0.88) بلغت +0.12 و+0.14 فيجب أن تمرّ؛ والمداخلُ **الملتبسةُ**
#    الفعليّةُ (‏67:1 · 67:16 · 67:22 · 78:7 · 78:10 · 78:11) فجوتُها ≤ +0.08 (‏بعضُها سالب: الجارةُ أقرب) فيجب أن تُردّ؛
#    فالهامشُ في الفاصل بين +0.08 و+0.12. وأيُّ أخفضَ منه يُمرّر ملتبساً، وأيُّ أعلى منه يردّ 78:4 السليمة.
NEAREST_MARGIN = 0.10
NEAREST_RADIUS = 2                          # الجاراتُ المقارَنة: ±2 في السورة
TOKEN_FUZZ = 0.8                            # تسامحُ حرفٍ في كشف نصّ الآية الأخرى (‏كشفُ ردٍّ لا قبول)
OVERLAP_SAME = 0.5                          # تداخلُ زمنين بهذه النسبة من الأقصر ⇒ أداءٌ واحد


# ───────────────────────── تكرارٌ مقيس من خريطة السماع ─────────────────────────
def _text_similar(a: list[str], b: list[str]) -> bool:
    return difflib.SequenceMatcher(None, " ".join(a), " ".join(b)).ratio() >= SIMILAR_VERSE


def _overlap(x, y) -> float:
    """نسبةُ تقاطع زمنَين إلى الأقصر منهما."""
    lo, hi = max(x[0], y[0]), min(x[1], y[1])
    short = min(x[1] - x[0], y[1] - y[0])
    return max(0, hi - lo) / short if short > 0 else 0.0


def _rec(cmap: dict, ayah: int):
    """(مرساة[بدء،نهاية]، جودتها، أداءات[[بدء،نهاية،تشابه]…]) من خريطةٍ كاملة أو مختصرة."""
    hm = cmap.get("heardMap")
    if hm is not None:
        r = hm.get(str(ayah)) or {}
        return r.get("anchorMs"), r.get("anchorQuality"), r.get("occurrences") or []
    r = (cmap.get("anchors") or {}).get(str(ayah))
    if isinstance(r, list):
        r = (r + [None, None, []])[:3]
        return r[0], r[1], r[2] or []
    return None, None, []


def measured_repeats(cmap: dict, texts: dict[int, list[str]]) -> dict[int, dict]:
    """{آية: {performances:[…], excluded:[…]}} للآيات ذواتِ أداءين منفصلَين فأكثر بتشابه ≥ 0.7 في غير المتشابهات.

    الأداءُ = مرساةُ الآية (‏جودة ≥ 0.5) أو أداءٌ مسموعٌ لها بتشابه ≥ 0.7؛ والمتداخلان أكثر من نصف الأقصر أداءٌ واحد.
    والأداءُ الذي يقع على موضع آيةٍ أخرى **تشبه نصَّها** (‏≥ 0.7) يُستثنى ويُسجَّل في `excluded`."""
    ayahs = sorted(texts)
    # مواضعُ كلِّ آية (‏مرساتُها وأداءاتها ≥0.7) لكشف الأداء الواقع على متشابهة
    spans: dict[int, list] = {}
    for a in ayahs:
        am, q, occ = _rec(cmap, a)
        sp = []
        if am and q is not None and float(q) >= MIN_ANCHOR_Q:
            sp.append((int(am[0]), int(am[1])))
        sp += [(int(o[0]), int(o[1])) for o in occ if float(o[2]) >= REPEAT_SIM]
        spans[a] = sp
    similar = {a: {b for b in ayahs if b != a and _text_similar(texts[a], texts[b])} for a in ayahs}
    out: dict[int, dict] = {}
    for a in ayahs:
        am, q, occ = _rec(cmap, a)
        perf, excl = [], []
        cands = []
        if am and q is not None and float(q) >= MIN_ANCHOR_Q:
            cands.append(("مرساة", int(am[0]), int(am[1]), float(q)))
        cands += [("أداء", int(o[0]), int(o[1]), float(o[2])) for o in occ if float(o[2]) >= REPEAT_SIM]
        for kind, s, e, v in cands:
            span = (s, e)
            if e <= s:
                continue
            on_similar = [b for b in similar[a] if any(_overlap(span, x) > OVERLAP_SAME for x in spans[b])]
            if on_similar:
                excl.append({"kind": kind, "startMs": s, "endMs": e, "score": v, "onSimilarAyahs": sorted(on_similar)})
                continue
            if any(_overlap(span, (p["startMs"], p["endMs"])) > OVERLAP_SAME for p in perf):
                continue
            perf.append({"kind": kind, "startMs": s, "endMs": e, "score": v})
        if len(perf) >= 2:
            out[a] = {"performances": perf, "excluded": excl}
    return out


# ───────────────────────── حكمُ نافذة مدخلٍ واحد ─────────────────────────
def _tok_eq(a: str, b: str) -> bool:
    return a == b or difflib.SequenceMatcher(None, a, b).ratio() >= TOKEN_FUZZ


def _trigram_hits(extra: list[str], other: list[str], own_tri: set) -> bool:
    """هل في `extra` ثلاثُ كلماتٍ متتاليةٌ تطابق ثلاثاً متتاليةً من آيةٍ أخرى (‏ولا تطابق نصَّ الآية نفسِها)؟"""
    if len(extra) < K or len(other) < K:
        return False
    for i in range(len(extra) - K + 1):
        tri = tuple(extra[i:i + K])
        if tri in own_tri:
            continue
        for j in range(len(other) - K + 1):
            if all(_tok_eq(tri[m], other[j + m]) for m in range(K)):
                return True
    return False


def other_ayah_in(extra_before: list[str], extra_after: list[str], ayah: int,
                  texts: dict[int, list[str]]) -> int | None:
    """رقمُ آيةٍ أخرى يظهر نصُّها في الكلام الزائد حول الآية المطابقة، أو None."""
    own = texts[ayah]
    own_tri = {tuple(own[i:i + K]) for i in range(max(0, len(own) - K + 1))}
    for b in sorted(texts):
        if b == ayah or texts[b] == own:
            continue
        ref = texts[b]
        for extra in (extra_before, extra_after):
            if _trigram_hits(extra, ref, own_tri):
                return b
        # بدءُ آيةٍ تالية يلاصق الآية (‏كلمتان فأكثر) · وختامُ آيةٍ سابقة يلاصقها من قبل
        t = min(len(extra_after), K)
        if t >= 2 and len(ref) >= t and all(_tok_eq(extra_after[m], ref[m]) for m in range(t)) \
                and tuple(extra_after[:t]) != tuple(own[:t]):
            return b
        t = min(len(extra_before), K)
        if t >= 2 and len(ref) >= t and all(_tok_eq(extra_before[-t + m], ref[-t + m]) for m in range(t)) \
                and tuple(extra_before[-t:]) != tuple(own[-t:]):
            return b
    return None


def _unify(word: str) -> list[str]:
    """توحيدُ الكتابة بدالّة المستودع `common.norm` (‏حركات · ألف خنجريّة · علاماتُ مصحف ووقف · تطويل · همزات · ألف/ياء)."""
    sys.path.insert(0, str(ROOT / "tools" / "alignment"))
    from common import norm                                              # noqa: PLC0415
    return norm(str(word)).split()


def _unify_ref(words: list[str]) -> list[str]:
    return [t for w in words for t in _unify(w)]


def _unify_toks(toks: list[tuple]) -> list[tuple]:
    """(رمز، بدء، ثقة) ⇒ نفسُها برموزٍ موحَّدة (‏الكلمةُ التي تتشظّى ترثها ثقتُها وبدؤها؛ والفارغةُ بعد التوحيد تسقط)."""
    return [(t, s, p) for w, s, p in toks for t in _unify(w)]


def rivals(ayah: int, texts: dict[int, list[str]]) -> list[int]:
    """جاراتُ الآية المنافِسة: ±2 في السورة وهي موجودةٌ ونصُّها يخالف نصَّ الآية
    (‏آيتان نصُّهما واحدٌ لا يُفرِّق بينهما التفريغُ ولا يضرّ خلطُهما نصّاً)."""
    own = texts[ayah]
    return [b for b in range(ayah - NEAREST_RADIUS, ayah + NEAREST_RADIUS + 1)
            if b != ayah and b in texts and texts[b] != own]


def judge_entry(ayah: int, toks: list[tuple], texts: dict[int, list[str]]) -> dict:
    """حكمُ نافذة المدخل: `toks` = [(رمزٌ، بدء م.ث، ثقة)] من تفريغ Whisper لنافذته، و`texts` نصوصُ آيات السورة المرجعيّة.

    يُوحَّد الطرفان أوّلاً، ثمّ: الآيةُ أقربُ بهامشٍ · وعددُ الكلمات في الحدّ · والثقةُ فوق العتبة.
    يُرجع {verdict: pass|reject, reason: '' | آية أخرى | زيادة | نقص, detail, words, refWords, simSelf, simNearest…}."""
    texts = {a: _unify_ref(t) for a, t in texts.items()}
    toks = _unify_toks(toks)
    ref = texts[ayah]
    n = len(ref)
    k = min(K, n)
    got = [t[0] for t in toks]
    total = len(got)
    lo, hi = max(k, math.ceil(FUZZ_LO * n)), math.floor(FUZZ_HI * n)
    sims = {b: PH._sim(got, texts[b]) for b in [ayah] + rivals(ayah, texts)} if got else {}
    s_self = sims.get(ayah, 0.0)
    near, s_near = max(((b, v) for b, v in sims.items() if b != ayah), key=lambda x: x[1], default=(None, 0.0))
    gap = s_self - s_near
    base = {"ayah": ayah, "words": total, "refWords": n, "wordBounds": [lo, hi],
            "heard": " ".join(got), "ratio": round(s_self, 3), "simSelf": round(s_self, 3),
            "nearestOther": near, "simNearestOther": round(s_near, 3), "gap": round(gap, 3),
            "margin": NEAREST_MARGIN}

    def rej(reason, detail, **kw):
        return {**base, "verdict": "reject", "reason": reason, "detail": detail, **kw}

    def other_by_text():
        """تسميةٌ للتقرير: آيةٌ أخرى يظهر نصُّها (‏ثلاثُ كلماتٍ متتالية) في التفريغ."""
        return other_ayah_in(got, [], ayah, texts)

    if not got:
        return rej("نقص", "لا تفريغَ في النافذة (‏صمتٌ أو لا كلام)")
    if near is not None and gap < 0:
        return rej("آية أخرى", f"الآية {near} أقربُ إلى التفريغ من الآية نفسِها ({s_near:.2f} > {s_self:.2f})", otherAyah=near)
    if near is not None and gap < NEAREST_MARGIN:
        return rej("آية أخرى", f"لا هامشَ للآية على الآية {near}: {s_self:.2f} − {s_near:.2f} = {gap:.2f} < {NEAREST_MARGIN}",
                   otherAyah=near)
    if total > hi or total < lo:
        # السببُ بالعدد (‏آيتان فأكثر ⇒ زيادة)، وما يظهر فيه من نصّ آيةٍ أخرى يُسجَّل في `containsAyah` للتقرير وحدَه
        other = other_by_text()
        hint = {"containsAyah": other} if other is not None else {}
        if total > hi:
            return rej("زيادة", f"عددُ كلمات النافذة {total} فوق الحدّ {hi}"
                       + (f" وفيها نصٌّ من الآية {other}" if other else ""), **hint)
        return rej("نقص", f"عددُ كلمات النافذة {total} دون الحدّ {lo}"
                   + (f" وفيها نصٌّ من الآية {other}" if other else ""), **hint)
    edge = toks[:k] + toks[-k:]
    low = min(t[2] for t in edge)
    mean = sum(t[2] for t in edge) / len(edge)
    base.update({"lowP": round(low, 2), "meanP": round(mean, 2), "firstWordMs": toks[0][1]})
    if low < MIN_WORD_P or mean < MEAN_WORD_P:
        return rej("نقص", f"ثقةُ الكلمات الطرفيّة دون العتبة (أدناها {low:.2f}، متوسّطُها {mean:.2f})")
    return {**base, "verdict": "pass", "reason": "",
            "detail": f"الآيةُ الأقرب ({s_self:.2f}" + (f" − {s_near:.2f} من {near} = {gap:.2f}" if near else "") +
                      f") · {total} كلمةً ضمن [{lo},{hi}] · ثقة أدناها {low:.2f}"}


def surah_verdict(rows: list[dict]) -> dict:
    rej = [r for r in rows if r["verdict"] != "pass"]
    return {"ok": not rej and bool(rows), "entries": len(rows), "rejected": len(rej),
            "byReason": {k: sum(1 for r in rej if r["reason"] == k) for k in sorted({r["reason"] for r in rej})},
            "rejectedAyahs": [r["ayah"] for r in rej]}


# ───────────────────────── التنفيذ (‏CI) ─────────────────────────
def surah_texts(riwaya: str, surah: int) -> dict[int, list[str]]:
    sys.path.insert(0, str(ROOT / "tools" / "alignment"))
    from common import load_index, load_text, norm, surah_slice          # noqa: PLC0415
    start, end, _info = surah_slice(load_index(), surah)
    txt = load_text(riwaya)
    return {a + 1: norm(txt[start + a]).split() for a in range(end - start)}


def cmd_repeats(a) -> int:
    surahs = [int(x) for x in a.surahs.replace(",", " ").split()]
    for s in surahs:
        files = glob.glob(os.path.join(a.maps, "**", f"heard_s{s:03d}.json"), recursive=True)
        if not files:
            print(f"س{s}: لا خريطةَ سماعٍ في {a.maps}")
            return 2
        cmap = json.load(open(files[0], encoding="utf-8"))
        rep = measured_repeats(cmap, surah_texts(a.riwaya, s))
        print(f"س{s}: {len(rep)} آيةً بتكرارٍ مقيس {sorted(rep)}")
        for ay, r in sorted(rep.items()):
            print(f"  {s}:{ay} ", " | ".join(f"{p['startMs']}-{p['endMs']}({p['score']})" for p in r["performances"]),
                  (" · مستثنى للمتشابهات: " + str(len(r["excluded"]))) if r["excluded"] else "")
        if a.out:
            Path(a.out).mkdir(parents=True, exist_ok=True)
            json.dump({"surah": s, "repeats": rep}, open(os.path.join(a.out, f"repeats_s{s:03d}.json"), "w",
                                                       encoding="utf-8"), ensure_ascii=False)
    return 0


def cmd_run(a) -> int:
    if (not a.key.startswith("timings-staging/") or a.key.count("/") != 2 or not a.key.endswith(".jz")):
        raise SystemExit("⛔ مفتاحُ مرشّحٍ صريحٌ في timings-staging/ وحده (‏لا كتابةَ في timings/)")
    riwaya = a.key.split("/")[1]
    surahs = [int(x) for x in a.surahs.replace(",", " ").split()]
    import promote as P                                              # noqa: PLC0415
    cl, bucket = P.s3()
    body = cl.get_object(Bucket=bucket, Key=a.key)["Body"].read()
    cand_sha = hashlib.sha256(body).hexdigest()
    idx = json.loads(gzip.decompress(body))
    sys.path.insert(0, str(ROOT / "tools" / "alignment"))
    from common import fetch_retry, to_wav16k                        # noqa: PLC0415
    import numpy as np                                               # noqa: PLC0415
    import faster_whisper                                            # noqa: PLC0415
    from faster_whisper import WhisperModel                          # noqa: PLC0415
    model = WhisperModel(a.model, device="cpu", compute_type="float32", cpu_threads=os.cpu_count() or 2)
    os.makedirs(a.out, exist_ok=True)
    rc = 0
    for s in surahs:
        texts = surah_texts(riwaya, s)
        ents = [e for e in idx["entries"] if str(e["ayahId"]).startswith(f"{s}:") and e.get("startMs") is not None]
        refs = {e.get("fileRef") for e in ents}
        if len(refs) != 1:
            raise SystemExit(f"⛔ س{s}: ملفُّ صوتٍ واحدٌ للسورة مطلوب ({sorted(map(str, refs))[:3]})")
        url = refs.pop()
        want = idx["audioSha256"][s - 1]
        mp3 = os.path.join(a.out, f"{s:03d}.mp3")
        fetch_retry(url, mp3)
        got_sha = hashlib.sha256(open(mp3, "rb").read()).hexdigest()
        if not want or got_sha != want:
            os.remove(mp3)
            print(f"⛔ س{s}: بصمةُ الصوت المنزَّل {got_sha[:8]} ≠ audioSha256 {str(want)[:8]} — لا إحصاء")
            rc = 3
            continue
        wav = to_wav16k(mp3, os.path.join(tempfile.mkdtemp(), "a.wav"))
        with wave.open(wav, "rb") as w:
            if w.getframerate() != SR or w.getnchannels() != 1:
                raise SystemExit("⛔ الصوتُ المفكوك ليس أحاديَّ 16ك.هز")
            pcm = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768.0
        rows = []
        for e in sorted(ents, key=lambda e: int(str(e["ayahId"]).split(":")[1])):
            ay = int(str(e["ayahId"]).split(":")[1])
            st, en = int(e["startMs"]), e.get("endMs")
            if en is None or int(en) <= st:
                rows.append({"ayah": ay, "startMs": st, "endMs": en, "verdict": "reject", "reason": "نقص",
                             "detail": "مدخلٌ بلا نهايةٍ صالحة", "words": 0, "heard": ""})
                continue
            seg = pcm[int(st * SR / 1000):int(int(en) * SR / 1000)]
            segs, _i = model.transcribe(seg, language="ar", beam_size=5, word_timestamps=True,
                                        condition_on_previous_text=False, vad_filter=False, temperature=0.0)
            words = [{"w": x.word.strip(), "s": st + int(x.start * 1000), "p": round(float(x.probability), 4)}
                     for sg in segs for x in (sg.words or [])]
            r = judge_entry(ay, PH._norm_words(words), texts)
            r.update({"startMs": st, "endMs": int(en)})
            rows.append(r)
            print(f"{s}:{ay} [{st}-{en}] ⇒ {r['verdict']} {r['reason']} · {r['detail']}", flush=True)
        os.remove(mp3)
        v = surah_verdict(rows)
        res = {"version": VERSION, "key": a.key, "candidateSha256": cand_sha, "surah": s, "riwaya": riwaya,
               "fileRef": url, "audioSha256": got_sha, "model": a.model, "computeType": "float32",
               "fasterWhisper": getattr(faster_whisper, "__version__", ""), "verdict": v, "entries": rows}
        out = os.path.join(a.out, f"entry_window_census_s{s:03d}.json")
        with open(out + ".part", "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False)
        os.replace(out + ".part", out)
        print(f"■ س{s}: {'✅ كلُّ المداخل تمرّ' if v['ok'] else '⛔ مردودة'} · {v['rejected']}/{v['entries']} · {v['byReason']}")
    return rc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("repeats", help="التكرارُ المقيس من خرائط السماع (‏heard_sNNN.json)")
    r.add_argument("--maps", required=True)
    r.add_argument("--riwaya", required=True)
    r.add_argument("--surahs", required=True)
    r.add_argument("--out", default="")
    q = sub.add_parser("run", help="تفريغُ نافذة كلّ مدخلٍ والحكمُ عليه")
    q.add_argument("--key", required=True)
    q.add_argument("--surahs", required=True)
    q.add_argument("--model", default="small", choices=PH.W_MODELS)
    q.add_argument("--out", required=True)
    a = ap.parse_args()
    return cmd_repeats(a) if a.cmd == "repeats" else cmd_run(a)


if __name__ == "__main__":
    sys.exit(main())
