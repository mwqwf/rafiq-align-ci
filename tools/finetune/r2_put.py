#!/usr/bin/env python3
"""☁️ رفعُ ملفٍّ إلى دلو R2 — من GitHub Actions (أسرارُ `R2_*` في البيئة) أو من جهاز المالك (`secure/r2_credentials.json`).

    python tools/finetune/r2_put.py <ملف محلي> <مفتاح R2> [<ملف> <مفتاح> ...]
    python tools/finetune/r2_put.py --no-clobber <ملف> <مفتاح>     # لا يكتب فوق قائمٍ البتّة

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

def existing(s3, bucket, key):
    """وصفُ المفتاح إن كان قائماً، أو `None` إن لم يكن، أو `{}` إن تعذّر السؤال.

    ⛔ **ولِمَ يُسأل قبل الرفع (‏2026-09-13):** مفتاحُ R2 **يُكتب فوقه بلا صوت**، فعنوانٌ نُسب
    إليه رقمٌ في اللوحة قد يصير يدلّ على **مادّةٍ أخرى** — وهو الذي أوجب أن تُختم بصمةُ الملفّ
    (`apkSha`) لا عنوانُه. ⇒ فالكتابةُ فوق القائم **تُقال في السجلّ** كي يُعرف متى وقعت.
    ⚠️ **وتعذُّرُ السؤال لا يُقرأ «جديدٌ»**: يُرجَع `{}` ويُطبع، فلا يُبنى على صمتٍ حكمٌ.
    """
    try:
        h = s3.head_object(Bucket=bucket, Key=key)
        return {"size": h.get("ContentLength"), "when": str(h.get("LastModified") or "")[:19]}
    except Exception as e:
        name = type(e).__name__
        code = getattr(e, "response", {}).get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchKey", "NotFound") or name in ("NoSuchKey", "404"):
            return None
        # ⛔ ويُقال **مرّةً واحدةً**: بيانةٌ بلا حقِّ السؤال (‏كتابةٌ فقط) تجعله سطراً مكرّراً في
        #    كلّ مفتاحٍ فيغرق السجلَّ ⇒ **تحذيرٌ يُغرق السجلَّ تحذيرٌ لا يُقرأ**.
        if not existing.warned:
            print(f"⚠️ تعذّر السؤالُ عن مفتاحٍ ({name} {code}) — لا يُقرأ ذلك «مفتاحٌ جديد»، "
                  "ولا يُقال ثانيةً في هذا الشوط", flush=True)
            existing.warned = True
        return {}


existing.warned = False


def main():
    args = [a for a in sys.argv[1:] if a != "--no-clobber"]
    no_clobber = "--no-clobber" in sys.argv[1:]
    if len(args) < 2 or len(args) % 2: sys.exit(__doc__)
    s3, bucket, cfg = client()
    for src, key in zip(args[::2], args[1::2]):
        size = os.path.getsize(src)
        was = existing(s3, bucket, key)
        if was is not None and was:
            msg = (f"⚠️ **كتابةٌ فوق مفتاحٍ قائم** {key} (‏كان {was.get('size')} بايتاً "
                   f"في {was.get('when')}) ⇒ كلُّ رقمٍ نُسب إلى هذا العنوان صار ينسب إلى غيره")
            if no_clobber:
                print(msg.replace("كتابةٌ فوق", "رُفض الرفعُ فوق") + " · `--no-clobber`", flush=True)
                continue
            print(msg, flush=True)
        s3.upload_file(src, bucket, key, Config=cfg)
        print(f"☁️ {src} ({size/1e6:.1f} MB) → {key}", flush=True)

if __name__ == "__main__":
    main()
