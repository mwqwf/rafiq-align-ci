# -*- coding: utf-8 -*-
"""برهان أن الصقل **نفَذ** لا أن وحدته موجودة. يخرج 1 إن لم ينفذ.

⛔ سبب وجوده (بلاغ github-7d وأمر github-f4، 2026-09-02): فحص الاستيراد في
بناء الصورة يثبت أن `refine` **يُستورَد**، ولا يثبت أنه **عمل على مدخل واحد**.
الشاهد الحيّ `timings/qalun/tareq_qalun.jz` — وُلّد بعد الإصلاح وفيه
`refineVersion=none` و`medTargeted=0` مع 1205 مداخل MED.

`medTargeted` هو **المقام**: عدد ما دخل الصقل. فصفرُه **مع وجود MED** يعني أن
الصقل لم يعمل أصلاً — لا أنه عمل فلم يجد ما يصقله (‏b9 قاس لقالون 46%).
⛔ والشرط مزدوج عمداً (أمر f4): `medTargeted == 0` **و** `MED > 0`. فهرسٌ بلا
مدخل MED واحد لا مقام له فيُتجاوَز بلا إنذار كاذب.
"""
import gzip
import json
import sys

d = json.load(gzip.open(sys.argv[1], "rt", encoding="utf-8"))
mt = d.get("medTargeted", 0) or 0
med = sum(1 for e in d.get("entries", []) if e.get("confBand") == "MED")
rv = d.get("refineVersion") or "none"
print(f"🔎 برهان الصقل: medTargeted={mt} · refinedCount={d.get('refinedCount', 0)} "
      f"· refineVersion={rv} · MED في الفهرس={med}")
if mt == 0 and med > 0:
    print("⛔ الصقل لم يعمل: مقامٌ صفر مع وجود MED — فهرسُ جيلٍ أول يبدو مكتملاً.")
    sys.exit(1)
if mt == 0:
    print("ℹ️ لا مداخل MED أصلاً — لا مقام للصقل، ولا حكم.")
sys.exit(0)
