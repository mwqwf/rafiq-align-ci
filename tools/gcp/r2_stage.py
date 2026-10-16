#!/usr/bin/env python3
"""أدوات R2 لسير gcp_train (تعمل على المشغّل لا على الجهاز).

  urls   --out F --expect-step N   روابط GET موقّعة (7 أيام) لملفات models/mushafak1/stage/ ⇒ ملف JSON للجهاز
  export --dir D --out-prefix P    رفع ملفات النقطة من مجلّد محلّي إلى R2 تحت P

الاعتماد من secure/r2_credentials.json (مفاتيح: endpoint · accessKeyId · secretAccessKey · bucket) يكتبه السير من السرّ.
⛔ لا تُطبع روابطُ ولا مفاتيح أبداً: أعدادٌ وأحجامٌ فقط، وتوقيعُ كلّ رابطٍ يُقنَّع في سجلّ Actions.
"""
import argparse
import json
import os
import sys
import urllib.parse

import boto3
from botocore.config import Config

STAGE = "models/mushafak1/stage/"
META_LIMIT = 230_000          # حدّ قيمة metadata الواحدة 256 ك.ب


def client(path):
    c = json.load(open(path, encoding="utf-8"))
    s3 = boto3.client("s3", endpoint_url=c["endpoint"], aws_access_key_id=c["accessKeyId"],
                      aws_secret_access_key=c["secretAccessKey"], region_name="auto",
                      config=Config(signature_version="s3v4", retries={"max_attempts": 5}))
    return s3, c["bucket"]


def mask(url):
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    for k in ("X-Amz-Signature", "X-Amz-Credential"):
        for v in q.get(k, []):
            print(f"::add-mask::{v}")      # أمرُ سير عملٍ يستهلكه المشغّل ولا يظهر في السجلّ


def cmd_urls(a):
    s3, bucket = client(a.creds)
    man = json.loads(s3.get_object(Bucket=bucket, Key=STAGE + "manifest.json")["Body"].read())
    step = int(man.get("step", -1))
    if step < a.expect_step:
        sys.exit(f"::error::خطوة المرحلة {step} دون expect_step={a.expect_step}")
    files = man.get("files") or []
    if not files:
        sys.exit("::error::manifest بلا ملفات")
    out = {"step": step, "manifest": None, "files": []}

    def sign(key):
        u = s3.generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=7 * 86400)
        mask(u)
        return u

    out["manifest"] = sign(STAGE + "manifest.json")
    total = 0
    for f in files:
        key = f["key"]
        full = key if key.startswith(STAGE) else STAGE + key.lstrip("/")
        rel = full[len(STAGE):]
        size = f.get("size", f.get("bytes"))
        sha = f.get("sha256")
        if not sha or size is None:
            sys.exit(f"::error::مدخل manifest بلا sha256/size ({rel})")
        head = s3.head_object(Bucket=bucket, Key=full)      # يتحقّق من الوجود والحجم قبل الإطلاق
        if int(head["ContentLength"]) != int(size):
            sys.exit(f"::error::حجم {rel} في R2 يخالف manifest")
        out["files"].append({"rel": rel, "size": int(size), "sha256": sha, "url": sign(full)})
        total += int(size)
    blob = json.dumps(out, separators=(",", ":"))
    if len(blob) > META_LIMIT:
        sys.exit(f"::error::حزمة الروابط {len(blob)} بايت تتجاوز حدّ metadata")
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write(blob)
    print(f"stage: step={step} files={len(files)} bytes={total} meta_bytes={len(blob)}")


def cmd_export(a):
    s3, bucket = client(a.creds)
    names = [n for n in ("last.pt", "best.pt", "run.json", "status.json") if os.path.exists(os.path.join(a.dir, n))]
    for need in ("last.pt", "run.json"):
        if need not in names:
            sys.exit(f"::error::{need} غائب عن المجلّد — لا تصدير")
    n = 0
    for name in names:
        s3.upload_file(os.path.join(a.dir, name), bucket, a.out_prefix.rstrip("/") + "/" + name)
        n += 1
    print(f"export: uploaded={n} files")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--creds", default="secure/r2_credentials.json")
    sp = ap.add_subparsers(dest="cmd", required=True)
    u = sp.add_parser("urls"); u.add_argument("--out", required=True); u.add_argument("--expect-step", type=int, default=0)
    e = sp.add_parser("export"); e.add_argument("--dir", required=True); e.add_argument("--out-prefix", required=True)
    a = ap.parse_args()
    {"urls": cmd_urls, "export": cmd_export}[a.cmd](a)


if __name__ == "__main__":
    main()
