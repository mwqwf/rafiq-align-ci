# -*- coding: utf-8 -*-
"""قياس دقة تتبّع التسميع على العيّنة — ومعه مجال ثقة وتصنيف أخطاء.

**المقياس المعلن:** نسبة الكلمات المتتبَّعة صحيحاً **بالموضع** =
مجموع الكلمات المرجعية التي أسندها الحاكم إلى مسموعٍ مطابق في موضعها
÷ مجموع كلمات العيّنة. (لا التطابق الحرفي للنص: كلمة تُسمع صحيحة لكن
تُسند إلى موضع آخر ليست متتبَّعة.)

التلاوة المرجعية صحيحة بالافتراض ⇒ كل ما دون 100% **إنذار كاذب** يظهر
للمستخدم خطأً في تلاوته. ومجال الثقة **bootstrap عنقودي على الآيات** لا على
الكلمات (كلمات الآية الواحدة مرتبطة، فالعنقود هو الآية).

    python tools/tasmi_bench/score.py --hyps work/hyps_ar.json [--variant NAME]
    python tools/tasmi_bench/score.py --compare work/hyps_en.json work/hyps_ar.json
"""
import argparse
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import scorer  # noqa: E402

SAMPLE = os.path.join(HERE, "sample.json")


def load_sample():
    return json.load(open(SAMPLE, encoding="utf-8"))


def config_for(name, riwaya):
    """إعداد الحاكم: `shipped` = المشحون اليوم، `proposed` = بعد إصلاحات
    التقرير (ے→ي، الخنجرية اختيارية، والنقل/الصلة **لورش وقالون وحدهما**
    لأن إسقاط «ال» في حفص خطأُ تلاوةٍ يجب أن يُكشف)."""
    if name == "shipped":
        return scorer.DEFAULT
    return scorer.Config(strip_yeh_barree=True, dagger_optional=True, naql=riwaya != "hafs")


def run(items, hyps, cfg="shipped", exclude=()):
    """يعيد قائمة نتائج لكل بند (مع أحكام الكلمات). [cfg] اسمٌ أو Config."""
    out = []
    for it in items:
        if it["id"] in exclude:
            continue
        c = cfg if isinstance(cfg, scorer.Config) else config_for(cfg, it["riwaya"])
        h = hyps.get(it["id"])
        if h is None or "error" in h or h.get("rc"):
            out.append({**it, "ok": False, "reason": (h or {}).get("error", "غائب")})
            continue
        s = scorer.score(it["refText"].split(), h["text"], c)
        out.append({**it, "ok": True, "hyp": h["text"], "ms": h.get("ms"),
                    "audioMs": h.get("audioMs"), "correct": s["correct"],
                    "total": s["total"], "words": s["words"], "additions": s["additions"]})
    return out


def aggregate(res, seed=7, boot=2000):
    good = [r for r in res if r["ok"]]
    c = sum(r["correct"] for r in good)
    t = sum(r["total"] for r in good)
    rng = random.Random(seed)
    ratios = []
    for _ in range(boot):                     # bootstrap عنقودي: العنقود = آية
        pick = [good[rng.randrange(len(good))] for _ in range(len(good))]
        tt = sum(p["total"] for p in pick)
        ratios.append(sum(p["correct"] for p in pick) / tt if tt else 0)
    ratios.sort()
    lo, hi = ratios[int(0.025 * boot)], ratios[int(0.975 * boot) - 1]
    perfect = sum(1 for r in good if r["correct"] == r["total"])
    return {
        "items": len(res), "scored": len(good), "failed": len(res) - len(good),
        "words": t, "correct": c, "accuracy": c / t if t else 0,
        "ci95": [lo, hi],
        "perfectAyat": perfect, "perfectRate": perfect / len(good) if good else 0,
        "missed": sum(1 for r in good for w in r["words"] if w[1] == scorer.MISSED),
        "substituted": sum(1 for r in good for w in r["words"] if w[1] == scorer.SUBSTITUTED),
        "additions": sum(len(r["additions"]) for r in good),
        "latencyMsMedian": _median([r["ms"] for r in good if r.get("ms")]),
        "rtfMedian": _median([r["ms"] / r["audioMs"] for r in good
                              if r.get("audioMs") and r.get("ms")]),
    }


def _median(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else None


def by_key(res, key):
    out = {}
    for r in res:
        if not r["ok"]:
            continue
        g = out.setdefault(r[key], {"words": 0, "correct": 0, "items": 0})
        g["words"] += r["total"]; g["correct"] += r["correct"]; g["items"] += 1
    for g in out.values():
        g["accuracy"] = g["correct"] / g["words"] if g["words"] else 0
    return out


def report(res, title):
    a = aggregate(res)
    print(f"\n══ {title} ══")
    print(f"  الدقة: {a['accuracy']*100:.2f}%  (ثقة 95%: {a['ci95'][0]*100:.2f}–{a['ci95'][1]*100:.2f})"
          f"  · {a['correct']}/{a['words']} كلمة · {a['scored']} آية")
    print(f"  آيات بلا خطأ واحد: {a['perfectAyat']}/{a['scored']} = {a['perfectRate']*100:.1f}%")
    print(f"  مفقودة {a['missed']} · مُبدلة {a['substituted']} · زائدة {a['additions']}")
    print(f"  الزمن: وسيط {a['latencyMsMedian']}م.ث · RTF وسيط {a['rtfMedian']:.3f}")
    for key in ("riwaya", "stratum", "reciter"):
        d = by_key(res, key)
        line = " · ".join(f"{k} {v['accuracy']*100:.1f}% ({v['items']})"
                          for k, v in sorted(d.items(), key=lambda x: -x[1]["accuracy"]))
        print(f"  حسب {key}: {line}")
    return a


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hyps", default=os.path.join(HERE, "work", "hyps_ar.json"))
    ap.add_argument("--compare")
    ap.add_argument("--dump", help="اكتب نتائج البنود إلى ملف json")
    ap.add_argument("--cfg", default="shipped", choices=["shipped", "proposed"])
    ap.add_argument("--exclude-misaligned", action="store_true",
                    help="استثنِ بنوداً أثبت الكاشف أن صوتها ليس آيتها (عيب مصدر)")
    args = ap.parse_args()
    sample = load_sample()
    hyps = json.load(open(args.hyps, encoding="utf-8"))["hyps"]
    exclude = ()
    if args.exclude_misaligned:
        mis = json.load(open(os.path.join(HERE, "work", "misaligned.json"), encoding="utf-8"))
        exclude = {m["id"] for m in mis["items"]}
    res = run(sample["items"], hyps, args.cfg, exclude)
    a = report(res, f"{os.path.basename(args.hyps)} · {args.cfg}"
                    + (f" · بلا {len(exclude)} مختلّ المصدر" if exclude else ""))
    if args.compare:
        h2 = json.load(open(args.compare, encoding="utf-8"))["hyps"]
        b = report(run(sample["items"], h2, args.cfg, exclude), os.path.basename(args.compare))
        print(f"\n  الفرق: {(b['accuracy']-a['accuracy'])*100:+.2f} نقطة")
    if args.dump:
        json.dump([{k: v for k, v in r.items() if k != "words"} for r in res],
                  open(args.dump, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
