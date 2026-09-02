# -*- coding: utf-8 -*-
"""رفع فهرس توقيتات مكتمل إلى R2 بمساره القانوني timings/{riwaya}/{reciterId}.jz.

python upload_timings.py --index work/timings_qalun_husary_qalun.jz
يقرأ الميتاداتا من الفهرس نفسه فيشتق المفتاح، ويتحقق بعد الرفع بالقراءة العامة.
"""
import argparse
import json
import os
import urllib.request

import boto3

from common import ROOT, read_jz

SECURE = os.path.join(ROOT, "secure", "r2_credentials.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    args = ap.parse_args()
    ti = read_jz(args.index)
    key = f"timings/{ti['riwaya']}/{ti['reciterId']}.jz"
    c = json.load(open(SECURE))
    s3 = boto3.client("s3", endpoint_url=c["endpoint"],
                      aws_access_key_id=c["accessKeyId"],
                      aws_secret_access_key=c["secretAccessKey"], region_name="auto")
    s3.upload_file(args.index, c["bucket"], key,
                   ExtraArgs={"ContentType": "application/gzip"})
    size = os.path.getsize(args.index)
    print(f"رُفع {key} ({size//1024}ك.ب، {len(ti['entries'])} آية)")

    # تحديث manifest الفهارس (اتفاق مع مستهلك التطبيق 2026-08-31): يغني عن الجس
    import time
    mkey = "timings/manifest.json"
    try:
        cur = json.loads(s3.get_object(Bucket=c["bucket"], Key=mkey)["Body"].read())
    except Exception:
        cur = {"version": 1, "indexes": []}
    row = {"riwaya": ti["riwaya"], "reciterId": ti["reciterId"],
           "entries": len(ti["entries"]), "updatedTs": int(time.time() * 1000)}
    cur["indexes"] = [x for x in cur["indexes"]
                      if not (x["riwaya"] == row["riwaya"] and x["reciterId"] == row["reciterId"])]
    cur["indexes"].append(row)
    cur["updated"] = row["updatedTs"]
    s3.put_object(Bucket=c["bucket"], Key=mkey,
                  Body=json.dumps(cur, ensure_ascii=False).encode(),
                  ContentType="application/json")
    print(f"مانيفست محدث: {len(cur['indexes'])} فهرساً")
    pub = c.get("publicBase") or "https://pub-2c2e1dcd92e84a2898820dd38d3e09e6.r2.dev"
    if pub:
        # r2.dev يحجب وكيل بايثون الافتراضي (403) — وكيل متصفح يلزم
        req = urllib.request.Request(f"{pub.rstrip('/')}/{key}",
                                     headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as r:
            ok = len(r.read()) == size
        print("تحقق القراءة العامة:", "✅" if ok else "❌ حجم مختلف")


if __name__ == "__main__":
    main()
