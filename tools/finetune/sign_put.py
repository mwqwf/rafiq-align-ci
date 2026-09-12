#!/usr/bin/env python3
"""🔏 روابطُ PUT موقّعةٌ مسبقاً لمخرَجات التدريب — تُوقَّع على جهاز المالك ولا يغادره سرّ.

    python tools/finetune/sign_put.py [--days 7] [--prefix finetune/out_v2]
    python tools/finetune/sign_put.py --env --hours 8 --prefix finetune/out_v2_cpu >> "$GITHUB_ENV"   # في CI

يطبع سطراً واحداً يُلصق قبل `bash run.sh` في خليّة كولاب:
    PUT_LAST='…' PUT_BEST='…' PUT_GGML='…' PUT_LOG='…'
و`--env` يطبع سطراً لكلِّ متغيّر بصيغة `VAR=url` ويقرأ الاعتمادَ من بيئة `R2_*` (GitHub Actions) لا من الملفّ.
كلُّ رابطٍ يسمح بكتابة **مفتاحٍ واحدٍ بعينه** لمدّةٍ محدودة — لا قراءةَ ولا حذفَ ولا مفتاحاً آخر.
"""
import argparse, json, os
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KEYS = {"PUT_LAST": "last.tar", "PUT_BEST": "best.tar", "PUT_GGML": "ggml-q8_0.bin", "PUT_LOG": "train_log.jsonl"}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--prefix", default="finetune/out_v2")
    ap.add_argument("--hours", type=float, default=0, help="مدّةٌ بالساعات (تغلب --days إن أُعطيت)")
    ap.add_argument("--env", action="store_true", help="سطرٌ لكلِّ متغيّر `VAR=url` والاعتمادُ من بيئة R2_* (لـGitHub Actions)")
    a = ap.parse_args()
    import boto3
    if os.environ.get("R2_ACCESS_KEY_ID"):
        c = {"endpoint": os.environ["R2_ENDPOINT"], "accessKeyId": os.environ["R2_ACCESS_KEY_ID"],
             "secretAccessKey": os.environ["R2_SECRET_ACCESS_KEY"], "bucket": os.environ["R2_BUCKET"]}
    else:
        c = json.load(open(os.path.join(ROOT, "secure", "r2_credentials.json")))
    s3 = boto3.client("s3", endpoint_url=c["endpoint"], aws_access_key_id=c["accessKeyId"],
                      aws_secret_access_key=c["secretAccessKey"], region_name="auto")
    ttl = int(a.hours * 3600) if a.hours else a.days * 86400
    parts = []
    for var, name in KEYS.items():
        url = s3.generate_presigned_url("put_object", Params={"Bucket": c["bucket"], "Key": f"{a.prefix}/{name}"},
                                        ExpiresIn=ttl, HttpMethod="PUT")
        parts.append(f"{var}={url}" if a.env else f"{var}='{url}'")
    print(chr(10).join(parts) if a.env else " ".join(parts))

if __name__ == "__main__":
    main()
