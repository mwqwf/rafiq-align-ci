# -*- coding: utf-8 -*-
"""🎓 **G4b — التلاوةُ الطويلة بسلوك المتعلّم**: حالةُ المالك بنصِّها.

⚠️ **لِمَ وُجدت:** قِيس (‏2026-09-09) أن التلاوة الطويلة **النظيفة** تصل كاملةً — المحركُ
ينقل **99٪** من كلماتها (‏50 تسجيلاً · وسيط 50ث) والمرآةُ مثلُه. فليس الطولُ وحدَه هو العلّة.
وشكوى المالك: «أسجّل عدّة آياتٍ ثم يكتب لي بعضَها كأنّه ناقصُ السمع، **وأحياناً في وسط
التلاوة نفسِها**».

⇒ **الفرضيّةُ المتبقّية: الطولُ + سلوكُ المتعلّم معاً.** وقياساتُ سلوك المتعلّم كلُّها (‏G2b)
كانت على **آيةٍ مفردة**، وقياساتُ الطول كلُّها على **قارئٍ محترفٍ متّصل**. فحاصلُ ضربِهما
لم يُقَس قطّ — وهو بالضبط ما يفعله المستخدم.

**ما يُضاف فوق تسجيلات G4:** تردّدٌ وإعادةٌ وبدايةٌ خاطئة وتنحنح، و**سكتاتٌ طويلة
(‏2.5–5ث) تتجاوز `MAX_GAP_SECONDS`** فتفصل المجموعات — وهو ما يصنعه المتعلّمُ الذي
يستذكر الآية التالية.

    python tools/tasmi_bench/build_long_learner.py
"""
import argparse
import json
import os
import sys

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

WORK = os.path.join(HERE, "work")
SRC = os.path.join(WORK, "g4")
OUT = os.path.join(WORK, "g4b")
SR = 16_000

CONDS = ("long-pause", "long-hesitate", "long-combo")


def long_pauses(x, rng, lo=2500, hi=5000, n=3):
    """سكتاتُ استذكارٍ طويلةٌ داخل التلاوة — **تتجاوز عتبةَ فصل المجموعات عمداً**."""
    import augment_learner as AL
    b = AL.word_bounds(x)
    if len(b) < n + 2:
        return x
    cuts = sorted(rng.choice(range(1, len(b) - 1), size=min(n, len(b) - 2), replace=False))
    out, prev = [], 0
    for c in cuts:
        p = b[c][0]
        out.append(x[prev:p])
        out.append(AL.silence(int(rng.integers(lo, hi)), rng))
        prev = p
    out.append(x[prev:])
    return np.concatenate(out).astype("float32")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", action="append", choices=CONDS)
    args = ap.parse_args()

    import augment_learner as AL

    plan = json.load(open(os.path.join(WORK, "long_plan.json"), encoding="utf-8"))
    items = plan["items"]
    conds = args.only or list(CONDS)
    for c in conds:
        os.makedirs(os.path.join(OUT, c), exist_ok=True)

    made = 0
    for it in items:
        src = os.path.join(SRC, it["id"] + ".wav")
        if not os.path.isfile(src):
            continue
        x, sr = sf.read(src, dtype="float32")
        if sr != SR:
            continue
        for c in conds:
            rng = AL.rng_for(it["id"], c)
            if c == "long-pause":
                y = long_pauses(x, rng)
            elif c == "long-hesitate":
                y = AL.apply_restart(AL.apply_repeat(x, rng), rng)
            else:
                y = long_pauses(AL.apply_restart(AL.apply_repeat(x, rng), rng), rng, n=2)
            sf.write(os.path.join(OUT, c, it["id"] + ".wav"), y.astype("float32"), SR, subtype="PCM_16")
        made += 1

    print(f"✅ {made} تسجيلاً × {len(conds)} شرطاً ⇒ {OUT}")
    for c in conds:
        d = os.path.join(OUT, c)
        ds = [sf.info(os.path.join(d, f)).duration for f in os.listdir(d)[:200]]
        if ds:
            print(f"   {c}: وسيطُ المدّة {sorted(ds)[len(ds)//2]:.0f}ث (الأصلُ 50ث)")
    return 0 if made else 1


if __name__ == "__main__":
    raise SystemExit(main())
