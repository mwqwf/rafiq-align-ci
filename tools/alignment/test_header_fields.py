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
                         # تُمرَّر كما هي: النسخة والعتبة **لكل سورة** لا للفهرس
                         "vadVersion": d.get("vadVersion"),
                         "vadRel": d.get("vadRel"),
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
    # ⛔ **حقول الليلة الجديدة — عقودها تُفحص لا تُوصف:**
    print(f"lowCount      = {idx['lowCount']}")
    print(f"vad           = {idx['vad']}")
    versions = (idx["vad"]["versions"] or {})
    if versions and sum(versions.values()) != len(per_surah):
        print(f"❌ عدّ النسخ {sum(versions.values())} ≠ سور الفهرس {len(per_surah)}")
        ok = False
    print(f"noSilence     = share {idx['noSilenceShare']} · "
          f"ns:na {idx['noSilenceToAnchor']} · ندرة سكتات {idx['sparsePauses']}")
    low_in_entries = sum(1 for e in idx["entries"] if e["confBand"] == "LOW")
    if idx["lowCount"] != low_in_entries:
        print(f"❌ lowCount {idx['lowCount']} ≠ المحسوب {low_in_entries}")
        ok = False
    # **LOW تُشحن ولا تُعدّ غياباً** — وهذا شرط قبولٍ لا إحصاء.
    if "low-conf" in (idx["missing"].get("byReason") or {}):
        print("❌ سببٌ `low-conf` في الغياب — LOW عادت تُسقط")
        ok = False
    skips = sum(v for k, v in stats.items() if k.startswith("skip:"))
    if skips < 200 and idx["sparsePauses"] is not None:
        print(f"❌ وسمُ ندرة السكتات على مقامٍ صغير ({skips}) — يجب أن يكون null")
        ok = False
    if skips >= 200:
        want = round(stats.get("skip:no-silence", 0) / skips, 3)
        if idx["noSilenceShare"] != want:
            print(f"❌ حصّة الصمت {idx['noSilenceShare']} ≠ {want}")
            ok = False
    # **حقنُ مدخلٍ مقلوب — الحارس يُختبر بما يجب أن يردّه:** يُقلب حدٌّ صالح
    # (نهايته قبل بدايته) فيجب أن يسقط من المداخل ويُعدّ غياباً بسبب `invalid`.
    import copy
    hurt = copy.deepcopy(per_surah)
    victim = None
    for sn in sorted(hurt):
        for e in hurt[sn]["entries"]:
            if e.get("startMs") is not None and e.get("endMs") is not None                     and e["endMs"] > e["startMs"]:
                e["endMs"] = e["startMs"] - 1
                victim = f"{sn}:{e['ayahIdx'] + 1}"
                break
        if victim:
            break
    if victim:
        hurt_idx = make_timing_index(riwaya, reciter, "surah", "KUFI", hurt,
                                     "align-0.2", True)
        gone = victim not in {e["ayahId"] for e in hurt_idx["entries"]}
        marked = hurt_idx["missing"]["byReason"].get("invalid", 0) >= 1
        print(f"حقنُ مقلوبٍ في {victim}: أُسقط {gone} · وُسم invalid {marked}")
        if not (gone and marked):
            print("❌ المدخل المقلوب لم يُسقط أو لم يُوسم")
            ok = False
    print("النتيجة:", "✅ العقود سليمة" if ok else "⚠️ خلل")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]) or 0)
