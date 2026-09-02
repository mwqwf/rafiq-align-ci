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
    try:
        with open(FROZEN_LIST, encoding="utf-8") as f:
            for line in f:
                line = line.split("#", 1)[0].strip()
                if line and line.split()[0] == key:
                    return True, f"{rid} مجمَّد في frozen.txt"
    except FileNotFoundError:
        # ⛔ الغياب **يرفض ولا يمرّ** (تنبيه github-82 عبر b9): «الحارس الذي
        #    يمرّ عند غياب قائمته يتحول إلى لا شيء يوم يُنسى الملف». والغياب
        #    في Actions أرجح منه على خادمٍ دائم لأن كل عدّاء يبدأ من صفر.
        return True, f"⛔ {FROZEN_LIST} غائب — الحارس بلا قائمة لا يحرس"
    return False, ""


def guard(rid, expect, log_path, th):
    """نفس شروط `index_ok`/`shipped_ok`، مقيسةً على نطاق السور المطلوب فعلاً."""
    d = os.path.join(ROOT, "tools", "alignment", "work", f"batch_{rid}")
    fs = glob.glob(os.path.join(d, "s*.json"))
    if len(fs) < expect:
        return False, f"سور {len(fs)}/{expect}"
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


def shipped_guard(idx, expect, th):
    d = json.load(gzip.open(idx, "rt", encoding="utf-8"))
    n = len(d.get("entries", []))
    hi = sum(1 for e in d["entries"] if e.get("confBand") == "HIGH")
    if expect < 114:
        # ⛔ عتبتا التغطية ونسبة HIGH معايرتان على **فهرس قارئ كامل**. تطبيقهما
        #    على تشغيلة اختبار من سورة واحدة رفضٌ كاذب: وقع فعلاً في smoke
        #    33581796764 — سورة 108 ثلاث آيات كلها MED ⇒ «HIGH 0/3 < 50%»،
        #    فبدت السلسلة فاشلة وهي سليمة حتى الرفع. تُقاس ولا تحجب هنا.
        return True, f"مشحون {n} · HIGH {hi} (تشغيلة جزئية: العتبتان لا تنطبقان)"
    if n < th["MIN_SHIPPED"]:
        return False, f"تغطية {n}/6236 < {th['MIN_SHIPPED']}"
    if n and hi < n * 0.5:
        return False, f"HIGH {hi}/{n} < 50%"
    return True, f"مشحون {n} · HIGH {hi}"


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
    ap.add_argument("--prefix", default=os.environ.get("STAGING_PREFIX", "timings-staging"))
    a = ap.parse_args()

    refuse, why_frozen = frozen_refuse(a.riwaya, a.reciter)
    if refuse:
        print(f"🧊 D-058: {why_frozen} — ⛔ لا رفع ولو إلى staging")
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
    s3.upload_file(idx, c["bucket"], key,
                   ExtraArgs={"ContentType": "application/gzip", "Metadata": meta})
    print(f"⬆️ رُفع {key} ({os.path.getsize(idx)//1024}ك.ب · "
          f"{'جزئي ' + str(expect) + ' سورة' if expect < 114 else 'كامل 114'})")


if __name__ == "__main__":
    main()
