# -*- coding: utf-8 -*-
"""كم من فهارس الليلة أصابه `-ac 512`؟ — تقديرٌ من الفهارس المنشورة نفسها.

الخلفية (‏§٥د من REPORT): ‏`-ac 512` ينصّف سياق المشفّر فيضيع ما بعد ~10ث من
المقطع المفرَّغ. فالسؤال التشغيلي: **كم مقطعاً تجاوز عشر ثوانٍ؟**

⚠️ الفهرس لا يسجّل المقاطع بل حدود الآي، فيُقدَّر المقطع من أثرٍ في الفهرس
نفسه: الحدّ `startApprox` معناه أن بدايته **قُسمت تقديرياً داخل مقطع** لم
يفصله صمت. فكلّ سلسلةٍ من حدٍّ مسنودٍ يتبعه حدودٌ تقديرية = **مقطعٌ واحد**،
ومدّته من بداية أوّله إلى نهاية آخره. تقديرٌ **متحفّظ**: مقطعٌ يحمل آيةً
واحدة يُقاس بمدّة تلك الآية، وهو الحدّ الأدنى لطول المقطع الحقيقي (المقطع
قد يبدأ قبلها بصمت).

    python tools/tasmi_bench/ac_exposure.py [--prefix timings/qalun/]
"""
import argparse
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))
from common import read_jz  # noqa: E402

WORK = os.path.join(HERE, "work", "indexes")


def client():
    import boto3
    c = json.load(open(os.path.join(ROOT, "secure", "r2_credentials.json")))
    return boto3.client("s3", endpoint_url=c["endpoint"], aws_access_key_id=c["accessKeyId"],
                        aws_secret_access_key=c["secretAccessKey"], region_name="auto"), c["bucket"]


def segments(entries):
    """يعيد قائمة مقاطع مقدَّرة: (مدة بالمللي، عدد الآيات فيه، نطاقاتها)."""
    by_file = {}
    for e in entries:
        by_file.setdefault(e["fileRef"], []).append(e)
    out = []
    for _, es in by_file.items():
        es.sort(key=lambda e: e["startMs"])
        cur = []
        for e in es:
            if cur and not e.get("startApprox"):
                out.append(cur)
                cur = []
            cur.append(e)
        if cur:
            out.append(cur)
    return [(g[-1]["endMs"] - g[0]["startMs"], len(g), [x.get("confBand") for x in g])
            for g in out]


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return (max(0.0, c - h) * 100, min(1.0, c + h) * 100)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", default="timings/")
    ap.add_argument("--limit", type=int, default=100)
    args = ap.parse_args()
    s3, bucket = client()
    os.makedirs(WORK, exist_ok=True)
    keys = []
    for pg in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=args.prefix):
        keys += [o["Key"] for o in pg.get("Contents", []) if o["Key"].endswith(".jz")]
    keys = keys[:args.limit]
    print(f"فهارس: {len(keys)}")

    tot = {"ayat": 0, "segs": 0, "segMs": 0}
    over10 = {"segs": 0, "ayat": 0}
    over20 = {"segs": 0, "ayat": 0}
    bands = {"≤10ث": {}, "10–20ث": {}, ">20ث": {}}
    per_reciter = []
    for k in keys:
        p = os.path.join(WORK, k.replace("/", "_"))
        if not os.path.exists(p):
            s3.download_file(bucket, k, p)
        ti = read_jz(p)
        segs = segments(ti["entries"])
        a10 = a20 = 0
        for ms, n, bs in segs:
            tot["segs"] += 1; tot["ayat"] += n; tot["segMs"] += ms
            b = "≤10ث" if ms <= 10_000 else ("10–20ث" if ms <= 20_000 else ">20ث")
            for x in bs:
                bands[b][x or "?"] = bands[b].get(x or "?", 0) + 1
            if ms > 10_000:
                over10["segs"] += 1; over10["ayat"] += n; a10 += n
            if ms > 20_000:
                over20["segs"] += 1; over20["ayat"] += n; a20 += n
        per_reciter.append((k.split("/")[-1][:-3], len(ti["entries"]),
                            a10 / max(1, len(ti["entries"])) * 100))

    print(f"\nالمجموع: {tot['ayat']} آية في {tot['segs']} مقطعاً مقدَّراً "
          f"(وسطي المقطع {tot['segMs']/max(1,tot['segs'])/1000:.1f}ث)")
    for name, d in (("مقاطع >10ث", over10), ("مقاطع >20ث", over20)):
        lo, hi = wilson(d["ayat"], tot["ayat"])
        print(f"  {name}: {d['segs']} مقطعاً · **{d['ayat']} آية = "
              f"{d['ayat']/tot['ayat']*100:.1f}%** من الفهرس [{lo:.1f}–{hi:.1f}]")
    print("\n  النطاقات حسب طول المقطع:")
    for b, d in bands.items():
        t = sum(d.values()) or 1
        print(f"   {b:7s} " + " · ".join(f"{k} {v} ({v/t*100:.0f}%)"
                                         for k, v in sorted(d.items())))
    per_reciter.sort(key=lambda x: -x[2])
    print("\n  أكثر القرّاء تعرّضاً (نسبة آياته داخل مقاطع >10ث):")
    for n, c, pct in per_reciter[:8]:
        print(f"   {n:26s} {pct:5.1f}%  ({c} آية)")
    print("\n  وأقلّهم:")
    for n, c, pct in per_reciter[-3:]:
        print(f"   {n:26s} {pct:5.1f}%  ({c} آية)")


if __name__ == "__main__":
    main()
