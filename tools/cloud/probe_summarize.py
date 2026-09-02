# -*- coding: utf-8 -*-
"""تلخيص مخرج مسبار المحتوى: الانزياحات المتفرقة تُجمَع في **جيوب** بحدودها.

الانزياح المفرد خبرٌ، والجيب حكمٌ: مدى متصل بإزاحة واحدة يدلّ على اختلاف عدّ
لا على عطب نسخ عشوائي — وهو وحده القابل للتصحيح بإعادة التسمية.

    python3 probe_summarize.py /root/probe_yassin_full.json
"""
import difflib
import json
import os
import sys
from collections import Counter

sys.path.insert(0, "/root/QuranRafiq/tools/alignment")
try:
    from common import load_index, load_text, norm
except Exception:
    load_text = None

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

d = json.load(open(sys.argv[1], encoding="utf-8"))
print("=== {}/{} ===".format(d["riwaya"], d["reciter"]))
print("فُحص {} · مطابق {} · منزاح {} · غير حاسم {} · قصيرة لا تُحاكَم {} · "
      "أخطاء {}".format(d["checked"], d["matched"], d["shifted"],
                        d.get("unclear", 0), d.get("unjudgedShort", 0),
                        d["errors"]))
res = d["results"]
sh = sorted([r for r in res if r.get("verdict") == "SHIFTED"],
            key=lambda r: r["slot"])

# ⛔ حارس التشابه الداخلي: القرآن يكرّر نفسه، والمسبار لا يعرف ذلك.
# ‏94:5 «فإن مع العسر يسرا» و94:6 «إن مع العسر يسرا» — وآلاء الرحمن تتكرر
# إحدى وثلاثين مرة. فتطابق الجار درجةً كاملة ليس دليل انزياح بل دليل أن
# الآيتين لا تتمايزان أصلاً. واتهام قارئ بهذا ظلمٌ بيّن، فيُنزَّل إلى «غير
# حاسم». والجيوب لا يمسّها هذا: تواتُر مدى متصل بإزاحة واحدة بنيةٌ لا تشابه.
AMBIG = 0.6
ambiguous = []
if load_text is not None:
    text = load_text(d["riwaya"])
    keep = []
    for r in sh:
        i, off = r["slot"], r["bestOffset"]
        j = i + off
        if 0 <= j < len(text):
            a, b = norm(text[i]).split(), norm(text[j]).split()
            m = difflib.SequenceMatcher(None, a, b)
            # الاحتواء يجري في الاتجاهين: «القارعة» (‏101:1) داخلةٌ كلها في
            # «وما أدراك ما القارعة» (‏101:3)، فالقسمة على الأطول تخفيها.
            # فيُقسَم على الأقصر — أي: هل ابتلع أحدُهما الآخر؟
            sim = sum(x.size for x in m.get_matching_blocks()) / max(
                min(len(a), len(b)), 1)
            if sim >= AMBIG:
                r["ambiguousWith"] = round(sim, 2)
                ambiguous.append(r)
                continue
        keep.append(r)
    if ambiguous:
        print("\n⚠️ أُسقط {} بلاغاً: نصّ الآية وجارِها متشابهان أصلاً فلا "
              "يتمايزان — تشابهٌ لا انزياح.".format(len(ambiguous)))
        for r in ambiguous:
            print("   {} ~ {} (تشابه نصي {})".format(
                r["ayah"], r.get("heardAyah"), r["ambiguousWith"]))
    sh = keep
    if not sh:
        print("\n✅ لم يبق بلاغ بعد إسقاط المتشابهات.")
        sys.exit(0)
if not sh:
    print("✅ لا انزياح مؤكَّد.")
    sys.exit(0)

print("توزيع الإزاحات: {}".format(dict(Counter(r["bestOffset"] for r in sh))))
print("\n=== الجيوب (مدى متصل بإزاحة واحدة) ===")
runs = []
for r in sh:
    if (runs and r["slot"] - runs[-1][-1]["slot"] <= 3
            and r["bestOffset"] == runs[-1][-1]["bestOffset"]):
        runs[-1].append(r)
    else:
        runs.append([r])
runs.sort(key=lambda g: -len(g))
for g in runs:
    strong = max(x["bestScore"] for x in g)
    tag = "⛔ جيب" if len(g) >= 3 else ("⚠️ زوج" if len(g) == 2 else "· مفرد")
    print("{} {} → {}  إزاحة {:+d}  ({} آية)  أقوى درجة {}".format(
        tag, g[0]["ayah"], g[-1]["ayah"], g[0]["bestOffset"], len(g), strong))

big = [g for g in runs if len(g) >= 3]
print("\nالخلاصة: {} جيباً مؤكَّداً ({} آية) · {} زوجاً ومفرداً.".format(
    len(big), sum(len(g) for g in big), len(runs) - len(big)))
print("والمفرد وحده لا يُبنى عليه حكمُ إعادة تسمية — يحتاج تحققاً بأذن أو "
      "بنموذج أكبر؛ أما الجيب فبنيةٌ لا صدفة.")
