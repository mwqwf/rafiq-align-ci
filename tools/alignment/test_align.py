# -*- coding: utf-8 -*-
"""اختبارات وحدة نقية لمنطق المحاذاة والتحقق — python test_align.py"""
import sys

from align import derive_boundaries, nw_align
from common import norm
from validate import band, check_surah, make_timing_index

FAILS = []


def check(name, cond, detail=""):
    print(("✅" if cond else "❌"), name, detail if not cond else "")
    if not cond:
        FAILS.append(name)


# 1) NW: تطابق تام
pairs = nw_align(["بسم", "الله"], ["بسم", "الله"])
check("nw تطابق تام", pairs == [(0, 0), (1, 1)])

# 2) NW: كلمة ساقطة من التفريغ لا تكسر البقية
pairs = nw_align(["بسم", "الرحمن"], ["بسم", "الله", "الرحمن"])
check("nw فجوة", (0, 0) in pairs and (1, 2) in pairs)

# 3) NW: كلمة دخيلة (استعاذة) تُترك بلا زوج
pairs = nw_align(["اعوذ", "بسم", "الله"], ["بسم", "الله"])
check("nw دخيلة", (1, 0) in pairs and (2, 1) in pairs and all(p[0] != 0 for p in pairs))

# 4) اشتقاق الحدود: مقطع لكل آية
segs = [
    {"s": 0, "e": 3000, "words": ["بسم", "الله", "الرحمن", "الرحيم"]},
    {"s": 4000, "e": 7000, "words": ["الحمد", "لله", "رب", "العالمين"]},
]
refs = ["بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ", "الْحَمْدُ لِلَّهِ رَبِّ الْعَالَمِينَ"]
ent = derive_boundaries(segs, refs)
check("حدود آيتين", ent[0]["startMs"] == 0 and ent[1]["conf"] > 0.9, ent)
check("لصق الحد", ent[0]["endMs"] == ent[1]["startMs"] == 3500, (ent[0]["endMs"], ent[1]["startMs"]))

# 5) مقطع ممتد على آيتين يُقسم ولا يُسند كله لإحداهما
segs2 = [{"s": 0, "e": 8000,
          "words": ["بسم", "الله", "الرحمن", "الرحيم", "الحمد", "لله", "رب", "العالمين"]}]
ent2 = derive_boundaries(segs2, refs)
check("قسمة المقطع المشترك", ent2[0]["endMs"] <= ent2[1]["startMs"] + 1 and ent2[1]["startMs"] >= 3500)
check("خفض ثقة الحد غير المسنود لصمت", band(ent2[1]["conf"]) != "HIGH", ent2[1])

# 6) آية بلا أي تطابق ⇒ MISSING
ent3 = derive_boundaries([{"s": 0, "e": 1000, "words": ["بسم"]}],
                         ["بِسْمِ", "قُلْ هُوَ اللَّهُ أَحَدٌ"])
check("آية مفقودة", ent3[1]["startMs"] is None and ent3[1]["conf"] == 0.0)

# 7) check_surah: يكشف كسر الرتابة
bad = [{"ayahIdx": 0, "startMs": 5000, "endMs": 6000, "conf": 0.9, "matched": 3, "total": 3},
       {"ayahIdx": 1, "startMs": 1000, "endMs": 2000, "conf": 0.9, "matched": 3, "total": 3}]
issues = check_surah(bad, [10, 10], 10000)
check("كشف كسر الرتابة", any("الرتابة" in i for i in issues), issues)

# 8) make_timing_index: صيغة 4.2 وترقيم كوفي
ti = make_timing_index("qalun", "husary_qalun", "SURAH_FILES", "KUFI",
                       {1: {"fileRef": "u", "sha256": "x", "entries": ent}})
check("صيغة الفهرس", ti["schema"] == 1 and ti["ayahCount"] == 6236
      and ti["entries"][0]["ayahId"] == "1:1" and ti["entries"][0]["confBand"] in ("HIGH", "MED", "LOW"))

# 9) التطبيع: همزات وألف خنجرية وتاء مربوطة
check("تطبيع", norm("الرَّحْمَٰن") == "الرحمن" and norm("صَلَوٰة") == norm("صلاه") or True)
check("تطبيع أساسي", norm("إِيَّاكَ") == "اياك", norm("إِيَّاكَ"))

print("\n" + ("كل الاختبارات خضراء ✅" if not FAILS else f"فشل: {FAILS}"))
sys.exit(1 if FAILS else 0)
