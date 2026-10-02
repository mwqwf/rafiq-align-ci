#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""محاذاةُ **بادئةِ** سورةٍ مصدرُها مبتورُ الذيل — CTC قسريّ على نصّ 1..N (والآيةُ N+1 بالوعةً).

⭐ **سببُه (أمرُ المالك 2026-10-02):** «إن كان البترُ في أوّل السورة أو آخرها فلا بأس
يُعلَن ذلك، لكن إن كان في الوسط تُلغى السورةُ بأكملها». فسورةٌ تسجيلُها الوحيدُ ينقطع
عند آيةٍ (النورُ عند العكري قالون: الملفُّ 766.9ث ينقطع وسط 24:32) **تُنشر بادئتُها
المتّصلة 1..N ويُعلَن ذيلُها N+1..آخرها غائباً بسبب `source_truncated`** — ولا فجوةَ وسطيّة.

**لماذا لا تكفي محاذاةُ السورة كاملةً (`ctc_seg.run_surah`)؟** لأنّ المحاذاةَ القسريّة
تفرض **كلَّ** النصّ على الصوت: نصُّ 33..64 لا صوتَ له فيُضغط على ذيل الملفّ ويُزاح معه
ما قبله. فهنا يُفرض النصُّ الذي **يوجد صوتُه فقط**: البسملةُ ثمّ 1..N، والآيةُ N+1
**بالوعةً** تمتصّ ما بعد N حتى نهاية الملفّ (ولا تُنشر). وهذا عينُ القياس الذي أثبت
1..30 للعكري (`ops/source-repair/akri_noor_available_prefix_diagnostic-20261002.json`).

⛔ **ما لا يفعله:** لا يولّد نصّاً (النصُّ من الرواية) · لا يُنشر منه بالوعةٌ ولا آيةٌ
بلا صوت · لا يُرفع شيئاً (المخرَجُ ملفٌّ محلّيّ بصيغة `batch_run`، يدمجه
`splice_surah.py --truncated-tail` ويرفعه `stage_transform.py --owner-truncated-tail`
بحُرّاسهما، ثمّ البوّابةُ الصوتيّةُ كاملةً).
⛔ **حُرّاسٌ قبل أيّ قبول** — وما لم يجتزها لا يُكتب ملفٌّ أصلاً:
   ١. ثقةُ CTC لكلّ آيةٍ منشورة 1..N ≥ 0.45 (حدُّ MED).
   ٢. مدّةُ كلّ آيةٍ منشورة بين 0.5× و2.0× المتوقَّع (حروفُها × وسيطِ معدّل القارئ في البادئة).
   ٣. الحدودُ صاعدةٌ بلا تداخل، وبدءُ البالوعة (= نهايةُ N) قبل نهاية الملفّ بثانيةٍ على
      الأقلّ — فالملفُّ يحوي صوتاً بعد N، أي أنّ N **قبل** موضع البتر لا بعده.
   ٤. لا HIGH بلا برهان صمت (D-025): الثقةُ تُسقَف 0.74 ما لم يقع الحدُّ في صمت.
⚖️ والحكمُ الحاسم للبوّابة الصوتيّة (مطالع · أربعة ملوح · إحصاءٌ شامل للسورة · عتبة 5%).

النموذج: مع `--quran-model` نموذجُ التلاوة المثبَّتُ البصمة (`quran_ctc_model.py` ·
Apache-2.0 · محرّك `ctc-quran-surah-1`)، وإلا `ctc-seg-1`.

    python tools/alignment_v3/ctc_prefix_align.py --url https://…/024.mp3 --surah 24 \
        --riwaya qalun --keep 30 --quran-model --out-dir tools/alignment/work/batch_akri_qalun
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "alignment"))
from ctc_seg import BASMALA, SR, _conf, _emissions, _segment  # noqa: E402
from ctc_gapsplit import fetch  # noqa: E402
from common import ffprobe_duration_ms, load_index, load_text, norm, surah_slice, to_wav16k  # noqa: E402
from vad import read_wav, silences, snap_to_silence  # noqa: E402

MIN_CONF = 0.45
DUR_LO, DUR_HI = 0.5, 2.0
TAIL_MARGIN_MS = 1000
BASMALA_DIAC = "بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ"


def chars(t: str) -> int:
    return len(norm(t).replace(" ", ""))


def build_rows(segs, n, keep, sil, total_ms):
    """يحوّل مقاطعَ CTC للبسملة+1..keep+1 (بعد قصّ البسملة) إلى صفوف `batch_run`.

    ‏`segs` مقاطعُ النصوص 1..keep+1 بالترتيب: (بدءٌ بالثواني، نهايةٌ بالثواني، درجة).
    يُعيد (الصفوفَ الـn، بدءَ البالوعة بالم.ث)."""
    if len(segs) != keep + 1:
        raise ValueError(f"مقاطعُ CTC {len(segs)} والمطلوبُ {keep + 1}")
    starts, snapped = [], []
    for st, _en, _sc in segs:
        t, on_sil = snap_to_silence(int(st * 1000), sil, tolerance_ms=700)
        starts.append(int(t))
        snapped.append(bool(on_sil))
    rows = []
    for k in range(keep):
        st, en = starts[k], starts[k + 1]
        conf = _conf(segs[k][2])
        if not snapped[k]:
            conf = min(conf, 0.74)                  # ⛔ D-025: لا HIGH بلا صمت
        rows.append({"ayahIdx": k, "startMs": st, "endMs": en, "conf": conf,
                     "snapped": snapped[k]})
    for k in range(keep, n):
        rows.append({"ayahIdx": k, "startMs": None, "endMs": None, "conf": 0.0,
                     "snapped": False})
    return rows, starts[keep]


def prefix_error(rows, keep, char_counts, sink_start_ms, total_ms):
    """سببُ ردّ البادئة، أو None — الحُرّاسُ الأربعة أعلاه."""
    pub = rows[:keep]
    if any(r["startMs"] is None or r["endMs"] is None for r in pub):
        return "آيةٌ في البادئة بلا حدود"
    prev = -1
    for r in pub:
        if not (0 <= r["startMs"] < r["endMs"]) or r["startMs"] < prev:
            return f"{r['ayahIdx'] + 1}: حدودٌ غيرُ صاعدة ({r['startMs']}→{r['endMs']})"
        prev = r["endMs"]
    low = [r["ayahIdx"] + 1 for r in pub if r["conf"] < MIN_CONF]
    if low:
        return f"ثقةُ CTC دون {MIN_CONF} في {low}"
    rates = [(r["endMs"] - r["startMs"]) / max(1, char_counts[r["ayahIdx"]]) for r in pub]
    med = statistics.median(rates)
    for r in pub:
        dur, exp = r["endMs"] - r["startMs"], char_counts[r["ayahIdx"]] * med
        if not (DUR_LO * exp <= dur <= DUR_HI * exp):
            return (f"{r['ayahIdx'] + 1}: مدّتُها {dur}م.ث والمتوقَّع {exp:.0f} "
                    f"(خارج {DUR_LO}–{DUR_HI}×)")
    if sink_start_ms != pub[-1]["endMs"]:
        return "بدءُ البالوعة لا يساوي نهايةَ آخر آيةٍ منشورة"
    if sink_start_ms > total_ms - TAIL_MARGIN_MS:
        return (f"لا صوتَ بعد الآية {keep} ({sink_start_ms}م.ث من {total_ms}) — "
                f"N ليست قبل موضع البتر")
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--url", required=True, help="ملفُّ السورة من الكتالوج نفسِه")
    ap.add_argument("--surah", type=int, required=True)
    ap.add_argument("--riwaya", required=True)
    ap.add_argument("--keep", type=int, required=True,
                    help="N: آخرُ آيةٍ تُنشر (يسمّيها المُطلِق صراحةً، ويُتحقّق منها بالحُرّاس)")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--quran-model", action="store_true",
                    help="نموذجُ التلاوة المثبَّتُ البصمة (محرّك ctc-quran-surah-1)")
    a = ap.parse_args()
    qidx = load_index()
    st0, en0, meta = surah_slice(qidx, a.surah)
    n = meta["ayahs"]
    if not 1 <= a.keep < n:
        raise SystemExit(f"⛔ --keep {a.keep} يجب أن يكون بين 1 و{n - 1} لسورة {a.surah}")
    texts = load_text(a.riwaya)[st0:en0]
    model_evidence = None
    if a.quran_model:
        import quran_ctc_model as Q
        model_evidence = Q.configure()
        refs = [Q.reference_text(t) for t in texts[:a.keep + 1]]
        lead = [] if a.surah in (1, 9) else [Q.reference_text(BASMALA_DIAC)]
    else:
        refs = [norm(t) for t in texts[:a.keep + 1]]
        lead = [] if a.surah in (1, 9) else [norm(BASMALA)]
    os.makedirs(a.out_dir, exist_ok=True)
    mp3 = os.path.join(a.out_dir, f"p{a.surah:03d}.mp3")
    fetch(a.url, mp3)
    sha = hashlib.sha256(open(mp3, "rb").read()).hexdigest()
    wav = to_wav16k(mp3)
    total_ms = ffprobe_duration_ms(mp3)
    x = read_wav(wav).astype(np.float32)
    sil = silences(wav)
    segs = _segment(_emissions(x), len(x), lead + refs)[len(lead):]
    rows, sink_start = build_rows(segs, n, a.keep, sil, total_ms)
    counts = [chars(t) for t in texts]
    why = prefix_error(rows, a.keep, counts, sink_start, total_ms)
    evidence = {"keep": a.keep, "sinkAyah": a.keep + 1, "absentFrom": a.keep + 1,
                "absentTo": n, "sinkStartMs": int(sink_start),
                "sinkAlignedEndMs": int(segs[a.keep][1] * 1000),
                "sinkConf": _conf(segs[a.keep][2]), "totalMs": int(total_ms),
                "reason": "source_truncated"}
    if why:
        print(f"⛔ س{a.surah} بادئة 1..{a.keep}: رُدّت — {why}")
        print(json.dumps({"surah": a.surah, "sha256": sha, "refused": why,
                          "truncatedTail": evidence}, ensure_ascii=False))
        return 1
    out = {"fileRef": a.url, "sha256": sha, "surah": a.surah, "totalMs": int(total_ms),
           "engine": "ctc-quran-surah-1" if a.quran_model else "ctc-seg-1",
           **({"alignmentModel": model_evidence} if model_evidence else {}),
           "truncatedTail": evidence,
           "entries": [dict(r, matched=0, total=len(norm(texts[r["ayahIdx"]]).split()))
                       for r in rows]}
    with open(os.path.join(a.out_dir, f"s{a.surah:03d}.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    bands = {}
    for r in rows[:a.keep]:
        b = "HIGH" if r["conf"] >= 0.75 else ("MED" if r["conf"] >= 0.45 else "LOW")
        bands[b] = bands.get(b, 0) + 1
    print(f"✅ س{a.surah}: بادئة 1..{a.keep} {bands} · البالوعة {a.keep + 1} تبدأ عند "
          f"{sink_start}م.ث من {int(total_ms)} · الذيل {a.keep + 1}..{n} يُعلَن غائباً")
    return 0


if __name__ == "__main__":
    sys.exit(main())
