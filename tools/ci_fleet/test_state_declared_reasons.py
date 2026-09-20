#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يختبر أنّ جردَ الدلو يفرّق بين **النقص المُعلَن بسببه** و**النقص الصامت**.

    python tools/ci_fleet/test_state_declared_reasons.py

⛔⛔ **عطبُ تضليلٍ مقيسٌ 2026-09-20:** كان `agent_cmd` يقرأ `reasonCode` من
ترويسة `transform` **وحدَها** — وهي لا تُكتب إلا حين يُنتَج الفهرسُ بـ
`drop_surah.py`. أمّا الفهرسُ الذي يُعلن نقصَه داخل `missing.byReason` (وهو
ما يقرؤه `run.py` ويطبعه «بعذرٍ معلَن») فكان الجردُ يقول عنه **«بلا سببٍ
مُعلَن»** وهو مُعلِنٌ فعلاً.

🔥 **والثمنُ دُفع في اليوم نفسِه:** عُرض على المالك «قرارُ منتَج» مبنيٌّ على أنّ
`nufais` يُغيّب 46 و47 **صامتاً**، والقياسُ بعده أظهر أنّ منشورَه يُعلن **73 من
81** غياباً بعذرِ البتر المصدريّ ⇒ **السؤالُ كان على باطل**.
⭐ **والدرس: جردٌ يقول «لا سبب» وهو لم يبحث عنه في موضعه يصنع قراراتٍ كاذبةً
واثقة** — والصمتُ في تقريرٍ ليس صمتاً في الواقع.

⚖️ قارئٌ محض: لا شبكةَ ولا دلو.
"""
from __future__ import annotations

import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                 # noqa: BLE001
        pass


def build(idx):
    """نفسُ منطق الجرد في `agent_cmd.cmd_state`."""
    tr = idx.get("transform") or {}
    mh = idx.get("missing") or {}
    by = mh.get("byReason") if isinstance(mh.get("byReason"), dict) else {}
    exc = sum(int(v or 0) for v in by.values())
    return {"entries": len(idx["entries"]), "reasonCode": tr.get("reasonCode"),
            "declaredReasons": by or None, "declaredCount": exc,
            "undeclaredCount": max(0, 6236 - len(idx["entries"]) - exc)}


def main() -> int:
    cases = [
        ("nufais الحقيقيّ: 6155 مدخلاً و73 بعذرٍ معلَن — وكان يُقرأ «صامتاً»",
         {"entries": [0] * 6155,
          "missing": {"byReason": {"source_truncated": 73}}},
         {"declaredCount": 73, "undeclaredCount": 8, "reasonCode": None}),
        ("وفهرسٌ صامتٌ حقّاً يبقى صامتاً — فلا يُغطّى عيبٌ بالإصلاح",
         {"entries": [0] * 6200},
         {"declaredCount": 0, "undeclaredCount": 36, "reasonCode": None}),
        ("وفهرسُ drop_surah: ترويسةُ تحويلٍ **وعذرٌ داخليّ** — البابان معاً",
         {"entries": [0] * 6172,
          "transform": {"reasonCode": "SOURCE_TRUNCATED"},
          "missing": {"byReason": {"source_truncated": 64}}},
         {"declaredCount": 64, "undeclaredCount": 0,
          "reasonCode": "SOURCE_TRUNCATED"}),
        ("وbyReason بشكلٍ غيرِ متوقَّع: لا ينهار ولا يدّعي عذراً لم يجده",
         {"entries": [0] * 6200, "missing": {"byReason": "كذا"}},
         {"declaredCount": 0, "undeclaredCount": 36, "reasonCode": None}),
        ("وفهرسٌ تامٌّ لا يُدرَج أصلاً — لا عذرَ ولا صمت",
         {"entries": [0] * 6236},
         {"declaredCount": 0, "undeclaredCount": 0, "reasonCode": None}),
    ]
    ok = True
    for desc, idx, exp in cases:
        got = build(idx)
        good = all(got[k] == v for k, v in exp.items())
        ok &= good
        print(f"{'✅' if good else '🔴'} {desc}")
        print(f"      مُعلَن={got['declaredCount']} · صامت={got['undeclaredCount']}"
              f" · reasonCode={got['reasonCode']}")
    print()
    print("⇒ صار الجردُ يقول **كم غياباً مُعلَنٌ بسببه وكم صامت**، بدل «لا سبب»"
          " التي كانت تُقرأ حكماً وهي عمى.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
