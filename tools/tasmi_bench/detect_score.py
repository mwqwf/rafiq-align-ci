# -*- coding: utf-8 -*-
"""قياس **الكشف**: هل يُمسك المحرك الخطأ إذا وقع، وأين؟

لكل صنف حقن (OMIT · SUBSTITUTE · SWAP · INSERT) يقيس ثلاثة أرقام:

1. **نسبة الكشف** — أن يُحكم بخطأٍ داخل نطاق الحقن (الموضع ±1 كلمة).
2. **دقّة الموضع** — أن يقع الحكم على الكلمة المحقونة **بعينها** لا على جارها.
3. **الإنذار الكاذب على السليم من الآية نفسها** — نسبة الكلمات المحكوم عليها
   خطأً **خارج** نطاق الحقن، ومعها خطُّ الأساس من التلاوة السليمة نفسها
   (‏`--clean`) — فالفارق وحده هو ما أحدثه الحقن.

⚠️ يُقرأ مع حدّ العيّنة في `inject.py`: الخطأ المصنوع أنظف من البشري.

    python tools/tasmi_bench/detect_score.py
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import scorer  # noqa: E402

def cfg_for(riwaya):
    """حفص بلا نقل، وورش/قالون به — كما يُشحن (‏naqlTolerant)."""
    return scorer.Config(strip_yeh_barree=True, dagger_optional=True,
                         naql=riwaya not in (None, "hafs"))


def judge(items, hyps):
    """يعيد لكل بند: أحكام الكلمات + عدد الزوائد."""
    out = {}
    for it in items:
        h = hyps.get(it["id"])
        if not h or "error" in h or not h.get("text"):
            continue
        s = scorer.score(it["refText"].split(), h["text"], cfg_for(it.get("riwaya")))
        out[it["id"]] = s
    return out


def zone(it):
    """نطاق الحقن بتسامح ±1 كلمة."""
    lo = it["wordIndex"] - 1
    hi = it["wordIndex"] + (2 if it["op"] == "SWAP" else 1)
    return lo, hi


def wilson(k, n, z=1.96):
    """مجال ثقة 95% لنسبةٍ ثنائية (Wilson) — أصدق من التقريب الطبيعي عند
    النسب القريبة من 1 والعيّنات الصغيرة (40 لكل صنف)."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return (max(0.0, c - h) * 100, min(1.0, c + h) * 100)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", default=os.path.join(HERE, "inject_plan.json"))
    ap.add_argument("--inj", default=os.path.join(HERE, "work", "inj_hyps.json"))
    ap.add_argument("--clean", default=os.path.join(HERE, "work", "clean_hyps.json"))
    ap.add_argument("--require-clean-correct", action="store_true",
                    help="لا تحتسب إلا بنداً كانت كلمته المستهدفة صحيحةً قبل الجراحة "
                         "(تحقّقٌ بعديّ من موضع القطع حين تكون الحدود مشتقّة لا مقيسة)")
    args = ap.parse_args()
    plan = json.load(open(args.plan, encoding="utf-8"))["items"]
    inj = judge(plan, json.load(open(args.inj, encoding="utf-8"))["hyps"])
    clean = judge(plan, json.load(open(args.clean, encoding="utf-8"))["hyps"]) \
        if os.path.exists(args.clean) else {}

    rows, skipped = {}, 0
    for it in plan:
        s = inj.get(it["id"])
        if s is None:
            continue
        c = clean.get(it["id"])
        if args.require_clean_correct:
            # شرطٌ سابق للحُكم: أن يكون التعرّف قد أصاب الكلمة **قبل** الجراحة —
            # وإلا فالبند يقيس عجز النموذج أو خطأ الحدّ لا الكشف.
            if c is None:
                skipped += 1
                continue
            tgt = [w for w in c["words"] if w[0] == it["wordIndex"]]
            if not tgt or tgt[0][1] != scorer.CORRECT:
                skipped += 1
                continue
        lo, hi = zone(it)
        bad = [w for w in s["words"] if w[1] != scorer.CORRECT]
        in_zone = [w for w in bad if lo <= w[0] <= hi]
        exact = [w for w in bad if w[0] == it["wordIndex"]
                 or (it["op"] == "SWAP" and w[0] == it["wordIndex"] + 1)]
        extra_add = len(s["additions"]) - (len(c["additions"]) if c else 0)
        hit = bool(in_zone) or (it["op"] == "INSERT" and extra_add > 0)
        exact_hit = bool(exact) or (it["op"] == "INSERT" and extra_add > 0)
        outside = [w for w in bad if not (lo <= w[0] <= hi)]
        outside_total = sum(1 for w in s["words"] if not (lo <= w[0] <= hi))
        base_bad = 0
        if c:
            base_bad = sum(1 for w in c["words"]
                           if w[1] != scorer.CORRECT and not (lo <= w[0] <= hi))
        r = rows.setdefault(it["op"], {"n": 0, "hit": 0, "exact": 0,
                                       "fa": 0, "faTotal": 0, "faBase": 0})
        r["n"] += 1; r["hit"] += hit; r["exact"] += exact_hit
        r["fa"] += len(outside); r["faTotal"] += outside_total; r["faBase"] += base_bad

    print(f"══ الكشف على الحقن ({sum(r['n'] for r in rows.values())} بنداً، "
          f"خط الأساس السليم: {'موجود' if clean else '⚠️ غائب'}"
          f"{f'، مستبعَد بشرط الصحة قبل الجراحة: {skipped}' if skipped else ''}) ══")
    print(f"{'الصنف':11s} {'ن':>4s} {'كشف':>8s} {'بالموضع':>9s} "
          f"{'إنذار كاذب (سليم الآية)':>26s}")
    for op in ("OMIT", "SUBSTITUTE", "SWAP", "INSERT"):
        r = rows.get(op)
        if not r:
            continue
        fa = r["fa"] / r["faTotal"] * 100 if r["faTotal"] else 0
        fb = r["faBase"] / r["faTotal"] * 100 if r["faTotal"] else 0
        lo, hi = wilson(r["hit"], r["n"])
        print(f"{op:11s} {r['n']:4d} {r['hit']/r['n']*100:7.1f}% [{lo:.1f}–{hi:.1f}] "
              f"{r['exact']/r['n']*100:8.1f}%   {fa:5.1f}% (سليماً {fb:.1f}%)")
    tot = {k: sum(r[k] for r in rows.values()) for k in ("n", "hit", "exact", "fa", "faTotal", "faBase")}
    lo, hi = wilson(tot["hit"], tot["n"])
    print(f"{'الإجمالي':11s} {tot['n']:4d} {tot['hit']/tot['n']*100:7.1f}% [{lo:.1f}–{hi:.1f}] "
          f"{tot['exact']/tot['n']*100:8.1f}%   "
          f"{tot['fa']/tot['faTotal']*100:5.1f}% (سليماً {tot['faBase']/tot['faTotal']*100:.1f}%)")


if __name__ == "__main__":
    main()
