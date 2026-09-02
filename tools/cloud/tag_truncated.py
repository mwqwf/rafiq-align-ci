# -*- coding: utf-8 -*-
"""وسم السور التي لا توافق مدتُها طولَها عند المصدر — وسمٌ لا محو.

سورةٌ مبتورة تعبر **كل** حُرّاسنا بعلامة نجاح: بصمتها تطابق الفهرس (لأن
الفهرس بُني على البتر نفسه)، و`complete:true` (لأن الملف موجود)، وبوابة
العدّ معطَّلة في وضع السور. فلا يكشفها إلا قياس المدة.

يكتب في مدخل القارئ:
  truncatedAtSource[]  — السور بمدتها الفعلية والمتوقعة ونسبتهما
  perFile[n].clipsOk = false  — للسورة المعيبة **وحدها**
  usableForClips يبقى كما هو — القارئ صالح في بقية سوره، والحرمان بقدره.

    python3 tag_truncated.py --probe /root/probe_surah_durations.json [--apply]
"""
import argparse
import json
import os
import sys
import time

import boto3

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
B = os.environ["R2_BUCKET"]
s3 = boto3.client("s3", endpoint_url=os.environ["R2_ENDPOINT"],
                  aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
                  aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
                  region_name="auto")

# ⛔ لا تُسمَّ الزيادة بتراً: الملف الأطول من سورته علّته غير الأقصر، ومن
# يقرأ «مبتورة» يذهب يبحث عن ذيلٍ ناقص وليس هناك ذيل ناقص. رُصد حياً:
# abkar س75 مدتها 176% من المتوقع — زيادةٌ لا نقص.
NOTE = ("مدة الملف لا توافق طول سورته — عيبٌ عند المصدر لا في "
        "مرآتنا: قِيس حجمُنا مقابل Content-Length من المصدر فتطابقا بايتاً "
        "ببايت. و`timingIndexShaMatch: MATCH` لا ينفي هذا بل يفسّره: الفهرس "
        "بُني على الصوت المعيب نفسه، فالتطابق يشهد باتساق الفهرس والصوت لا "
        "بصحة أيّهما. وكل حارس يجيب عن سؤاله هو.")


def guard(key):
    if "_quarantine" in key:
        sys.exit("⛔ كتابة ممنوعة تحت مسار محجور: " + key)
    return key


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", required=True)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    probe = json.load(open(a.probe, encoding="utf-8"))
    bad = [r for r in probe if r.get("verdict") == "SUSPECT"]
    by_riwaya = {}
    for r in bad:
        by_riwaya.setdefault(r["riwaya"], []).append(r)

    for riwaya, items in by_riwaya.items():
        mkey = "audio/{}/manifest.json".format(riwaya)
        cur = json.loads(s3.get_object(Bucket=B, Key=mkey)["Body"].read())
        touched = 0
        for r in items:
            hit = next((e for e in cur.get("reciters", [])
                        if e["id"] == r["reciter"]), None)
            if hit is None:
                print("⚠️ لا مدخل لـ{}".format(r["reciter"]))
                continue
            rows = []
            for x in r["suspect"]:
                ratio = round(x["durationMs"] / max(x["expectedMs"], 1), 2)
                rows.append({"surah": x["surah"],
                             "kind": ("SHORT_AT_SOURCE" if ratio < 1
                                      else "LONG_AT_SOURCE"),
                             "durationMs": x["durationMs"],
                             "expectedMs": x["expectedMs"],
                             "ratio": ratio})
                for f in hit.get("perFile", []):
                    if f["surah"] == x["surah"]:
                        f["clipsOk"] = False       # العيب بقدره لا أوسع
            hit["durationMismatchAtSource"] = rows
            hit["durationMismatchNote"] = NOTE
            hit.pop("truncatedAtSource", None)   # تسمية أولى غير دقيقة
            hit.pop("truncatedNote", None)
            blocked = set(hit.get("clipsBlockedBySurah") or [])
            blocked.update(x["surah"] for x in r["suspect"])
            hit["clipsBlockedBySurah"] = sorted(blocked)
            hit["clipsOkBySurah"] = [n for n in range(1, 115)
                                     if n not in blocked]
            touched += 1
            print("⛔ {}/{}: سور {} وُسمت".format(
                riwaya, r["reciter"],
                ", ".join(str(x["surah"]) for x in r["suspect"])))
        if touched and a.apply:
            cur["updated"] = int(time.time())
            s3.put_object(Bucket=B, Key=guard(mkey),
                          ContentType="application/json",
                          Body=json.dumps(cur, ensure_ascii=False,
                                          indent=1).encode("utf-8"))
            print("✅ {} — {} قارئاً".format(mkey, touched))
    if not a.apply:
        print("\n(تجربة جافة — أضف --apply للكتابة)")


if __name__ == "__main__":
    main()
