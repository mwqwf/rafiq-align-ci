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


def plan(argv):
    """يفصل الأزواجَ (ملفٌّ ⇜ مفتاح) عن العلَم — **والعدَدُ الفرديُّ يُرفض** (‏D-496).

    ⛔ **ولماذا الرفضُ لا التجاهل:** `r2_put a.bin k1 b.bin` بعددٍ فرديٍّ **يُزاوج خطأً**
    لو مُضي فيه ⇒ يُرفع ملفٌّ إلى **مفتاح غيره**، وكلُّ رقمٍ نُسب إلى ذلك العنوان يصير
    يدلّ على مادّةٍ أخرى. يُعيد `(None, no_clobber)` عند الخطأ.
    """
    args = [a for a in argv if a != "--no-clobber"]
    no_clobber = "--no-clobber" in argv
    if len(args) < 2 or len(args) % 2:
        return None, no_clobber
    return list(zip(args[::2], args[1::2])), no_clobber


def selftest():
    """🧪 حارسُ الرافع — **بلا شبكةٍ ولا `boto3` ولا سرّ** (‏D-496)."""
    import io, contextlib
    ok = True

    def say(good, line):
        nonlocal ok
        ok &= bool(good)
        print(("✅ " if good else "❌ ") + line)

    # ① المزاوجة: الزوجيُّ يمرّ، والفرديُّ يُرفض، والعلَمُ لا يُعَدّ ملفّاً
    say(plan(["a.bin", "k1", "b.bin", "k2"])[0] == [("a.bin", "k1"), ("b.bin", "k2")],
        "المزاوجةُ السويّة: ملفٌّ ⇜ مفتاح")
    say(plan(["a.bin", "k1", "b.bin"])[0] is None and plan(["a.bin"])[0] is None and plan([])[0] is None,
        "⛔ والعدَدُ الفرديُّ يُرفض — وإلّا رُفع ملفٌّ إلى مفتاح غيره")
    pairs, nc = plan(["--no-clobber", "a.bin", "k1"])
    say(pairs == [("a.bin", "k1")] and nc, "و`--no-clobber` علَمٌ لا ملفّ، ويُقرأ في أيّ موضع")
    say(plan(["a.bin", "k1"])[1] is False, "وبلا العلَم: الكتابةُ فوق القائم مسموحةٌ وتُقال في السجلّ")

    # ② تصنيفُ خطأ السؤال — وهو القاعدةُ المكتوبةُ في `existing` نفسِها
    class Miss(Exception):
        response = {"Error": {"Code": "404"}}

    class Denied(Exception):
        response = {"Error": {"Code": "AccessDenied"}}

    class S3:
        def __init__(self, err=None, head=None):
            self.err, self.head = err, head

        def head_object(self, **_):
            if self.err:
                raise self.err
            return self.head

    was = existing.warned
    try:
        existing.warned = False
        say(existing(S3(err=Miss()), "b", "k") is None,
            "المفتاحُ الغائبُ ⇒ `None` (‏جديدٌ فعلاً)")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            r1 = existing(S3(err=Denied()), "b", "k")
            r2 = existing(S3(err=Denied()), "b", "k2")
        say(r1 == {} and r2 == {},
            "⛔ وتعذُّرُ السؤال ⇒ `{}` **لا `None`** — فلا يُقرأ الصمتُ «مفتاحٌ جديد»")
        say(buf.getvalue().count("تعذّر السؤالُ") == 1,
            "والتحذيرُ يُقال **مرّةً واحدةً** في الشوط — فتحذيرٌ يُغرق السجلَّ لا يُقرأ")
        h = existing(S3(head={"ContentLength": 4096, "LastModified": "2026-09-14T20:30:00Z"}), "b", "k")
        say(h == {"size": 4096, "when": "2026-09-14T20:30:00"},
            f"والقائمُ يُوصف بحجمه وتاريخه: {h}")
    finally:
        existing.warned = was

    print("\n" + ("✅ الرافعُ يفعل ما يدّعي — ولا يزاوج خطأً ولا يقرأ الصمتَ جِدَّةً"
                  if ok else "❌ الرافعُ لا يفعل ما يدّعي"))
    return 0 if ok else 1


def main():
    if "--selftest" in sys.argv[1:]:
        return selftest()
    pairs, no_clobber = plan(sys.argv[1:])
    if pairs is None: sys.exit(__doc__)
    s3, bucket, cfg = client()
    for src, key in pairs:
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
