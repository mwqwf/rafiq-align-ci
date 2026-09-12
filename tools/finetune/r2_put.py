#!/usr/bin/env python3
"""☁️ رفعُ ملفٍّ إلى دلو R2 — من GitHub Actions (أسرارُ `R2_*` في البيئة) أو من جهاز المالك (`secure/r2_credentials.json`).

    python tools/finetune/r2_put.py <ملف محلي> <مفتاح R2> [<ملف> <مفتاح> ...]

المتعدّدُ الأجزاء تلقائيّ في boto3 (`upload_file`) فالملفّاتُ الكبيرة (غيغابايت) تمرّ.
"""
import json, os, sys
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # ويندوز: cp1256 يسقط على الرموز
except Exception: pass

def client():
    import boto3
    from boto3.s3.transfer import TransferConfig
    if os.environ.get("R2_ACCESS_KEY_ID"):
        c = {"endpoint": os.environ["R2_ENDPOINT"], "accessKeyId": os.environ["R2_ACCESS_KEY_ID"],
             "secretAccessKey": os.environ["R2_SECRET_ACCESS_KEY"], "bucket": os.environ["R2_BUCKET"]}
    else:
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        c = json.load(open(os.path.join(root, "secure", "r2_credentials.json")))
    s3 = boto3.client("s3", endpoint_url=c["endpoint"], aws_access_key_id=c["accessKeyId"],
                      aws_secret_access_key=c["secretAccessKey"], region_name="auto")
    return s3, c["bucket"], TransferConfig(multipart_threshold=64 << 20, multipart_chunksize=64 << 20, max_concurrency=4)

def main():
    args = sys.argv[1:]
    if len(args) < 2 or len(args) % 2: sys.exit(__doc__)
    s3, bucket, cfg = client()
    for src, key in zip(args[::2], args[1::2]):
        size = os.path.getsize(src)
        s3.upload_file(src, bucket, key, Config=cfg)
        print(f"☁️ {src} ({size/1e6:.1f} MB) → {key}", flush=True)

if __name__ == "__main__":
    main()
