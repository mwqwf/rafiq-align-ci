# -*- coding: utf-8 -*-
"""عيّنة التسميع المرجعية — 200 آية موزعة على الروايات الثلاث وطبقات الطول.

المبدأ: **لا رقم بلا عيّنة ومداها.** هذا الملف هو سند كل رقم في REPORT.md:
كل بند فيه يحمل مصدره الصوتي وحقيقته الأرضية النصية ومعرّفه الثابت، فيُعاد
إنتاج القياس بلا اجتهاد.

الحقيقة الأرضية النصية من أصول التطبيق (`core/quran/.../assets/quran/text_*.jz`)
— نصّ الرواية نفسه الذي يعرضه المصحف؛ فالتلاوة المرجعية **صحيحة بالافتراض**
(قارئ متقن يتلو الآية كاملة)، ومن ثمّ فالمثالي 100% تتبّعاً، وكل انحراف
**إنذار كاذب** يراه المستخدم خطأً في تلاوته وهو خطأ فينا.

المصادر:
  hafs  — الحصري المعلّم (everyayah، آية-بآية)
  warsh — الدوسري (مرآتنا على R2، آية-بآية، أصلها everyayah)
  qalun — الحصري/قالون (ملفات سور على R2) ⇒ تُقصّ الآية من فهرس توقيتاتنا،
          ولا يُقبل إلا حدٌّ **HIGH غير تقديري** من الطرفين، مع هامش أمان.
          هذا الحدّ يُذكر مع كل رقم قالوني: القصّ يضيف مصدر خطأ ليس في
          المصدرين الآخرين.

    python tools/tasmi_bench/sample.py            # يكتب sample.json
"""
import argparse
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))
from common import load_index, load_text, read_jz  # noqa: E402

WORK = os.path.join(HERE, "work")
SAMPLE = os.path.join(HERE, "sample.json")
SEED = 1446

# قرّاء العيّنة — تنويع مقصود (توجيه الإشراف 09-01): إيقاعات وتسجيلات مختلفة
# لا قارئ واحد، كي لا يقيس البنشمارك تسجيلاً بعينه بدل المحرك.
RECITERS = {
    "hafs": [
        ("husary_muallim", "https://everyayah.com/data/Husary_Muallim_128kbps/", "everyayah.com"),
        ("minshawi", "https://everyayah.com/data/Minshawy_Murattal_128kbps/", "everyayah.com"),
        ("abdulbasit", "https://everyayah.com/data/Abdul_Basit_Murattal_192kbps/", "everyayah.com"),
        ("alafasy", "https://everyayah.com/data/Alafasy_128kbps/", "everyayah.com"),
    ],
    "warsh": [
        ("dosary", "https://pub-2c2e1dcd92e84a2898820dd38d3e09e6.r2.dev/audio/warsh/dosary/",
         "everyayah.com (مرآة R2)"),
        ("yassin", "https://pub-2c2e1dcd92e84a2898820dd38d3e09e6.r2.dev/audio/warsh/yassin/",
         "everyayah.com (مرآة R2)"),
    ],
    # ⚠️ قالون بقارئ واحد اضطراراً: لا مصدر آية-بآية لقالون في أي مكان، ولا
    # فهرس توقيتات عندنا لغير الحصري/قالون. يُذكر مع كل رقم قالوني.
    "qalun": [("husary_qalun", None, "mp3quran (مرآة R2) + فهرس توقيتاتنا")],
}
QALUN_R2_KEY = "audio/qalun/husary_qalun/{surah:03d}.mp3"

# حصص الروايات: قالون أقلّ لأن آياته مقصوصة (مصدر خطأ إضافي موثق أعلاه).
QUOTA = {"hafs": 70, "warsh": 70, "qalun": 60}
# طبقات الطول بعدد كلمات الآية — الحدود من توزيع المصحف لا من الذوق.
STRATA = [("S", 1, 4), ("M", 5, 9), ("L", 10, 19), ("XL", 20, 10_000)]
STRATUM_SHARE = {"S": 0.25, "M": 0.30, "L": 0.25, "XL": 0.20}
QALUN_PAD_MS = 300          # هامش القصّ حول الحد (يستوعب انزياح ±300م.ث المعاير)
QALUN_MAX_FILE = 25_000_000  # لا نُنزّل ملف سورة أكبر من ذلك لأجل آية


def stratum_of(n):
    for name, lo, hi in STRATA:
        if lo <= n <= hi:
            return name
    return None


def ayah_ids(index):
    """(globalIndex → (surah, ayah)) بالعدّ الكوفي الموحّد لأصولنا."""
    out = {}
    for s in index["surahs"]:
        for a in range(s["ayahs"]):
            out[s["start"] + a] = (s["n"], a + 1)
    return out


def qalun_cuttable(index):
    """آيات قالون الصالحة للقصّ: حدّا البداية والنهاية HIGH وغير تقديريين،
    والملف ≤25م.ب. يعيد (map ayahId → معلومات القصّ)."""
    ti = read_jz(os.path.join(WORK, "timings_qalun.jz"))
    sizes = {int(k): v for k, v in json.load(open(os.path.join(WORK, "qalun_sizes.json"))).items()}
    by_id = {e["ayahId"]: e for e in ti["entries"]}
    out = {}
    for e in ti["entries"]:
        s, a = (int(x) for x in e["ayahId"].split(":"))
        if sizes.get(s, 1 << 40) > QALUN_MAX_FILE:
            continue
        if e.get("confBand") != "HIGH" or e.get("startApprox"):
            continue
        nxt = by_id.get(f"{s}:{a+1}")
        # نهاية الآية = بداية التالية؛ فإن كانت تقديرية فالنهاية مشكوك فيها.
        if nxt is not None and (nxt.get("confBand") != "HIGH" or nxt.get("startApprox")):
            continue
        out[e["ayahId"]] = {
            "startMs": max(0, e["startMs"] - QALUN_PAD_MS),
            "endMs": e["endMs"] + QALUN_PAD_MS,
            "confBand": e["confBand"],
            "nextBand": (nxt or {}).get("confBand", "EOF"),
        }
    return out, ti


def build():
    index = load_index()
    ids = ayah_ids(index)
    cut, ti = qalun_cuttable(index)
    rng = random.Random(SEED)
    items, used_keys = [], set()

    for riwaya, quota in QUOTA.items():
        text = load_text(riwaya)
        pool = {name: [] for name, _, _ in STRATA}
        for gi, (s, a) in ids.items():
            words = text[gi].split()
            st = stratum_of(len(words))
            if st is None:
                continue
            if riwaya == "qalun" and f"{s}:{a}" not in cut:
                continue
            pool[st].append((gi, s, a, words))
        for st, share in STRATUM_SHARE.items():
            want = round(quota * share)
            cand = pool[st]
            rng.shuffle(cand)
            picked = 0
            for gi, s, a, words in cand:
                if picked >= want:
                    break
                key = (riwaya, gi)
                if key in used_keys:
                    continue
                used_keys.add(key)
                picked += 1
                rec, base, origin = RECITERS[riwaya][picked % len(RECITERS[riwaya])]
                item = {
                    "id": f"{riwaya}_{rec}_{s:03d}{a:03d}",
                    "riwaya": riwaya,
                    "surah": s, "ayah": a, "globalIndex": gi,
                    "stratum": st, "wordCount": len(words), "reciter": rec,
                    "refText": " ".join(words),
                }
                if base is not None:
                    item["source"] = {"kind": "ayah_file", "url": f"{base}{s:03d}{a:03d}.mp3",
                                      "reciter": rec, "origin": origin}
                else:
                    c = cut[f"{s}:{a}"]
                    item["source"] = {"kind": "cut_from_surah", "reciter": rec,
                                      "r2Key": QALUN_R2_KEY.format(surah=s), "origin": origin,
                                      **c, "padMs": QALUN_PAD_MS}
                items.append(item)
            if picked < want:
                print(f"⚠️ {riwaya}/{st}: {picked}/{want} فقط (نفد المخزون المؤهل)")

    meta = {
        "seed": SEED, "total": len(items), "quota": QUOTA,
        "strata": {n: [lo, hi] for n, lo, hi in STRATA}, "stratumShare": STRATUM_SHARE,
        "groundTruth": "core/quran/src/main/assets/quran/text_{riwaya}.jz (عدّ كوفي 6236)",
        "reciters": {k: [r[0] for r in v] for k, v in RECITERS.items()},
        "qalunTimingIndex": {k: ti[k] for k in ("reciterId", "engineVersion", "generatedAt", "ayahCounting")},
        "limits": [
            "التلاوة المرجعية مفترضة صحيحة ⇒ المقياس يقيس الإنذار الكاذب لا كشف الخطأ.",
            "آيات قالون مقصوصة من ملفات سور بفهرسنا (±300م.ث هامش) — مصدر خطأ زائد.",
            "الحركات والتجويد خارج v1 (D-006).",
        ],
    }
    json.dump({"meta": meta, "items": items}, open(SAMPLE, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"✅ {len(items)} بنداً → {SAMPLE}")
    for r in QUOTA:
        sub = [i for i in items if i["riwaya"] == r]
        dist = {st: sum(1 for i in sub if i["stratum"] == st) for st, _, _ in STRATA}
        print(f"   {r}: {len(sub)} {dist}")


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    build()
