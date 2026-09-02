# -*- coding: utf-8 -*-
"""حارس الرفع + الرفع إلى timings-staging/ — نسخة CI.

⛔ لماذا ملفٌ مستقل لا استدعاءُ `run_fleet.py`: ذاك سائقٌ بأثرٍ جانبي عند
الاستيراد (يقرأ القائمة ويشغّل الخيوط في المستوى الأعلى) فلا يمكن استيراد
دوالّه، **و`upload_timings.py` يكتب في `timings/` وهو مسار الإنتاج الذي
يشتغل عليه أسطول الخوادم الآن** — الكتابة فيه من CI تصادمٌ صريح.

⛔ ولماذا لا نُعيد كتابة العتبات: تُقرأ **من `run_fleet.py` نفسه** وقت التشغيل،
فإن غيّرها صاحبها تغيّرت هنا، وإن اختفت **يسقط هذا السكربت بصوتٍ عالٍ** بدل أن
يرفع بعتبةٍ قديمة صامتة.
"""
import argparse
import glob
import gzip
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "alignment"))
from common import ROOT, read_jz  # noqa: E402

FLEET = os.path.join(ROOT, "tools", "cloud", "run_fleet.py")
FROZEN_LIST = os.path.join(ROOT, "tools", "index_qa", "frozen.txt")


def thresholds():
    """العتبات من مصدرها الوحيد — لا نسخة ثانية تتعفّن."""
    src = open(FLEET, encoding="utf-8").read()
    out = {}
    for name in ("GUARD_MIN_ENTRIES", "MIN_SHIPPED"):
        m = re.search(rf"^{name}\s*=\s*(\d+)", src, re.M)
        if not m:
            raise SystemExit(f"⛔ لم أجد {name} في {FLEET} — العتبات تغيّرت شكلاً. أوقف الرفع وراجع.")
        out[name] = int(m.group(1))
    return out


def frozen_refuse(riwaya, rid):
    """حارس التجميد (D-058) مطبَّقاً على staging أيضاً.

    الرفع هنا إلى `timings-staging/` فلا يكتب فوق الإنتاج أصلاً — لكن إنتاج
    نسخةٍ منافسة لفهرسٍ **مجمَّد** يخلط الحكم على صاحبه (تحذير github-b9 في
    `husary_qalun` نصّاً)، والقائمة مصدرها ملف الأسطول لا نسخةً عندي.
    """
    key = f"timings/{riwaya}/{rid}.jz"

    def keys_of(text):
        out = set()
        for line in text.splitlines():
            line = line.split("#", 1)[0].strip()
            if line:
                out.add(line.split()[0])
        return out

    # ⛔ **مصدر الصدق هو الدلو لا الشجرة** (‏D-075، أمر github-f4): شجرة كل
    #    عدّاءٍ لقطةٌ من لحظة استنساخه، وبها سقط رافع الأسطول — جمَّد b9 فهرساً
    #    ورافعٌ بنسخةٍ أقدم لم يرَ التجميد فكتب فوقه. والدلو واحدٌ للجميع.
    frozen = set()
    try:
        import boto3
        c = json.load(open(os.path.join(ROOT, "secure", "r2_credentials.json")))
        s3 = boto3.client("s3", endpoint_url=c["endpoint"],
                          aws_access_key_id=c["accessKeyId"],
                          aws_secret_access_key=c["secretAccessKey"], region_name="auto")
        frozen |= keys_of(s3.get_object(Bucket=c["bucket"], Key="timings/frozen.txt")
                          ["Body"].read().decode("utf-8"))
    except Exception as ex:
        # ⛔ فشلٌ **مغلق**: قائمةٌ لا تُقرأ ليست قائمةً فارغة. وتعذّر الشبكة
        #    ليس إذناً بالكتابة فوق مجمَّد.
        return True, f"⛔ تعذّرت قراءة timings/frozen.txt من الدلو ({ex}) — لا رفع"

    # ⛔ ونضمّ نسخة الشجرة **زيادةً لا بديلاً**: قِيس فعلاً (2026-09-02) أن
    #    نسخة الدلو كانت تنقص `husary_warsh` الذي في الشجرة ⇒ الاستبدال وحده
    #    كان **يُضعف** الحارس ويُطلق مجمَّداً. والاتحاد لا يمكن أن يكون أضعف
    #    من أيٍّ من المصدرين، وأي فرقٍ بينهما يُبلَّغ في السطر أدناه.
    tree = set()
    try:
        with open(FROZEN_LIST, encoding="utf-8") as f:
            tree = keys_of(f.read())
    except FileNotFoundError:
        tree = set()

    only_tree = tree - frozen
    if key in frozen:
        return True, f"{rid} مجمَّد (الدلو)"
    if key in tree:
        return True, f"{rid} مجمَّد (الشجرة وحدها — ⚠️ ينقص الدلو: {sorted(only_tree)})"
    if only_tree:
        print(f"⚠️ انحرافٌ في قائمة التجميد — في الشجرة ولا في الدلو: {sorted(only_tree)}")
    return False, ""


def guard(rid, expect, log_path, th):
    """نفس شروط `index_ok`/`shipped_ok`، مقيسةً على نطاق السور المطلوب فعلاً."""
    d = os.path.join(ROOT, "tools", "alignment", "work", f"batch_{rid}")
    fs = glob.glob(os.path.join(d, "s*.json"))
    if len(fs) < expect:
        return False, f"سور {len(fs)}/{expect}"
    # ⛔ «جزئيٌّ بلا قصد» (اقتراح github-b9 بعد اختباره حارسي بتشغيل فعلي):
    #    `--expect-surahs` مِقبضٌ بيد المستدعي **يُطفئ عتبتَي التغطية وHIGH**.
    #    وهذا صحيحٌ للجزئي الحقيقي (تطبيقهما على سورةٍ من ثلاث آيات رفضٌ كاذب)،
    #    لكنّ الخطر أن تُمرَّر تشغيلةٌ **كاملة** بـ`expect` خاطئ فتخرج بلا
    #    حراسة وتبدو مقبولة. والفرق يُحسم بالواقع لا بالنية: **الجزئي الحقيقي
    #    لا يملك 114 سورة**، فوجودها مع `expect` أصغر خطأُ استدعاءٍ لا تشغيلةٌ
    #    جزئية ⇒ يُوقَف ويُبلَّغ.
    if expect < 114 and len(fs) >= 114:
        return False, (f"⛔ جزئيٌّ بلا قصد: {len(fs)} سورة على القرص بينما "
                       f"--expect-surahs={expect} — خطأُ استدعاءٍ يُطفئ العتبتين. "
                       "صحّح الاستدعاء ولا تتجاوز.")
    n, nosha = 0, 0
    for f in fs:
        try:
            j = json.load(open(f, encoding="utf-8"))
        except Exception as ex:
            return False, f"json معطوب: {ex}"
        n += sum(1 for e in j.get("entries", []) if e.get("startMs") is not None)
        if not j.get("sha256"):
            nosha += 1
    if nosha:
        return False, f"سور بلا بصمة صوت: {nosha}"
    if expect >= 114 and n < th["GUARD_MIN_ENTRIES"]:
        return False, f"مداخل {n} < {th['GUARD_MIN_ENTRIES']}"
    try:
        lg = open(log_path, encoding="utf-8", errors="ignore").read()
        bad = lg.count("Error opening input files") + lg.count("Traceback")
        if bad:
            return False, f"أخطاء صوت/تنفيذ في السجل: {bad}"
    except Exception:
        pass
    return True, f"مداخل {n} · بصمات {len(fs)}/{len(fs)}"


def refine_guard(d):
    """⛔ برهان أن الصقل **عمل** لا أن وحدته موجودة (بلاغ github-7d، 2026-09-02).

    الفرق جوهري وقد أخطأتُ فيه: فحصُ الإقلاع عندي يثبت أن `refine` **يُستورَد**،
    ولا يثبت أنه **نفَذ** على مدخل واحد. والشاهد الحيّ `tareq_qalun` — وُلّد
    بعد الإصلاح وفيه `refineVersion=none` و`medTargeted=0` مع 1205 مدخلاً MED.

    و`medTargeted` هو **المقام**: عدد ما دخل الصقل. فصفرُه يعني أن الصقل لم
    يعمل أصلاً، لا أنه عمل فلم يجد ما يصقله (‏b9 قاس لقالون 46%).
    """
    mt = d.get("medTargeted", 0) or 0
    rv = d.get("refineVersion") or "none"
    if mt == 0:
        return False, (f"⛔ الصقل لم يعمل: medTargeted=0 · refineVersion={rv} — "
                       "فهرسُ جيلٍ أول يبدو مكتملاً. لا يُرفع.")
    # ⛔ ولا يُقاس «قِلّة» الاستهداف عيباً: `medTargeted` **ليس** عدد MED كله.
    #    الصقل لا يستهدف إلا MED الذي له سياق مرساتين؛ والمسنود بصمتٍ يُترك
    #    عمداً. (‏husary_warsh: medTargeted=56 مقابل MED=404 — أثرتُها إنذاراً
    #    فتبيّن أنها الحالة الطبيعية، ثم دُقّق الفهرس صوتياً فقُبل بعطب 0.5%
    #    ورُقّي وجُمّد.) ⇒ ⛔ لا يُضاف حدٌّ أدنى لنسبة medTargeted/MED: يُنتج
    #    رفضاً كاذباً على فهارس سليمة، ولا معدّل مرجعيّ لكل رواية يُبنى عليه.
    return True, f"صقل: medTargeted={mt} · refined={d.get('refinedCount', 0)} · {rv}"


def shipped_guard(idx, expect, th):
    d = json.load(gzip.open(idx, "rt", encoding="utf-8"))
    ok_r, why_r = refine_guard(d)
    if not ok_r:
        return False, why_r
    n = len(d.get("entries", []))
    hi = sum(1 for e in d["entries"] if e.get("confBand") == "HIGH")
    if expect < 114:
        # ⛔ عتبتا التغطية ونسبة HIGH معايرتان على **فهرس قارئ كامل**. تطبيقهما
        #    على تشغيلة اختبار من سورة واحدة رفضٌ كاذب: وقع فعلاً في smoke
        #    33581796764 — سورة 108 ثلاث آيات كلها MED ⇒ «HIGH 0/3 < 50%»،
        #    فبدت السلسلة فاشلة وهي سليمة حتى الرفع. تُقاس ولا تحجب هنا.
        return True, f"مشحون {n} · HIGH {hi} · {why_r} (تشغيلة جزئية: العتبتان لا تنطبقان)"
    if n < th["MIN_SHIPPED"]:
        return False, f"تغطية {n}/6236 < {th['MIN_SHIPPED']}"
    if n and hi < n * 0.5:
        return False, f"HIGH {hi}/{n} < 50%"
    return True, f"مشحون {n} · HIGH {hi} · {why_r}"


def count_expected(spec):
    out = set()
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-")
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(part))
    return len([x for x in out if 1 <= x <= 114])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reciter", required=True)
    ap.add_argument("--riwaya", required=True)
    ap.add_argument("--expect-surahs", default="1-114")
    ap.add_argument("--log", default="")
    ap.add_argument("--prefix", default=os.environ.get("STAGING_PREFIX", "timings-staging"),
                    help="⛔ تحت `timings-staging/` وحدها — انظر حارس البادئة أدناه")
    a = ap.parse_args()

    # ⛔ حارس البادئة (قرار github-f4، 2026-09-02): **كل كاتبٍ إلى الدلو يحمل
    #    حرّاسه داخله، ولا يكتب إلا في وجهته**. هذا السكربت هو الكاتب الوحيد
    #    إلى `timings-staging/`، و`upload_timings.py` (‏b9) الكاتب الوحيد إلى
    #    `timings/`. فبادئةٌ ثالثة تعني كاتباً بلا حارسٍ يخصّها — وبها يُفتح
    #    الباب من حيث سُدّ. والقيد على `--prefix` **و**`STAGING_PREFIX` معاً.
    root_prefix = (a.prefix or "").strip("/").split("/")[0]
    if root_prefix != "timings-staging":
        print(f"⛔ بادئة ممنوعة: {a.prefix!r} — هذا الكاتب لا يكتب إلا تحت "
              "`timings-staging/`. الكتابة في `timings/` لـ`upload_timings.py` "
              "بحرّاسه، وأي بادئة أخرى كاتبٌ بلا حارس.")
        sys.exit(2)

    # ⛔ التجميد في staging: مَنعٌ مشروط لا مطلق (تصحيح github-f4، 2026-09-02).
    #    كان حارسي يرفض المجمَّد في staging **مطلقاً** — وهو أشدّ مما يجب:
    #    ‏`staging` هو **المسار الوحيد لاستبدال مجمَّد** (رفعٌ موسوم ← حكم ←
    #    رفع تجميدٍ صريح ← ترقية)، فالمنع المطلق يُغلق باب الإصلاح على نفسه.
    #    والشرطان الباقيان يحفظان المقصد الأصلي: **لا مفتاحاً عارياً** (‏`<id>.jz`
    #    يُخلط بالمنشور فيلتبس الحكم — وهو ما حذّر منه b9)، **ولا كتابةً فوق
    #    موجود** (والبصمة في الاسم مشتقّةٌ من المحتوى، فوجود المفتاح يعني
    #    محتوىً مطابقاً؛ والكتابة عليه تمحو شاهداً بلا أن تضيف شيئاً — D-042).
    frozen, why_frozen = frozen_refuse(a.riwaya, a.reciter)
    if frozen and why_frozen.startswith("⛔"):
        print(f"🧊 {why_frozen}")     # تعذّرت قراءة القائمة ⇒ فشلٌ مغلق
        sys.exit(2)

    th = thresholds()
    expect = count_expected(a.expect_surahs)
    ok, why = guard(a.reciter, expect, a.log, th)
    if not ok:
        print(f"🛑 {a.reciter} رُفض الرفع: {why}")
        sys.exit(2)

    idx = os.path.join(ROOT, "tools", "alignment", "work", f"timings_{a.riwaya}_{a.reciter}.jz")
    if not os.path.exists(idx):
        print(f"🛑 {a.reciter}: لا فهرس {idx}")
        sys.exit(2)
    ok2, why2 = shipped_guard(idx, expect, th)
    if not ok2:
        print(f"🛑 {a.reciter} رُفض الرفع (بعد الإسقاط): {why2}")
        sys.exit(2)
    print(f"🔒 حارس الرفع: {why} · {why2}")

    import boto3
    c = json.load(open(os.path.join(ROOT, "secure", "r2_credentials.json")))
    s3 = boto3.client("s3", endpoint_url=c["endpoint"],
                      aws_access_key_id=c["accessKeyId"],
                      aws_secret_access_key=c["secretAccessKey"], region_name="auto")
    # ⛔ البصمة في الاسم (قرار المشرف github-f4، 2026-09-02): المفتاح الثابت
    #    جعل فاحصاً يلتقط نسخةً **أثناء بنائها** فيحكم على ناقص. واللاحقة أول
    #    ثماني خانات من sha256 الملف نفسه ⇒ الاسم يرمّز المحتوى، ومطابقة
    #    اللاحقة بالبصمة فحصٌ مجاني للمستهلك.
    import hashlib
    h = hashlib.sha256()
    with open(idx, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    sha8 = h.hexdigest()[:8]
    # ⛔ الجزئي يُسمّى جزئياً (طلب github-7e، وهو محقّ): عتبتا التغطية وHIGH
    #    مُوقَفتان على التشغيلة الجزئية ⇒ الفهرس يصل المدقّق **بلا حارسٍ أوّلي**،
    #    و«جزئيٌّ» و«ناقصٌ» يبدوان سواءً في عدد المداخل. فالتمييز يُحمل في
    #    **الاسم والميتاداتا** معاً: الاسم يُرى في الجرد بلا تنزيل، والميتاداتا
    #    تُقرأ بـHEAD بلا فكّ ضغط.
    part = "" if expect >= 114 else f".partial{expect}"
    key = f"{a.prefix}/{a.riwaya}/{a.reciter}{part}.{sha8}.jz"
    meta = {"partial": "true" if expect < 114 else "false",
            "surahs": str(expect), "sha256-8": sha8, "source": "github-actions"}
    # ⛔ لا manifest ولا كتابة في timings/: الترقية من staging إلى الإنتاج
    #    قرارُ صاحب الأسطول بعد مقارنته بالمنشور، لا قرارَ عدّاءٍ مجاني.
    # ⛔ شرطا المجمَّد يُطبَّقان هنا، على المفتاح النهائي لا على النية:
    if frozen:
        if ".jz" in key and f"{a.reciter}.jz" in key:
            print(f"🧊 {a.reciter} مجمَّد ⇒ ⛔ لا مفتاح عارٍ في staging "
                  "(يلتبس بالمنشور فيختلط الحكم). المطلوب `<id>.<sha8>.jz`.")
            sys.exit(2)
        try:
            s3.head_object(Bucket=c["bucket"], Key=key)
            print(f"🧊 {a.reciter} مجمَّد و`{key}` موجودٌ سلفاً ⇒ ⛔ لا كتابة فوقه. "
                  "والبصمة مشتقّة من المحتوى، فالموجود مطابقٌ لما كنت سأرفع.")
            sys.exit(2)
        except Exception as ex:               # noqa: BLE001
            if "404" not in str(ex) and "NoSuchKey" not in type(ex).__name__ \
               and "ClientError" not in type(ex).__name__:
                print(f"🧊 تعذّر التحقق من وجود `{key}` ({ex}) ⇒ ⛔ لا رفع لمجمَّد بلا يقين")
                sys.exit(2)
        print(f"🧊 {a.reciter} مجمَّد — يُرفع بمفتاحٍ موسومٍ جديد (مسار الاستبدال المشروع)")

    s3.upload_file(idx, c["bucket"], key,
                   ExtraArgs={"ContentType": "application/gzip", "Metadata": meta})
    print(f"⬆️ رُفع {key} ({os.path.getsize(idx)//1024}ك.ب · "
          f"{'جزئي ' + str(expect) + ' سورة' if expect < 114 else 'كامل 114'})")


if __name__ == "__main__":
    main()
