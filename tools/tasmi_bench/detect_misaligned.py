# -*- coding: utf-8 -*-
"""كاشف بنود العيّنة التي **صوتها ليس آيتها** — عيبُ مصدرٍ لا عيبُ محرك.

الطريقة: يُحاكَم التفريغ على نصّ الآية وجيرانها (±3) بالحاكم نفسه؛ فإن كان
جارٌ أفضل من الآية نفسها بفارق واضح، فالملف الصوتي لآية أخرى — وهو ما يقع
حين يخالف عدُّ آي المصدر عدَّ أصولنا الكوفي (اختلاف العدّ المدني في ورش).

هذه البنود تُستثنى من رقم التتبّع (مع إعلانها) لأنها تقيس **محاذاة المصدر**
لا المحرك؛ وتُبلَّغ لفريق الصوت لأنها تعني أن المستخدم قد يسمع آيةً غير التي
يقرؤها في تلك المواضع.

    python tools/tasmi_bench/detect_misaligned.py --hyps work/hyps_ar_win.json
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))
import scorer  # noqa: E402
from common import load_text  # noqa: E402

BEST_CFG = scorer.Config(strip_yeh_barree=True, dagger_optional=True)
MARGIN = 0.25       # الجار يفوز فقط بفارق ربع — لا نطرد بنداً لتذبذب طفيف


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hyps", default=os.path.join(HERE, "work", "hyps_ar_win.json"))
    ap.add_argument("--out", default=os.path.join(HERE, "work", "misaligned.json"))
    args = ap.parse_args()
    sample = json.load(open(os.path.join(HERE, "sample.json"), encoding="utf-8"))
    hyps = json.load(open(args.hyps, encoding="utf-8"))["hyps"]
    texts = {r: load_text(r) for r in ("hafs", "warsh", "qalun")}
    bad = []
    for it in sample["items"]:
        h = hyps.get(it["id"])
        if not h or not h.get("text"):
            continue
        cfg = scorer.Config(strip_yeh_barree=True, dagger_optional=True,
                            naql=it["riwaya"] != "hafs")
        own = None
        best = (0.0, 0)
        for d in range(-3, 4):
            gi = it["globalIndex"] + d
            if not 0 <= gi < len(texts[it["riwaya"]]):
                continue
            s = scorer.score(texts[it["riwaya"]][gi].split(), h["text"], cfg)
            r = s["correct"] / max(1, s["total"])
            if d == 0:
                own = r
            if r > best[0]:
                best = (r, d)
        if best[1] != 0 and best[0] - own > MARGIN:
            bad.append({"id": it["id"], "reciter": it["reciter"], "riwaya": it["riwaya"],
                        "ayah": f"{it['surah']}:{it['ayah']}", "offset": best[1],
                        "ownScore": round(own, 3), "neighborScore": round(best[0], 3)})
    json.dump({"margin": MARGIN, "items": bad}, open(args.out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"⚠️ {len(bad)} بنداً صوتُه ليس آيتَه → {args.out}")
    for b in bad:
        print(f"   {b['id']} ({b['ayah']}) الجار {b['offset']:+d}: "
              f"{b['ownScore']:.2f} ← {b['neighborScore']:.2f}")


if __name__ == "__main__":
    main()
