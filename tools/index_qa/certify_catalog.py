#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يكتب في الكتالوج **تغطيةَ كل قارئ وشهادتَه** (D-220) — محسوبةً من الدلو لا بيد.

    python tools/index_qa/certify_catalog.py            # عرضٌ فقط
    python tools/index_qa/certify_catalog.py --yes      # يكتب catalog/reciters.json
    python tools/index_qa/certify_catalog.py --self-test

**لماذا** (‏أمر المشرف github-10، 2026-09-05): كشف فحصُ P1 أنّ 26 فهرساً مخدوماً
تغطيتُها 29–95% وهي معدودةٌ «داعمةً لآية-آية»، فيرى المستخدمُ قارئاً في القائمة
ثم لا يجد ثلثَ المصحف عنده. ⇒ الحقلان يجعلان **الواجهة تعرف ما تعرفه البوابة**:

- `ayahCoverage`: نسبةُ مداخل الفهرس المخدوم إلى عدّ الرواية (‏1.0 لمن صوتُه
  مقطَّعٌ آيةً آية أصلاً).
- `ayahCertified`: **صحيحٌ فقط** باجتماع شروط D-220 الثلاثة — تغطيةٌ ≥98%،
  وبلا فشلٍ بنيويّ، **وحكمُ بوابةٍ على البصمة المخدومة نفسها**.

⛔ **حارسٌ يُسقط التوليد كلَّه** (لا يُصلَح بصمت): إن خرج قارئٌ `certified=true`
وليس لبصمته المخدومة حكم، **يُوقَف الكتابة** ويُبلَّغ — لأن شهادةً بلا حكمٍ هي
بعينها العطبُ الذي وُضع الحقلُ ليمنعه.

⛔ **ولا يُغيّر هذا الملفُّ شيئاً غير الحقلين**: يُقارَن الكتالوجُ قبل وبعد،
فإن اختلف حقلٌ ثالثٌ يُوقَف.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import promote  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:                                     # noqa: BLE001
        pass

CATALOG_KEY = "catalog/reciters.json"
MIN_COV = 0.98
CERTIFIER = "certify_catalog-1.0"


def certify(cat, served, verdict_shas):
    """يُرجع (الكتالوجُ الجديد، إحصاء) — دالّةٌ نقيّةٌ تُختبر بلا شبكة."""
    stat = {"certified": 0, "total": 0, "byRiwaya": {}}
    for r in cat.get("riwayat", []):
        rid = r["id"]
        for x in r.get("reciters", []):
            stat["total"] += 1
            key = f"timings/{rid}/{x['id']}.jz"
            if x.get("mode") == "ayah":
                cov, cert = 1.0, True
            elif key in served:
                n, tot, sha, fatal = served[key]
                cov = round(n / max(1, tot), 4)
                cert = bool(cov >= MIN_COV and not fatal and sha in verdict_shas)
            else:
                cov, cert = 0.0, False
            x["ayahCoverage"] = cov
            x["ayahCertified"] = cert
            b = stat["byRiwaya"].setdefault(rid, [0, 0])
            b[1] += 1
            if cert:
                stat["certified"] += 1
                b[0] += 1
    cat["certifiedBy"] = CERTIFIER
    return cat, stat


def _self_test() -> None:
    cat = {"riwayat": [{"id": "hafs", "reciters": [
        {"id": "a", "mode": "ayah"},
        {"id": "b", "mode": "surah"},          # تغطيةٌ كاملةٌ وحكم ⇒ شهادة
        {"id": "c", "mode": "surah"},          # تغطيةٌ ناقصة ⇒ لا
        {"id": "d", "mode": "surah"},          # تغطيةٌ كاملةٌ بلا حكم ⇒ لا
        {"id": "e", "mode": "surah"},          # لا فهرسَ أصلاً ⇒ لا
    ]}]}
    served = {"timings/hafs/b.jz": (6236, 6236, "SHB", False),
              "timings/hafs/c.jz": (3000, 6236, "SHC", False),
              "timings/hafs/d.jz": (6236, 6236, "SHD", False)}
    out, st = certify(json.loads(json.dumps(cat)), served, {"SHB", "SHC"})
    got = {x["id"]: (x["ayahCoverage"], x["ayahCertified"])
           for x in out["riwayat"][0]["reciters"]}
    assert got["a"] == (1.0, True), "ayah أصلاً يُشهد"
    assert got["b"] == (1.0, True), "تغطيةٌ كاملةٌ وحكمٌ ⇒ شهادة"
    assert got["c"][1] is False, "التغطيةُ الناقصة تُسقط الشهادة"
    assert got["d"][1] is False, "⛔ حكمٌ غائبٌ يُسقط الشهادة ولو كانت التغطيةُ كاملة"
    assert got["e"] == (0.0, False), "بلا فهرسٍ لا شهادة"
    # الفشلُ البنيويّ يُسقط الشهادة ولو تمّت التغطيةُ ووُجد الحكم
    served2 = dict(served); served2["timings/hafs/b.jz"] = (6236, 6236, "SHB", True)
    out2, _ = certify(json.loads(json.dumps(cat)), served2, {"SHB"})
    assert out2["riwayat"][0]["reciters"][1]["ayahCertified"] is False, "الفشلُ البنيويّ يُسقط"
    print("  ✅ الشروطُ الثلاثة كلٌّ منها يُسقط الشهادةَ وحده، والمجتمِعُ يُشهد")
    print(f"✅ --self-test أخضر · {CERTIFIER}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        _self_test()
        return

    cl, bucket = promote.s3()
    pg = cl.get_paginator("list_objects_v2")
    keys = []
    for p in pg.paginate(Bucket=bucket, Prefix="timings/"):
        for o in p.get("Contents", []):
            if o["Key"].endswith(".jz"):
                keys.append(o["Key"])

    def load(k):
        raw = cl.get_object(Bucket=bucket, Key=k)["Body"].read()
        d = json.load(gzip.open(io.BytesIO(raw), "rt", encoding="utf-8"))
        fatal = bool((d.get("qa") or {}).get("fatal"))
        return k, (len(d.get("entries") or []), d.get("ayahCount") or 6236,
                   hashlib.sha256(raw).hexdigest(), fatal)
    with ThreadPoolExecutor(12) as ex:
        served = dict(ex.map(load, keys))

    shas = set()
    for p in pg.paginate(Bucket=bucket, Prefix="state/"):
        for o in p.get("Contents", []):
            shas.add(o["Key"])
    # الحكمُ يُنسب إلى البصمة: مفتاحُ الحالة يحمل بادئتَها الثمانية.
    verdict_shas = {s for _, (_, _, s, _) in served.items()
                    if any(s[:8] in k for k in shas)}

    raw_cat = cl.get_object(Bucket=bucket, Key=CATALOG_KEY)["Body"].read()
    before = json.loads(raw_cat)
    after, stat = certify(json.loads(raw_cat), served, verdict_shas)

    # ⛔ الحارس: شهادةٌ بلا حكمٍ تُسقط التوليد كلَّه.
    bad = []
    for r in after.get("riwayat", []):
        for x in r.get("reciters", []):
            if x.get("ayahCertified") and x.get("mode") != "ayah":
                k = f"timings/{r['id']}/{x['id']}.jz"
                if k not in served or served[k][2] not in verdict_shas:
                    bad.append(k)
    if bad:
        sys.exit(f"⛔ شهادةٌ بلا حكمٍ على البصمة المخدومة: {bad[:5]} — يُوقَف التوليد")

    # ⛔ ولا يتغيّر إلا الحقلان.
    def strip(c):
        c = json.loads(json.dumps(c))
        c.pop("certifiedBy", None)
        for r in c.get("riwayat", []):
            for x in r.get("reciters", []):
                x.pop("ayahCoverage", None)
                x.pop("ayahCertified", None)
        return c
    if json.dumps(strip(before), sort_keys=True) != json.dumps(strip(after), sort_keys=True):
        sys.exit("⛔ تغيّر حقلٌ غيرُ الحقلين في الكتالوج — يُوقَف")

    print(f"مشهودون {stat['certified']}/{stat['total']} = "
          f"{stat['certified'] / stat['total']:.1%}")
    for k, (ok, tot) in sorted(stat["byRiwaya"].items()):
        print(f"   {k:8s} {ok:3d}/{tot:3d} = {ok / tot:.0%}")
    if not a.yes:
        print("عرضٌ فقط — أضف --yes للكتابة")
        return
    body = json.dumps(after, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    cl.put_object(Bucket=bucket, Key=CATALOG_KEY, Body=body,
                  ContentType="application/json")
    got = cl.get_object(Bucket=bucket, Key=CATALOG_KEY)["Body"].read()
    if hashlib.sha256(got).hexdigest() != hashlib.sha256(body).hexdigest():
        sys.exit("⛔ ما نزل يخالف ما رُفع — بلاغُ حادثة")
    print(f"↑ كُتب {CATALOG_KEY} ({len(body)} بايت) → ✅")


if __name__ == "__main__":
    main()
