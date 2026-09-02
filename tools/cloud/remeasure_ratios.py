# -*- coding: utf-8 -*-
"""إعادة قياس نسب المدة **بلا تنزيل ولا خادم** — فتُرفع `ratiosPendingRemeasure`.

⛔ المشكلة: نسب `catalog/diagnosis/` حُسبت بمقامٍ منفوخ، وتصحيحها كان
   موقوفاً على `ffprobe` — أي على قرصٍ يُنزَّل عليه 114 ملفاً لكل قارئ، وقد
   سقط الخادم. **فبقيت النسب خاطئةً موسومةً بخطئها، وذلك أفضل ما أمكن.**

**والحلّ من rafiq-tafsir:** المدّة تُقاس من **ترويسة أول إطار MP3** لا من
فكّ الملف — طلبُ `Range` صغير يكفي. فصار التصحيح ممكناً من أي مكان.

⛔ ولا أُعيد كتابة محلّله: `parse_bitrate` عنده محصَّن بـ**ثلاثة إطاراتٍ
   متّصلة** بعد أن أعطى التطابقُ الكاذب الفرقانَ 8048ث والحقّ 1337ث.
   **خذ المودَعة لا فكرتَها** — وهو نصُّه، وأعمل به.

والمقام المصحَّح: الوتيرة من السور ≥300 كلمة (حيث الثابت مهمَل) ثم يُشتقّ
الثابت منها — لا وسيط السور كلها (فأكثرها قصيرة والثابت يسحقها).

    python3 remeasure_ratios.py --validate       # مقابل قيمٍ معلومة أولاً
    python3 remeasure_ratios.py --apply
"""
import argparse
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import boto3

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools", "qa_coverage"))
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))
import pace_probe as pp                                   # noqa: E402
from common import load_index, load_text, norm            # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
LOCK = threading.Lock()
_t = threading.local()
HEAD_BYTES = 262144        # يتجاوز وسم ID3 الكبير (صور الغلاف تبلغ 100ك.ب)
BIG_WORDS = 300


def client():
    p = os.environ.get("R2_CREDENTIALS",
                       os.path.join(ROOT, "secure", "r2_credentials.json"))
    c = json.load(open(p, encoding="utf-8"))
    return boto3.client("s3", endpoint_url=c["endpoint"],
                        aws_access_key_id=c["accessKeyId"],
                        aws_secret_access_key=c["secretAccessKey"],
                        region_name="auto"), c["bucket"]


def s3t(bucket):
    if not hasattr(_t, "c"):
        _t.c, _ = client()
    return _t.c


def duration_ms(bucket, key, attempts=3):
    """المدّة من الحجم ومعدّل البتّ — طلبٌ واحد صغير، بلا تنزيل.

    ⛔ بإعادة محاولة: عملٌ على 4674 كائناً تكفيه **مهلةُ قراءةٍ واحدة**
    عابرة ليسقط كله — وقد سقط فعلاً بعد عشرين ملفاً. والانقطاع العابر ليس
    خطأً في البيانات، فلا يُعامَل معاملته.
    """
    for i in range(attempts):
        try:
            r = s3t(bucket).get_object(
                Bucket=bucket, Key=key,
                Range="bytes=0-{}".format(HEAD_BYTES - 1))
            head = r["Body"].read()
            total = int(r["ContentRange"].split("/")[-1])
            br, _sr = pp.parse_bitrate(head)
            if not br:
                return None
            return int(total * 8 / br * 1000)
        except Exception:
            if i == attempts - 1:
                return None
            time.sleep(2 * (i + 1))
    return None


_wcache = {}


def words_of(riwaya):
    if riwaya not in _wcache:
        text, index = load_text(riwaya), load_index()
        _wcache[riwaya] = {
            s["n"]: sum(len(norm(text[s["start"] + i]).split())
                        for i in range(s["ayahs"]))
            for s in index["surahs"]}
    return _wcache[riwaya]


def measure(bucket, riwaya, rid, threads):
    words = words_of(riwaya)
    pref = "audio/{}/{}/".format(riwaya, rid)
    dur = {}

    def one(n):
        ms = duration_ms(bucket, pref + "{:03d}.mp3".format(n))
        if ms:
            with LOCK:
                dur[n] = ms

    with ThreadPoolExecutor(threads) as ex:
        list(ex.map(one, range(1, 115)))
    if len(dur) < 60:
        return None, None, dur

    def med(v):
        v = sorted(v)
        return v[len(v) // 2] if v else 0.0
    big = [dur[n] / words[n] for n in dur if words[n] >= BIG_WORDS]
    if len(big) < 8:
        big = [dur[n] / words[n] for n in dur if words[n] > 0]
    rate = med(big)
    c = max(med([dur[n] - rate * words[n] for n in dur]), 0.0)
    return rate, c, dur


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--threads", type=int, default=12)
    a = ap.parse_args()
    s3, bucket = client()

    if a.validate:
        # ⛔ لا يُبنى على مقياسٍ لم يُقابَل بقيمةٍ معلومة: هذه قِيست بـffprobe
        known = [("qalun", "akri_qalun", 24, 765.8),
                 ("qalun", "akri_qalun", 25, 1337.2),
                 ("qalun", "akri_qalun", 2, 8563.1),
                 ("douri", "husary_douri", 25, 1076.0)]
        print("| الملف | ffprobe | المسبار | الفارق |")
        print("|---|---:|---:|---:|")
        for riw, rid, sn, exp in known:
            ms = duration_ms(bucket,
                             "audio/{}/{}/{:03d}.mp3".format(riw, rid, sn))
            got = (ms or 0) / 1000
            print("| {}/{} س{} | {:.1f}ث | {:.1f}ث | **{:+.2f}%** |".format(
                riw, rid, sn, exp, got, 100 * (got - exp) / exp))
        return

    keys = []
    for pg in s3.get_paginator("list_objects_v2").paginate(
            Bucket=bucket, Prefix="catalog/diagnosis/"):
        keys += [o["Key"] for o in pg.get("Contents", [])]
    print("ملفات التشخيص: {}".format(len(keys)))
    fixed = 0
    for k in sorted(keys):
        try:
            d = json.loads(s3.get_object(Bucket=bucket, Key=k)["Body"].read())
        except Exception as e:
            print("  ⚠️ {}: {}".format(k, str(e)[:60]))
            continue
        riwaya, rid = d["riwaya"], d["reciter"]
        if d.get("ratiosRemeasuredAt") and not d.get("ratiosPendingRemeasure"):
            continue                      # أُنجز في نوبةٍ سابقة — استئنافٌ لا إعادة
        rate, c, dur = measure(bucket, riwaya, rid, a.threads)
        if not rate:
            print("  ⚠️ {}/{}: قياسات أقل من أن يُبنى عليها".format(riwaya, rid))
            continue
        words = words_of(riwaya)
        changed = 0
        for w in d.get("weakSurahs", []):
            n = w["surah"]
            if n not in dur or words.get(n, 0) < 30:
                continue
            new = round(dur[n] / (c + rate * words[n]), 2)
            if new != w.get("durationRatio"):
                w["durationRatioOld"] = w.get("durationRatio")
                w["durationRatio"] = new
                changed += 1
        d["msPerWord"] = round(rate)
        d["overheadMs"] = round(c)
        d["ratiosPendingRemeasure"] = False
        d["ratiosRemeasuredAt"] = int(time.time())
        d["ratiosMethod"] = ("مدّة من ترويسة أول إطار MP3 عبر Range (بلا "
                             "تنزيل) · مقامٌ من السور ≥300 كلمة ثم ثابتٌ "
                             "مشتقّ منها")
        print("  {}/{}: وتيرة {:.0f} · ثابت {:.0f}ث · {} نسبة صُحّحت".format(
            riwaya, rid, rate, c / 1000, changed))
        if a.apply:
            if "_quarantine" in k:
                sys.exit("⛔ كتابة ممنوعة تحت مسار محجور: " + k)
            s3.put_object(Bucket=bucket, Key=k, ContentType="application/json",
                          Body=json.dumps(d, ensure_ascii=False,
                                          indent=1).encode("utf-8"))
        fixed += 1
    print("\n{} ملفاً {}".format(fixed, "خُتم" if a.apply else "(تجربة جافة)"))


if __name__ == "__main__":
    main()
