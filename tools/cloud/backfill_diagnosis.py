# -*- coding: utf-8 -*-
"""ختمٌ رجعي: تشخيص كل قارئ له فهرس على الدلو — بالصيغة الآلية نفسها.

⛔ يستدعي `write_diagnosis` من `mirror_follower` نفسه لا نسخةً منه: صيغتان
   تدّعيان أنهما واحدة تفترقان عند أول تعديل، ومستهلكٌ يقرأ إحداهما ويظنّها
   الأخرى يبني على وهم. **منفذُ الكتابة واحد للآلي وللرجعي.**

    python3 backfill_diagnosis.py [--threads 12]
"""
import argparse
import gzip
import json
import sys

sys.path.insert(0, "/root")

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def is_surah_index(idx, catalog_row):
    """حدِّد قارئَ السور بلا تحويل غياب وسمٍ إرثيّ إلى رفضٍ صامت.

    الفهارس الحديثة تصرّح بـ`sourceKind=SURAH_FILES`. أمّا الفهرس الإرثي
    فلا يُقبل إلا بشاهدين مستقلين: الكتالوج يقول وضع السور، والفهرس يحمل
    114 بصمة صوتية. التصريح المخالف يَغلب ولا يُتجاوز.
    """
    kind = idx.get("sourceKind")
    if kind is not None:
        normalized = str(kind).strip().upper().replace("-", "_")
        return normalized in {"SURAH", "SURAH_FILES"}, "sourceKind={}".format(kind)
    mode = str((catalog_row or {}).get("mode") or "").lower()
    hashes = idx.get("audioSha256")
    ok = mode in {"surah", "surah_files", "surah-files"} and (
        isinstance(hashes, list) and len(hashes) == 114
    )
    detail = "legacy mode={} audioSha256={}".format(
        mode or "missing", len(hashes) if isinstance(hashes, list) else "invalid")
    return ok, detail


def self_test():
    hashes = ["x"] * 114
    assert is_surah_index({"sourceKind": "SURAH_FILES"}, {"mode": "ayah"})[0]
    assert is_surah_index({"sourceKind": "surah"}, {"mode": "ayah"})[0]
    assert not is_surah_index({"sourceKind": "AYAH_FILES",
                               "audioSha256": hashes}, {"mode": "surah"})[0]
    assert is_surah_index({"audioSha256": hashes}, {"mode": "surah"})[0]
    assert not is_surah_index({"audioSha256": hashes}, {"mode": "ayah"})[0]
    assert not is_surah_index({"audioSha256": hashes[:-1]}, {"mode": "surah"})[0]
    print("✅ legacy diagnosis source gate: 6/6")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--threads", type=int, default=12)
    ap.add_argument("--only", default=None, help="riwaya/reciter لواحد فقط")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        self_test()
        return

    import mirror_follower as mf  # noqa: E402

    catalog = mf.load_catalog()
    keys = [k for k in mf.listing("timings/") if k.endswith(".jz")]
    if a.only:
        keys = [k for k in keys if a.only in k]
    print("=== ختم تشخيص {} فهرساً ===".format(len(keys)), flush=True)
    done = skipped = 0
    for key in sorted(keys):
        riwaya, rid = key.split("/")[1], key.split("/")[2][:-3]
        try:
            idx = json.loads(gzip.decompress(
                mf.s3.get_object(Bucket=mf.BUCKET, Key=key)["Body"].read()))
        except Exception as e:
            print("  ⚠️ {}: {}".format(key, str(e)[:60]))
            skipped += 1
            continue
        accepted, source_detail = is_surah_index(
            idx, catalog.get((riwaya, rid)))
        if not accepted:
            print("  ↷ {}/{}: ليس مصدر سور ({})".format(
                riwaya, rid, source_detail), flush=True)
            skipped += 1
            continue
        if source_detail.startswith("legacy "):
            print("  ℹ️ {}/{}: فهرس إرثي مقبول بحارسي الكتالوج و114 بصمة ({})".format(
                riwaya, rid, source_detail), flush=True)
        g = mf.surah_duration_guard(riwaya, rid, a.threads)
        cnt = mf.write_diagnosis(riwaya, rid, idx, g, key)
        if cnt is None:
            print("  ⚠️ {}/{}: تعذّر التشخيص".format(riwaya, rid))
            skipped += 1
        else:
            done += 1
            print("  ✅ {}/{} — {}".format(riwaya, rid, cnt or "نظيف"),
                  flush=True)
    print("\n=== كُتب {} · تُخطّي {} ===".format(done, skipped))


if __name__ == "__main__":
    main()
