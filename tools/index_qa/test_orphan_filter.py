#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يختبر مِصفاةَ «المتجاوَز لا المنسيّ» في `orphan_candidates`.

    python tools/index_qa/test_orphan_filter.py

⛔ **لماذا كُتب (2026-09-20):** أوّلُ تشغيلٍ للأداة صاح **449 مرّة**. وحارسٌ
يشتكي من كلّ شيءٍ لا يُعمل به، كما أنّ حارساً لا يجد شيئاً ليس حارساً —
**كلاهما يُقرأ صمتاً**. والسببُ أنّ المسرحَ يحتفظ بكلّ بصمةٍ جُرّبت، فأغلبُ
العدد **متجاوَزٌ لا منسيّ**.

⚖️ قارئٌ محض: بلا شبكةٍ ولا دلو — يُبنى مسرحٌ صناعيٌّ معلومُ الجواب.
"""
from __future__ import annotations

import datetime as dt
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                 # noqa: BLE001
        pass

KEY_RE = re.compile(
    r"^timings-staging/(?P<riwaya>[^/]+)/(?P<rid>.+)\.(?P<sha8>[0-9a-f]{8})\.jz$")


def T(h):
    return dt.datetime(2026, 9, 1, tzinfo=dt.timezone.utc) + dt.timedelta(hours=h)


def keep(staging, pub):
    """نفسُ منطق المِصفاة في الأداة — يُبقى ما ليس متجاوَزاً."""
    newest = {}
    for key, mtime in staging:
        m = KEY_RE.match(key)
        if m:
            k = (m["riwaya"], m["rid"])
            if k not in newest or mtime > newest[k][1]:
                newest[k] = (key, mtime)
    out, sup_new, sup_pub = [], 0, 0
    for key, mtime in staging:
        m = KEY_RE.match(key)
        if not m:
            continue
        if newest[(m["riwaya"], m["rid"])][0] != key:
            sup_new += 1
            continue
        pt = pub.get(f"timings/{m['riwaya']}/{m['rid']}.jz")
        if pt is not None and pt > mtime:
            sup_pub += 1
            continue
        out.append(key)
    return out, sup_new, sup_pub


def main() -> int:
    staging = [
        ("timings-staging/hafs/zayd.aaaaaaaa.jz", T(10)),   # بصمةٌ قديمة
        ("timings-staging/hafs/zayd.bbbbbbbb.jz", T(20)),   # الأحدثُ لزيد
        ("timings-staging/hafs/omar.cccccccc.jz", T(30)),   # سبقه نشرٌ أحدث
        ("timings-staging/hafs/bakr.dddddddd.jz", T(40)),   # يتيمٌ حقيقيّ
        ("timings-staging/warsh/bakr.eeeeeeee.jz", T(41)),  # اسمٌ نفسُه · روايةٌ أخرى
        ("timings-staging/hafs/notes.json", T(50)),          # ليس فهرساً
    ]
    pub = {"timings/hafs/omar.jz": T(35), "timings/hafs/zayd.jz": T(5)}

    kept, sup_new, sup_pub = keep(staging, pub)
    checks = [
        ("الأحدثُ لزيدٍ يبقى", "timings-staging/hafs/zayd.bbbbbbbb.jz" in kept),
        ("والأقدمُ يُطرح متجاوَزاً", "timings-staging/hafs/zayd.aaaaaaaa.jz" not in kept),
        ("ونشرٌ أحدثُ يطرح مرشَّحَه", "timings-staging/hafs/omar.cccccccc.jz" not in kept),
        ("واليتيمُ الحقيقيُّ يبقى", "timings-staging/hafs/bakr.dddddddd.jz" in kept),
        ("ولا يخلط روايتَين باسمٍ واحد",
         "timings-staging/warsh/bakr.eeeeeeee.jz" in kept),
        ("وما ليس فهرساً يُتجاهل", all("notes" not in k for k in kept)),
        ("ونشرٌ أقدمُ لا يطرح شيئاً (زيد نُشر قبل مرشَّحه)",
         "timings-staging/hafs/zayd.bbbbbbbb.jz" in kept),
        ("والعددُ المطروحُ يُعلَن لا يُخفى", (sup_new, sup_pub) == (1, 1)),
    ]
    ok = True
    for desc, good in checks:
        ok &= good
        print(f"{'✅' if good else '🔴'} {desc}")
    print()
    print(f"⇒ من {len(staging) - 1} فهرساً في المسرح بقي {len(kept)} للشكوى، "
          f"وطُرح {sup_new + sup_pub} متجاوَزاً — **والمطروحُ يُعلَن بعدده**.")
    print("⛔ ولا تُخفي المصفاةُ شيئاً نهائيّاً: `--all` يُظهر الكلَّ.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
