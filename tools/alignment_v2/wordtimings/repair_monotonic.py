# -*- coding: utf-8 -*-
"""إصلاح بيانات بحت: فرض رتابة نقاط القطع على مخرج وُلِّد قبل الإصلاح البنيوي.

نفس التطبيع الذي يطبّقه `generate.py` الآن (نقاط قطع غير متناقصة محصورة في مدى
الآية) مطبَّقاً على مخرج قائم — بلا صوت ولا whisper ولا إعادة محاذاة، فالنتيجة
مطابقة لما كان سيُنتجه المولّد المصلَح حرفياً.

python repair_monotonic.py --index <idx.jz> --file <wordtimings.jz> [--apply]
"""
import argparse, os, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "alignment"))
from common import read_jz, write_jz  # noqa: E402

MIN_WORD_MS = 60


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--file", required=True)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    doc = read_jz(a.file)
    span = {e["ayahId"]: (e["startMs"], e["endMs"])
            for e in read_jz(a.index)["entries"]}
    fixed = 0
    for e in doc["entries"]:
        s0, e0 = span[e["ayahId"]]
        w = e["words"]
        # ⚠️ لا تُرجع الكلمة الأولى إلى حدّ الآية: بدايتها بدء الكلام المقيس،
        #    وتغييرها يُدخل الصمت الابتدائي ويهدم معايرة الـ180م.ث.
        cuts = [max(s0, min(int(w[0]["startMs"]), e0))] +                [x["startMs"] for x in w[1:]] + [e0]
        for j in range(1, len(cuts)):
            cuts[j] = max(cuts[j - 1], min(int(cuts[j]), e0))
        changed = False
        for j, x in enumerate(w):
            if x["startMs"] != cuts[j] or x["endMs"] != cuts[j + 1]:
                changed = True
            x["startMs"], x["endMs"] = cuts[j], cuts[j + 1]
        fixed += changed
    bad = sum(1 for e in doc["entries"] for x in e["words"]
              if x["startMs"] > x["endMs"])
    nonmono = sum(1 for e in doc["entries"]
                  for i in range(len(e["words"]) - 1)
                  if e["words"][i]["endMs"] > e["words"][i + 1]["startMs"])
    zero = sum(1 for e in doc["entries"] for x in e["words"]
               if x["endMs"] <= x["startMs"])
    print("آيات تغيّرت: %d من %d" % (fixed, len(doc["entries"])))
    print("بعد الإصلاح — مقلوب: %d · متداخل: %d · صفري الطول: %d"
          % (bad, nonmono, zero))
    if a.apply and bad == 0 and nonmono == 0:
        write_jz(a.file, doc)
        print("✅ كُتب %s" % a.file)
    elif a.apply:
        print("⛔ لم يُكتب — سند المنع: مقلوب=%d متداخل=%d" % (bad, nonmono))


if __name__ == "__main__":
    main()
