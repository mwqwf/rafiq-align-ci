# -*- coding: utf-8 -*-
"""نسخ ملفات الجيوب بأسمائها الصحيحة إلى **مسار جديد** — بلا مساس بالأصل.

⛔ لماذا مسار جديد لا إعادة تسمية في مكانها: الاسم «الصحيح» **مشغولٌ بملف
   آخر منزاح**، فالنسخ إليه كتابةٌ فوق أصل — أي محوٌ في ثوب إصلاح. والمحو
   ممنوع مطلقاً. فيُكتب الإصلاح في `fixPrefix` والأصل يبقى شاهداً كما هو.

المنطق: بلاغٌ يقول «الملف المسمّى A محتواه الآية B» ⇒ ننسخ بايتات ملف A إلى
اسم B تحت المسار الجديد. فمن أراد B وجده صحيحاً، والأصل لم يُمَس.

⛔ حارسان لا يُتجاوزان:
   ١. لا كتابة إلا تحت `fixPrefix` — وأي مفتاح خارجه يُرفض.
   ٢. لا كتابة فوق مفتاح موجود تحت `fixPrefix` نفسه (تصادم بلاغين).

    python3 fix_shift_copy.py --riwaya warsh --reciter yassin \
        --probe /root/probe_yassin_full.json \
        --pockets '12:102-12:111,4:12-4:14,27:36-27:38' \
        --prefix audio/yassin_warsh/fix1/ [--apply]
"""
import argparse
import hashlib
import json
import os
import sys

import boto3

sys.path.insert(0, "/root/QuranRafiq/tools/alignment")
from common import load_index  # noqa

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
B = os.environ["R2_BUCKET"]
s3 = boto3.client("s3", endpoint_url=os.environ["R2_ENDPOINT"],
                  aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
                  aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
                  region_name="auto")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--riwaya", required=True)
    ap.add_argument("--reciter", required=True)
    ap.add_argument("--probe", required=True)
    ap.add_argument("--pockets", required=True)
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--only", default=None,
                    help="قائمة س:آ — لا يُنسخ إلا ما أكّده الشاهدان معاً")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    if "_quarantine" in a.prefix:
        sys.exit("⛔ الكتابة تحت مسار محجور ممنوعة.")
    if not a.prefix.endswith("/"):
        sys.exit("⛔ المسار الجديد يجب أن ينتهي بشرطة مائلة.")

    index = load_index()
    slots = []
    for s in index["surahs"]:
        for i in range(s["ayahs"]):
            slots.append((s["n"], i + 1))
    pos = {"{}:{}".format(sn, an): i for i, (sn, an) in enumerate(slots)}

    ranges = []
    for tok in a.pockets.split(","):
        lo, hi = tok.strip().split("-")
        ranges.append((pos[lo], pos[hi]))

    probe = json.load(open(a.probe, encoding="utf-8"))
    rows = [r for r in probe["results"] if r.get("verdict") == "SHIFTED"
            and any(lo <= r["slot"] <= hi for lo, hi in ranges)]
    if a.only:
        # ⛔ لا يُنسخ إلا ما شهد له الشاهدان المستقلان معاً (التفريغ + المدة).
        # ما اختلفا فيه يبقى معلَّقاً: شاهدٌ واحد لا يكفي لإنشاء ملفٍ يُتلى.
        keep = {x.strip() for x in a.only.split(",")}
        before = len(rows)
        rows = [r for r in rows if r["ayah"] in keep]
        print("قُصر النسخ على المؤكَّد بشاهدين: {} من {}".format(
            len(rows), before))
    rows.sort(key=lambda r: r["slot"])
    print("جيوب: {} · ملفات ستُنسخ: {}".format(len(ranges), len(rows)))

    src_pref = "audio/{}/{}/".format(a.riwaya, a.reciter)
    plan, skipped = [], []
    for r in rows:
        i, off = r["slot"], r["bestOffset"]
        j = i + off
        if not (0 <= j < len(slots)):
            skipped.append((r["ayah"], "الجار خارج المصحف"))
            continue
        ssn, san = slots[i]
        tsn, tan = slots[j]
        # ⛔ المصدر والهدف يجب أن يكونا في السورة نفسها — وإلا فالبلاغ عابرُ
        # حدود سورة ولا يصلح لإعادة تسمية آلية (يحتاج بتّاً بشرياً).
        if ssn != tsn:
            skipped.append((r["ayah"], "يعبر حدّ سورة → {}:{}".format(tsn, tan)))
            continue
        plan.append({
            "src": src_pref + "{:03d}{:03d}.mp3".format(ssn, san),
            "dst": a.prefix + "{:03d}{:03d}.mp3".format(tsn, tan),
            "servesAyah": "{}:{}".format(tsn, tan),
            "fromFileNamed": "{}:{}".format(ssn, san),
            "offset": off, "score": r["bestScore"],
        })

    dsts = [p["dst"] for p in plan]
    if len(set(dsts)) != len(dsts):
        sys.exit("⛔ تصادم: هدفان بالاسم نفسه — أوقف وراجع البلاغات.")

    have = set()
    tok = None
    while True:
        kw = dict(Bucket=B, Prefix=a.prefix, MaxKeys=1000)
        if tok:
            kw["ContinuationToken"] = tok
        r = s3.list_objects_v2(**kw)
        for o in r.get("Contents", []):
            have.add(o["Key"])
        if not r.get("IsTruncated"):
            break
        tok = r["NextContinuationToken"]

    for p in plan:
        mark = "⛔ موجود سلفاً" if p["dst"] in have else "→"
        print("  {} {}  {}  (يخدم {} · إزاحة {:+d} · درجة {})".format(
            mark, p["src"].split("/")[-1], p["dst"].split("/")[-1],
            p["servesAyah"], p["offset"], p["score"]))
    for ayah, why in skipped:
        print("  ⏭ {} — {}".format(ayah, why))

    if not a.apply:
        print("\n(تجربة جافة — أضف --apply للتنفيذ)")
        return

    done = []
    for p in plan:
        if p["dst"] in have:
            print("⛔ تخطٍّ: {} موجود — لا كتابة فوق شيء.".format(p["dst"]))
            continue
        body = s3.get_object(Bucket=B, Key=p["src"])["Body"].read()
        s3.put_object(Bucket=B, Key=p["dst"], Body=body,
                      ContentType="audio/mpeg")
        p["bytes"] = len(body)
        p["sha256"] = hashlib.sha256(body).hexdigest()
        done.append(p)
        print("✅ {} ← {} ({} بايت)".format(p["dst"], p["src"], len(body)))

    manifest = {"reciter": a.reciter, "riwaya": a.riwaya, "prefix": a.prefix,
                "note": ("نسخٌ بايتيّ من ملفات منزاحة إلى أسمائها الصحيحة. "
                         "الأصل لم يُمَس ولم يُحذف منه شيء."),
                "files": done, "skipped": skipped}
    s3.put_object(Bucket=B, Key=a.prefix + "manifest.json",
                  ContentType="application/json",
                  Body=json.dumps(manifest, ensure_ascii=False,
                                  indent=1).encode("utf-8"))
    print("\n✅ {} ملفاً نُسخ · {} تُخطّي · مانيفست الإصلاح: {}manifest.json".format(
        len(done), len(skipped), a.prefix))


if __name__ == "__main__":
    main()
