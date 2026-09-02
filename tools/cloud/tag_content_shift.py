# -*- coding: utf-8 -*-
"""وسم الانزياح المحتوائي في المانيفست — وسمٌ لا محو، وقابل للتراجع.

⛔ لا يحذف ولا يكتب فوق ملف صوتي البتة. عمله كله في `audio/{riwaya}/manifest.json`.

يكتب لكل قارئ منزاح:
  contentShift.pockets[]  — الجيوب المؤكَّدة بمداها وإزاحتها (بنيةٌ لا صدفة)
  contentShift.suspect[]  — المفردات: خبرٌ موسوم بلا قرار
  usableForClips = false  — فالقصاصة تفترض أن الملف يحوي آيته
  usableForFullSurah = false — وضع الآي: الملف **هو** الآية، فانزياحه يُسمع
                               الحافظ آيةً ويقرأ غيرها. لا تشغيل بحال.

    python3 tag_content_shift.py --riwaya warsh --reciter yassin \
        --probe /root/probe_yassin_full.json
"""
import argparse
import json
import os
import sys
import time

import boto3

sys.path.insert(0, "/root/QuranRafiq/tools/alignment")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
B = os.environ["R2_BUCKET"]
s3 = boto3.client("s3", endpoint_url=os.environ["R2_ENDPOINT"],
                  aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
                  aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
                  region_name="auto")


def guard(key):
    if "_quarantine" in key:
        sys.exit("⛔ كتابة ممنوعة تحت مسار محجور: " + key)
    return key


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--riwaya", required=True)
    ap.add_argument("--reciter", required=True)
    ap.add_argument("--pockets", required=True,
                    help="JSON: [{from,to,offset,count,strongest}]")
    ap.add_argument("--suspect", required=True, help="JSON: قائمة س:آ")
    ap.add_argument("--fix-prefix", default=None)
    a = ap.parse_args()

    pockets = json.loads(a.pockets)
    suspect = json.loads(a.suspect)
    mkey = "audio/{}/manifest.json".format(a.riwaya)
    cur = json.loads(s3.get_object(Bucket=B, Key=mkey)["Body"].read())
    hit = None
    for e in cur.get("reciters", []):
        if e["id"] == a.reciter:
            hit = e
    if hit is None:
        sys.exit("⛔ لا مدخل لـ{} في {}".format(a.reciter, mkey))

    hit["contentShift"] = {
        "detectedAt": int(time.time()),
        "method": "probe_content.py — تفريغ ومطابقة نصية بالجيران ±3",
        "verdict": "SHIFTED_POCKETS",
        "pockets": pockets,
        "suspect": suspect,
        "note": ("الملف يحوي آيةً غير التي يحملها اسمه في هذه المواضع. "
                 "لا يكشفه اسم ولا بصمة ولا بوابة عدّ: البصمة تثبت أننا نسخنا "
                 "المصدر بايتاً ببايت لا أن المصدر صادق، وبوابة العدّ الثمانية "
                 "اجتازها هذا المجلد 8/8 لأن ثماني نقاط لا تصادف الجيوب — "
                 "فهي شرط لازم غير كافٍ. والمفردات (suspect) خبرٌ لا حكم: "
                 "إزاحاتها مختلطة ودرجاتها ضعيفة وأكثرها في سور كثيرة التكرار."),
    }
    if a.fix_prefix:
        hit["contentShift"]["fixPrefix"] = a.fix_prefix
    # ⛔ وضع الآي: الملف **هو** الآية. انزياحه يُسمع الحافظ آيةً ويقرأ غيرها
    # صامتاً بلا خطأ ظاهر — فلا تشغيل ولا قصاصة حتى يُبتّ.
    hit["usableForClips"] = False
    hit["usableForFullSurah"] = False
    cur["updated"] = int(time.time())
    s3.put_object(Bucket=B, Key=guard(mkey), ContentType="application/json",
                  Body=json.dumps(cur, ensure_ascii=False, indent=1).encode("utf-8"))
    n = sum(p["count"] for p in pockets)
    print("✅ وُسم {}/{}: {} جيباً ({} آية) · {} مفردة موسومة suspect".format(
        a.riwaya, a.reciter, len(pockets), n, len(suspect)))
    print("   usableForClips=false · usableForFullSurah=false (وضع الآي)")
    print("   ⛔ لم يُحذف ولم يُكتب فوق أي ملف صوتي — الوسم قابل للتراجع.")


if __name__ == "__main__":
    main()
