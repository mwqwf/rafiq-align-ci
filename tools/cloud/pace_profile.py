# -*- coding: utf-8 -*-
"""أهو نقصٌ أم تسريع؟ — بملف الوتيرة داخل السورة، من الفهرس وحده.

⛔ العلّة التي يسدّها (كشفها rafiq-tafsir): **نسبة المدة تكشف الشذوذ ولا
   تسمّي سببه.** فملفٌ أقصر مما يحتمل نصّه قد يكون مبتوراً وقد يكون تلاوةً
   أسرع — وعلاجاهما متضادّان: الأول يُوسم ويُستثنى من الإعادة، والثاني
   **لا عيب فيه أصلاً** ووسمُه ظلمٌ لتسجيلٍ سليم.

الفارز: **انتظام الوتيرة عبر السورة**.
  · منتظمٌ في الأرباع الأربعة  ⇒ الملف كله أسرع ⇒ `PACE_ANOMALY` (يُذكر ولا يُدان)
  · كسرٌ حادّ بعد موضع        ⇒ مادةٌ ضائعة   ⇒ `AUDIO_SHORT` (يُوسم)

قِيس على حالتين معلومتين:
  `husary_douri` س25 → 74·78·74·75 (مدى 4 نقاط)  ⇒ تسريع
  `akri_qalun`   س24 → 84·27·34·40 (مدى 57 نقطة) ⇒ نقص

⛔ وحدُّه معلن: يحتاج **مرجعاً** من سورٍ كبيرة مكتملة في الفهرس نفسه. فقارئٌ
   يعمّ الخلل سوره كلها لا مرجع له — ولا يُحكم فيه بهذا الفارز (‏`3siri`).
   ولا يعمل على سورةٍ مداخلها قليلة (‏مدخلة واحدة لا تُقسَم أرباعاً).

⛔ لا يقرأ صوتاً ولا يكتب في التخزين — الفهرس والنصّ فقط.

    python3 pace_profile.py --riwaya qalun --reciter akri_qalun --surah 24
"""
import argparse
import collections
import gzip
import json
import os
import sys

import boto3

sys.path.insert(0, os.environ.get("RAFIQ_TOOLS", "tools/alignment"))
from common import load_index, load_text, norm  # noqa

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SPREAD_UNIFORM = 15   # مدى الأرباع دونه ⇒ منتظم ⇒ تسريع لا نقص
MIN_ENTRIES = 12      # أقلّ من ذلك لا يُقسَم أرباعاً
# ⛔ حدُّ اللسان — شاهدٌ **لا يحتاج مرجعاً من القارئ ولا من الفهرس**
# (‏من rafiq-tafsir): أسرعُ تلاوةٍ قِيست في الأسطول كله 988 م.ث/كلمة
# (‏a_majed) وأبطؤها 1863 (‏husary_warsh). فنسبةٌ دون هذا الحدّ تعني وتيرةً
# **خارج ما يطيقه لسانٌ**، وتستبعد التسريع الرقمي أيضاً لا البطء وحده:
# ملفٌ سُرِّع أربعة أضعاف لا يبقى مفهوماً. ⇒ بترٌ يقيناً بلا أرباع.
# شاهده الحيّ: `3siri` س9 عند 248 م.ث/كلمة — أربع كلماتٍ في الثانية
# متّصلةً إحدى عشرة دقيقة، أي أسرع بأربعة أضعافٍ من أسرع الأسطول.
HUMAN_FLOOR = 0.35    # نسبةٌ دونه ⇒ خارج المدى البشري ⇒ بتر


def client():
    p = os.environ.get("R2_CREDENTIALS", "secure/r2_credentials.json")
    c = json.load(open(p, encoding="utf-8"))
    return boto3.client("s3", endpoint_url=c["endpoint"],
                        aws_access_key_id=c["accessKeyId"],
                        aws_secret_access_key=c["secretAccessKey"],
                        region_name="auto"), c["bucket"]


def below_human_floor(ratio):
    """أخارج المدى البشري هو؟ — حكمٌ بلا مرجعٍ ولا أرباع.

    يعمل حيث يعجز كل ما عداه: لا يحتاج سورةً سليمة يُقاس عليها، ولا مداخل
    تكفي للأرباع. ومن ثمّ فهو الجواب على السور القصيرة قليلة المداخل.
    """
    return ratio is not None and ratio < HUMAN_FLOOR


def profile(s3, bucket, riwaya, rid, sn, ratio=None):
    d = json.loads(gzip.decompress(s3.get_object(
        Bucket=bucket, Key="timings/{}/{}.jz".format(riwaya, rid))
        ["Body"].read()))
    text, index = load_text(riwaya), load_index()
    st = {s["n"]: (s["start"], s["ayahs"]) for s in index["surahs"]}
    words = {s["n"]: sum(len(norm(text[s["start"] + i]).split())
                         for i in range(s["ayahs"])) for s in index["surahs"]}
    per = collections.defaultdict(list)
    for e in d["entries"]:
        a, b = e["ayahId"].split(":")
        per[int(a)].append((int(b), e["startMs"], e["endMs"]))

    # ⛔ المرجع يحتاج فهرساً **ممتدّاً** لا **كاملاً** — كشفه rafiq-tafsir.
    # فالوتيرة تُحسب على الآي المُسنَدة وحدها (مدّتها ÷ كلماتها)، فلا يضرّها
    # نقصُ غيرها. واشتراطي الاكتمال (‏≥90%) كان يحرمني المرجع عند كل قارئ
    # منخفض التغطية — أي عند **أحوج الحالات إلى الحكم**، فيقول الفارز
    # «لا أدري» وهو قادر. والمطلوب عددٌ يكفي للتمثيل لا اكتمالٌ يمنع.
    REF_MIN_ENTRIES = 15
    ref = []
    for m, rows in per.items():
        if words[m] < 800 or len(rows) < REF_MIN_ENTRIES:
            continue
        tot = sum(y - x for _, x, y in rows)
        w = sum(len(norm(text[st[m][0] + i - 1]).split()) for i, _, _ in rows)
        if w:
            ref.append(tot / w)
    if not ref:
        if below_human_floor(ratio):
            return {"verdict": "AUDIO_SHORT", "ratio": ratio,
                    "why": ("نسبةٌ دون حدّ اللسان — بترٌ بلا حاجةٍ إلى "
                            "مرجعٍ من القارئ")}
        return {"verdict": "NO_REFERENCE",
                "why": "لا سورة كبيرة ممتدّة في هذا الفهرس يُقاس عليها"}
    ref.sort()
    mref = ref[len(ref) // 2]
    rows = sorted(per[sn])
    if len(rows) < MIN_ENTRIES:
        if below_human_floor(ratio):
            return {"verdict": "AUDIO_SHORT", "entries": len(rows),
                    "refMsPerWord": round(mref), "ratio": ratio,
                    "why": ("نسبةٌ دون حدّ اللسان (‏{}) ⇒ وتيرةٌ خارج ما "
                            "يطيقه لسان — بترٌ بلا حاجةٍ إلى أرباع"
                            .format(HUMAN_FLOOR))}
        return {"verdict": "TOO_FEW", "entries": len(rows), "refMsPerWord":
                round(mref), "why": "مداخل أقلّ من أن تُقسَم أرباعاً"}
    q, quarters = len(rows) // 4, []
    for k in range(4):
        seg = rows[k * q:(k + 1) * q] if k < 3 else rows[3 * q:]
        tot = sum(y - x for _, x, y in seg)
        w = sum(len(norm(text[st[sn][0] + i - 1]).split()) for i, _, _ in seg)
        quarters.append(round(100 * (tot / w) / mref) if w else None)
    vals = [x for x in quarters if x is not None]
    spread = max(vals) - min(vals)
    # ⛔ لا تُسمَّ الزيادة نقصاً — وقد وقعتُ في هذا مرتين في ليلة. الفارز
    # يكشف **اضطراب** الوتيرة لا اتجاهه، فسورةٌ نسبتها 1.76 وأرباعها
    # مضطربة عيبُها **زيادةٌ في موضع** لا بترٌ؛ ومن يقرأ «مبتورة» يذهب
    # يبحث عن ذيلٍ ناقص وليس هناك. (‏abkar س75 · 3siri س78.)
    if spread <= SPREAD_UNIFORM:
        v = "PACE_ANOMALY"
    elif ratio is not None and ratio > 1.0:
        v = "AUDIO_IRREGULAR_LONG"
    else:
        v = "AUDIO_SHORT"
    return {"verdict": v,
            "quarters": quarters, "spreadPoints": spread,
            "refMsPerWord": round(mref), "entries": len(rows),
            "ayahs": st[sn][1],
            "why": ("انتظامٌ عبر السورة ⇒ الملف كله أسرع، لا مادة ضائعة"
                    if spread <= SPREAD_UNIFORM else
                    "كسرٌ حادّ بين الأرباع ⇒ مادةٌ ضائعة لا تسريع")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--riwaya", required=True)
    ap.add_argument("--reciter", required=True)
    ap.add_argument("--surah", type=int, required=True)
    ap.add_argument("--ratio", type=float, default=None,
                    help="نسبة المدة إن عُرفت — تُفعّل حدّ اللسان")
    a = ap.parse_args()
    s3, b = client()
    r = profile(s3, b, a.riwaya, a.reciter, a.surah, a.ratio)
    print("{}/{} س{}: {}".format(a.riwaya, a.reciter, a.surah,
                                 json.dumps(r, ensure_ascii=False)))


if __name__ == "__main__":
    main()
