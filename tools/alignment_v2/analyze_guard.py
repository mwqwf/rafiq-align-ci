# -*- coding: utf-8 -*-
"""تحليل حارس الترقية: علاقة (مصدر الصقل، اتساع فجوة المرساتين) بالخطأ الحقيقي.

يعمل على النوافذ المكاشَفة وحدها — بلا أي استدعاء whisper جديد.
"""
import copy
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "alignment"))

import baseline  # noqa: E402
from gt import boundary_error  # noqa: E402
from refine import refine_surah  # noqa: E402

rows = []
for sn in (19, 20):
    d = baseline.build(sn, gap_ms=80, log=lambda *_: None)
    before = copy.deepcopy(d["entries"])
    gt = d["gtBounds"]
    refine_surah(d, log=lambda *_: None)
    for b, a, g in zip(before, d["entries"], gt):
        if not a.get("refined"):
            continue
        rows.append({"surah": sn, "ayah": g["ayah"], "src": a["refineSrc"],
                     "gap": a.get("refineGap"), "acc": a.get("refineAcc"),
                     "err": boundary_error(a["startMs"], g),
                     "errBefore": boundary_error(b["startMs"], g)})

bad = [r for r in rows if abs(r["err"]) > 300]
print(f"مصقول: {len(rows)} · خارج ±300م.ث: {len(bad)}")
for r in bad:
    print("  ❌", r)
print("\n=== توزيع الفجوة حسب المصدر ===")
for src in sorted({r["src"] for r in rows}):
    g = sorted(r["gap"] for r in rows if r["src"] == src)
    e = [abs(r["err"]) for r in rows if r["src"] == src]
    print(f"{src}: n={len(g)} فجوة وسيط={g[len(g)//2]} أعلى={g[-1]} "
          f"خطأ وسيط={sorted(e)[len(e)//2]} خارج العتبة={sum(1 for x in e if x>300)}")
print("\n=== لو حرسنا: HIGH فقط لـtoken-snap وفجوة ≤ عتبة ===")
for thr in (400, 600, 800, 1000, 1500, 2000, 3000):
    kept = [r for r in rows if r["src"] == "token-snap" and r["gap"] <= thr]
    leak = [r for r in kept if abs(r["err"]) > 300]
    print(f"  عتبة {thr:5d}م.ث: يُرقّى {len(kept):3d}/{len(rows)} · يتسرب خطأ {len(leak)}")
json.dump(rows, open(os.path.join("work", "guard_rows.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
