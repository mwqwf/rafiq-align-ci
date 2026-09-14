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


def ttl_seconds(days, hours):
    """مدّةُ الصلاحية بالثواني — **والساعاتُ تغلب الأيّام إن أُعطيت** (‏D-496).

    ⛔ **ولماذا تُفرَد ويُحرَس حسابُها:** هذه مدّةُ **حقِّ كتابةٍ في الدلو**. قصيرةٌ جدّاً ⇒
    يسقط شوطُ تدريبٍ طويلٌ عند الرفع بعد ساعات؛ طويلةٌ جدّاً ⇒ **رابطُ كتابةٍ حيٌّ أيّاماً**
    في سجلِّ شوطٍ عامّ. فالخطأُ في ضربِ عددٍ هنا **ليس خطأً في العرض**.
    """
    if hours:
        return int(hours * 3600)
    return int(days) * 86400


def key_for(prefix, name):
    """مفتاحُ R2 الكامل — **والشرطةُ الزائدةُ مفتاحٌ آخرُ لا تجميلٌ** (‏D-496).

    ⛔ `finetune/out_v2/` + `ggml-q8_0.bin` بلا تشذيبٍ ⇒ `finetune/out_v2//ggml-q8_0.bin`،
    وهو **مفتاحٌ مغايرٌ تماماً** في S3/R2: يُرفع النموذجُ إليه فيقرأ الأسطولُ القديمَ صامتاً.
    ⛔ **وبادئةٌ فارغةٌ تكتب في جذر الدلو** ⇒ تُرفض.
    """
    p = str(prefix or "").strip().strip("/")
    if not p:
        raise ValueError("⛔ بادئةٌ فارغةٌ تكتب في جذر الدلو — سمِّ `--prefix`")
    return f"{p}/{name}"


def render(pairs, env):
    """صيغةُ المخرَج: `--env` سطرٌ لكلّ متغيّرٍ بلا اقتباس (‏`$GITHUB_ENV` يقرأه حرفيّاً)،
    وإلّا سطرٌ واحدٌ مقتبَسٌ يُلصق في صدفة. ⛔ وخلطُهما يكسر أحدَهما صامتاً."""
    if env:
        return chr(10).join(f"{v}={u}" for v, u in pairs)
    return " ".join(f"{v}='{u}'" for v, u in pairs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--prefix", default="finetune/out_v2")
    ap.add_argument("--hours", type=float, default=0, help="مدّةٌ بالساعات (تغلب --days إن أُعطيت)")
    ap.add_argument("--env", action="store_true", help="سطرٌ لكلِّ متغيّر `VAR=url` والاعتمادُ من بيئة R2_* (لـGitHub Actions)")
    ap.add_argument("--selftest", action="store_true", help="حارسٌ بلا شبكةٍ ولا boto3 ولا سرّ")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    import boto3
    if os.environ.get("R2_ACCESS_KEY_ID"):
        c = {"endpoint": os.environ["R2_ENDPOINT"], "accessKeyId": os.environ["R2_ACCESS_KEY_ID"],
             "secretAccessKey": os.environ["R2_SECRET_ACCESS_KEY"], "bucket": os.environ["R2_BUCKET"]}
    else:
        c = json.load(open(os.path.join(ROOT, "secure", "r2_credentials.json")))
    s3 = boto3.client("s3", endpoint_url=c["endpoint"], aws_access_key_id=c["accessKeyId"],
                      aws_secret_access_key=c["secretAccessKey"], region_name="auto")
    ttl = ttl_seconds(a.days, a.hours)
    pairs = []
    for var, name in KEYS.items():
        url = s3.generate_presigned_url("put_object", Params={"Bucket": c["bucket"], "Key": key_for(a.prefix, name)},
                                        ExpiresIn=ttl, HttpMethod="PUT")
        pairs.append((var, url))
    print(render(pairs, a.env))
    return 0


def selftest():
    """🧪 حارسُ موقِّع الروابط — **بلا شبكةٍ ولا `boto3` ولا سرٍّ واحد** (‏D-496)."""
    ok = True

    def say(good, line):
        nonlocal ok
        ok &= bool(good)
        print(("✅ " if good else "❌ ") + line)

    # ① المدّة: الساعاتُ تغلب الأيّام، وصفرُ ساعاتٍ يسقط إلى الأيّام
    say(ttl_seconds(7, 0) == 604800 and ttl_seconds(7, 8) == 28800 and ttl_seconds(1, 0.5) == 1800,
        "المدّة: 7 أيّامٍ=604800 · و8 ساعاتٍ تغلبها=28800 · ونصفُ ساعةٍ=1800")
    say(ttl_seconds(0, 0) == 0, "وصفرٌ صريحٌ يبقى صفراً — ولا يُخترع افتراضٌ في الحساب")

    # ②⛔ الشرطةُ الزائدةُ مفتاحٌ آخر — وهذا بندُ D-496 نفسُه
    say(key_for("finetune/out_v2", "ggml-q8_0.bin") == "finetune/out_v2/ggml-q8_0.bin",
        "المفتاحُ السويّ")
    say(key_for("finetune/out_v2/", "ggml-q8_0.bin") == "finetune/out_v2/ggml-q8_0.bin"
        and key_for("/finetune/out_v2/", "x") == "finetune/out_v2/x",
        "⛔ والشرطةُ الزائدةُ تُشذَّب: `out_v2//ggml` مفتاحٌ مغايرٌ يقرأ الأسطولُ عنده القديمَ صامتاً")
    for bad in ("", "   ", "/", None):
        try:
            key_for(bad, "x")
            say(False, f"بادئةٌ فارغةٌ ({bad!r}) لم تُرفض — وهي تكتب في جذر الدلو")
            break
        except ValueError:
            pass
    else:
        say(True, "⛔ والبادئةُ الفارغةُ تُرفض بأربع صورٍ — فلا كتابةَ في جذر الدلو")

    # ③ المفاتيحُ الأربعةُ بأسمائها — واسمٌ يتغيّر يرفع نموذجاً لا يقرؤه أحد
    say(KEYS == {"PUT_LAST": "last.tar", "PUT_BEST": "best.tar",
                 "PUT_GGML": "ggml-q8_0.bin", "PUT_LOG": "train_log.jsonl"},
        f"والمفاتيحُ الأربعةُ كما هي: {list(KEYS.values())}")

    # ④ الصيغتان لا تختلطان
    p = [("PUT_GGML", "https://x/y?sig=1"), ("PUT_LOG", "https://x/z?sig=2")]
    say(render(p, True) == "PUT_GGML=https://x/y?sig=1\nPUT_LOG=https://x/z?sig=2",
        "`--env`: سطرٌ لكلٍّ بلا اقتباسٍ (‏`$GITHUB_ENV` يقرأ الاقتباسَ حرفاً فيُفسد الرابط)")
    say(render(p, False) == "PUT_GGML='https://x/y?sig=1' PUT_LOG='https://x/z?sig=2'",
        "وبلا `--env`: سطرٌ واحدٌ مقتبَسٌ للصدفة")

    print("\n" + ("✅ الموقِّعُ يفعل ما يدّعي — ومفتاحُه مفتاحٌ واحدٌ بمدّةٍ محسوبة"
                  if ok else "❌ الموقِّعُ لا يفعل ما يدّعي"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
