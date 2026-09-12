# -*- coding: utf-8 -*-
"""🎯 **حدودٌ مثاليّةٌ للتقطيع** — تُستخرج من **النسخة النظيفة** وتُستعمل على المضجَّجة.

⛔ **السؤالُ الذي بُنيت له** (‏D-346 تركه مفتوحاً): انهيارُ الطويل المضجَّج (‏‎−36 نقطة) — أهو
**سمعٌ** أم **حدودٌ**؟ إصلاحُ عتبة السكوت أعطى 8 نطقاتٍ بدل 1 ولم يحرّك الدقّة، لكنّ الثمانيةَ
ليست الحدودَ الصحيحة. وهذا يعطي المضجَّجَ **حدودَ نسخته النظيفة بعينِها** (حقيقةٌ أرضيّةٌ بالبناء،
فالملفّان من صوتٍ واحدٍ أُضيف إليه ضجيج):
  • إن عادت الدقّةُ ⇒ العطبُ **في الكشف** ويُصلَح بخوارزميّة.
  • إن لم تعد ⇒ العطبُ **في السمع** ولا يُصلحه تقطيع ⇒ البابُ نموذجٌ أو رفضُ الحكم.

    python tools/tasmi_bench/make_oracle_cuts.py --clean work/g4 --out work/oracle_g4.json
"""
import argparse, glob, json, os, sys
import numpy as np, soundfile as sf
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import frontend as fe, local_whisper as LW


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    cuts = {}
    for p in sorted(glob.glob(os.path.join(a.clean, "*.wav"))):
        x, _ = sf.read(p, dtype="float32")
        au = fe.normalize_v2(x)
        u = LW.split_at_silences(au, fe.speech_floor_v2(au))
        cuts[os.path.basename(p)[:-4]] = [[int(s), int(e)] for s, e in u]
        del x, au
    json.dump(cuts, open(a.out, "w", encoding="utf-8"))
    n = [len(v) for v in cuts.values()]
    print(f"🎯 {len(cuts)} بنداً · نطقاتٌ وسيطاً {int(np.median(n))} (المدى {min(n)}–{max(n)}) ⇒ {a.out}")


if __name__ == "__main__":
    sys.exit(main())
