# -*- coding: utf-8 -*-
"""معايرة «قبل/بعد» لصقل MED — بنمط calibrate.py ومقياسه حرفياً.

المقياس: خطأ الحد = بعده عن فترة الصمت المقبولة بين كلام الآيتين (0 إن وقع داخلها).
معيار النجاح المكلَّف به: ≥90% من **الحدود المصقولة** ضمن ±300م.ث.

python calibrate_v2.py --surah 19 [--surah 20 --surah 23]
"""
import argparse
import copy
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "alignment"))
from validate import band  # noqa: E402

import baseline  # noqa: E402
from gt import W2, boundary_error, ground_truth  # noqa: E402
from refine import refine_surah  # noqa: E402


def evaluate(surah_no, gap_ms=None, key="husary_hafs", log=print):
    d = baseline.build(surah_no, gap_ms=gap_ms, key=key, log=log)
    before = copy.deepcopy(d["entries"])
    gt = d.get("gtBounds") or ground_truth(surah_no, len(before))
    refine_surah(d, log=log)
    after = d["entries"]

    rows = []
    for eb, ea, g in zip(before, after, gt):
        rows.append({
            "ayah": g["ayah"],
            "errBefore": boundary_error(eb["startMs"], g),
            "errAfter": boundary_error(ea["startMs"], g),
            "bandBefore": band(eb["conf"]) if eb["startMs"] is not None else "MISSING",
            "bandAfter": band(ea["conf"]) if ea["startMs"] is not None else "MISSING",
            "refined": ea.get("refined", False),
            "src": ea.get("refineSrc", ""),
        })

    def pct(sel, field):
        v = [r for r in sel if r[field] is not None]
        if not v:
            return 0, 0, 0.0
        ok = sum(1 for r in v if abs(r[field]) <= 300)
        return ok, len(v), ok / len(v) * 100

    ref = [r for r in rows if r["refined"]]
    log(f"\n=== سورة {surah_no} ===")
    ob, tb, pb = pct(rows, "errBefore")
    oa, ta, pa = pct(rows, "errAfter")
    log(f"كل الحدود ±300م.ث: قبل {ob}/{tb} = {pb:.1f}%  ←  بعد {oa}/{ta} = {pa:.1f}%")
    if ref:
        rb = pct(ref, "errBefore")
        ra = pct(ref, "errAfter")
        log(f"الحدود المصقولة ({len(ref)}): قبل {rb[0]}/{rb[1]} = {rb[2]:.1f}%  ←  "
            f"**بعد {ra[0]}/{ra[1]} = {ra[2]:.1f}%** (الهدف ≥90%)")
        # عتبة المشرفة: الصقل الذي يصلح ٣٠ ويكسر ٥ مرفوض ⇒ قِس المكسور صراحةً
        fixed = [r for r in ref if r["errBefore"] is not None and r["errAfter"] is not None
                 and abs(r["errBefore"]) > 300 >= abs(r["errAfter"])]
        broken = [r for r in ref if r["errBefore"] is not None and r["errAfter"] is not None
                  and abs(r["errBefore"]) <= 300 < abs(r["errAfter"])]
        worse = [r for r in ref if r["errAfter"] is not None and r["errBefore"] is not None
                 and abs(r["errAfter"]) > abs(r["errBefore"]) + 50]
        log(f"✅ أُصلح (كان >300 فصار ≤300): {len(fixed)} {[r['ayah'] for r in fixed][:20]}")
        log(f"⛔ كُسر (كان ≤300 فصار >300): {len(broken)} {[r['ayah'] for r in broken][:20]}")
        log(f"↘ تدهور >50م.ث بلا كسر عتبة: {len(worse)} {[r['ayah'] for r in worse][:15]}")
        d["fixedBroken"] = (len(fixed), len(broken))
    else:
        log("لا حدود مصقولة!")
    bb = {}
    ba = {}
    for r in rows:
        bb[r["bandBefore"]] = bb.get(r["bandBefore"], 0) + 1
        ba[r["bandAfter"]] = ba.get(r["bandAfter"], 0) + 1
    log(f"النطاقات: قبل {bb}  ←  بعد {ba}")
    tag = f"tight{gap_ms}_" if gap_ms is not None else ""
    out = os.path.join(W2, f"calib_v2_{tag}{key}_s{surah_no:03d}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"surah": surah_no, "rows": rows, "stats": d.get("refineStats")},
                  f, ensure_ascii=False, indent=1)
    log(f"التفاصيل: {out}")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--surah", type=int, action="append", required=True)
    ap.add_argument("--reciter", default="husary_hafs",
                    help="مفتاح القارئ في gt.SOURCES (اختبار التعميم)")
    ap.add_argument("--gap", type=int, default=None,
                    help="ضمّ مُحكم بفجوة gap م.ث (يعيد إنتاج MED بحقيقة أرضية مضبوطة)")
    args = ap.parse_args()
    allrows = []
    for s in args.surah:
        allrows += evaluate(s, gap_ms=args.gap, key=args.reciter)
    ref = [r for r in allrows if r["refined"] and r["errAfter"] is not None]
    if len(args.surah) > 1 and ref:
        ok = sum(1 for r in ref if abs(r["errAfter"]) <= 300)
        print(f"\n=== الإجمالي: الحدود المصقولة {ok}/{len(ref)} = {ok/len(ref)*100:.1f}% "
              f"(الهدف ≥90%) ===")


if __name__ == "__main__":
    main()
