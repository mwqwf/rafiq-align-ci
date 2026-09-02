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
import mirror_follower as mf  # noqa

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--threads", type=int, default=12)
    ap.add_argument("--only", default=None, help="riwaya/reciter لواحد فقط")
    a = ap.parse_args()

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
        if idx.get("sourceKind") != "SURAH_FILES":
            skipped += 1
            continue
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
