#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختبار حقول أثر الصقل في ترويسة الفهرس — على **فهرس حقيقي** لا مصنوع.

يقرأ مخرجات الأسطول (`work/batch_*/s*.json`) ويبني منها الترويسة بنفس الدالة
التي تبني الإنتاج، ثمّ يطبع الحقول ويتحقّق من عقودها الثلاثة:

1. `medTargeted` = مجموع قيم `refineStats` (كل مدخل دخل الصقل خرج منه أثر).
2. `refinedCount` = قيمة `token-snap` في `refineStats` (المصقول فعلاً).
3. `refineVersion` قيمة صريحة دائماً — لا `null` ولا حقلٌ غائب.

التشغيل:  python tools/alignment/test_header_fields.py <مجلد batch_*> [rowaya] [id]
"""
import glob
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from validate import make_timing_index                              # noqa: E402


def load(batch_dir):
    per_surah = {}
    for path in sorted(glob.glob(os.path.join(batch_dir, "s*.json"))):
        d = json.load(open(path, encoding="utf-8"))
        sn = d.get("surah") or int(os.path.basename(path)[1:4])
        per_surah[sn] = {"fileRef": d.get("fileRef") or f"{sn:03d}.mp3",
                         "sha256": d.get("sha256") or d.get("audioSha256"),
                         "entries": d["entries"]}
    return per_surah


def main(batch_dir, riwaya="qalun", reciter="test"):
    per_surah = load(batch_dir)
    if not per_surah:
        raise SystemExit(f"لا مخرجات في {batch_dir}")
    idx = make_timing_index(riwaya, reciter, "surah", "KUFI", per_surah,
                            "align-0.2", True)
    stats = idx["refineStats"]
    print(f"مجلد: {batch_dir} · سور {len(per_surah)} · مداخل {len(idx['entries'])}")
    print(f"refineVersion = {idx['refineVersion']!r}")
    print(f"refinedCount  = {idx['refinedCount']}")
    print(f"medTargeted   = {idx['medTargeted']}")
    print(f"refineStats   = {stats}")
    ok = True
    total = sum(stats.values())
    if total != idx["medTargeted"]:
        print(f"❌ مجموع refineStats {total} ≠ medTargeted {idx['medTargeted']}")
        ok = False
    if stats.get("token-snap", 0) != idx["refinedCount"]:
        print(f"❌ token-snap {stats.get('token-snap', 0)} ≠ refinedCount {idx['refinedCount']}")
        ok = False
    if idx["refineVersion"] is None:
        print("❌ refineVersion = null — القيمة يجب أن تكون صريحة")
        ok = False
    if idx["medTargeted"]:
        rate = idx["refinedCount"] / idx["medTargeted"]
        print(f"معدّل نجاح الصقل = {rate:.1%}")
        if rate > 1:
            print("❌ نسبة تتجاوز 100% — المقام ملوّث")
            ok = False
    print("النتيجة:", "✅ العقود سليمة" if ok else "⚠️ خلل")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]) or 0)
