# -*- coding: utf-8 -*-
"""مراقبة المرآة **من الدلو** لا من الخادم — تعمل رغم انقطاع SSH.

⛔ درسٌ ميداني: انقطع SSH إلى الأسطول الخمسة عن جهاز المالك بينما R2 يعمل
   من الجهاز نفسه، فصار المراقب المبنيّ على SSH يولّد ضجيج انقطاعٍ عن عملٍ
   جارٍ. **والحقيقة من الدلو لا من الخادم** — فمراقبٌ يقرأ الأثر يبقى حياً
   وإن غاب الطريق إلى صانعه.

يطبع سطراً عند كل تغيّر: فهرس جديد · قارئ مُرئي · تشخيص جديد.

    python3 watch_r2.py [--interval 60]
"""
import argparse
import json
import os
import sys
import time

import boto3

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CRED = os.environ.get("R2_CREDENTIALS", "secure/r2_credentials.json")


def client():
    c = json.load(open(CRED, encoding="utf-8"))
    return boto3.client("s3", endpoint_url=c["endpoint"],
                        aws_access_key_id=c["accessKeyId"],
                        aws_secret_access_key=c["secretAccessKey"],
                        region_name="auto"), c["bucket"]


def snapshot(s3, b):
    out = {}
    for pref in ("timings/", "catalog/diagnosis/", "audio/"):
        for pg in s3.get_paginator("list_objects_v2").paginate(
                Bucket=b, Prefix=pref):
            for o in pg.get("Contents", []):
                k = o["Key"]
                if k.endswith(".jz") or k.endswith("manifest.json") \
                        or k.startswith("catalog/diagnosis/"):
                    out[k] = o["ETag"]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=int, default=60)
    a = ap.parse_args()
    s3, b = client()
    prev = snapshot(s3, b)
    print("مراقب R2: {} كائناً مرصوداً · كل {}ث".format(len(prev), a.interval),
          flush=True)
    while True:
        time.sleep(a.interval)
        try:
            cur = snapshot(s3, b)
        except Exception as e:
            print("⚠️ تعذّرت قراءة الدلو: {}".format(str(e)[:80]), flush=True)
            continue
        for k, v in cur.items():
            if k not in prev:
                print("🆕 {}".format(k), flush=True)
            elif prev[k] != v:
                print("♻️ {}".format(k), flush=True)
        prev = cur


if __name__ == "__main__":
    main()
