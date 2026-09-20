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


def classify(sha, pending_sha, struct_sha, n_audio):
    """نفسُ فرزِ الأداة بين البابَين — الوقفُ أسبقُ من اليتم."""
    if sha and sha in pending_sha:
        return "pending"
    if sha in struct_sha and n_audio < 4:
        return "orphan"
    return "none"


def test_two_doors() -> bool:
    """⛔ صنفان من النسيان لا صنفٌ واحد، ولا يُخلط النداءان:
    **يتيمٌ** بوّابتُه ناقصة ⇒ يُستكمل بملوحٍ ومطالع؛
    و**موقوفٌ** بوّابتُه تامّةٌ ولا عطبَ فيه ⇒ ينتظر قرارَ المالك وحدَه.
    والشاهدُ الحيّ: nufais.64811f36 — ثلاثةَ عشرَ ملحاً بلا عطبٍ واحد، موقوفٌ
    منذ 2026-09-05، ولا جردَ في الأسطول كان يُظهره.
    """
    P = {"64811f36": "موقوف — قرارُ منتَجٍ مطلوب: سورٌ محذوفةٌ بإعلانٍ وسبب: [46, 47]"}
    S = {"64811f36", "3987d0e4"}
    cases = [
        ("64811f36", 13, "pending", "موقوفٌ ببوّابةٍ تامّة ⇒ بابُ القرار لا بابُ اليتم"),
        ("64811f36", 0, "pending", "وموقوفٌ بلا ملوحٍ يبقى موقوفاً — الوقفُ أسبقُ"),
        ("3987d0e4", 0, "orphan", "ناجٍ بنيويّاً بلا ملوح ⇒ يتيم"),
        ("3987d0e4", 4, "none", "ناجٍ ببوّابةٍ تامّةٍ ⇒ لا شكوى"),
        ("zzzzzzzz", 0, "none", "لا فحصَ بنيويَّ له ⇒ لا يُشتكى منه"),
    ]
    ok = True
    for sha, n, exp, desc in cases:
        got = classify(sha, P, S, n)
        good = got == exp
        ok &= good
        print(f"{'✅' if good else '🔴'} {desc}")
    return ok


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

    ok_doors = test_two_doors()
    print()
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
    return 0 if (ok and ok_doors) else 1


if __name__ == "__main__":
    raise SystemExit(main())
