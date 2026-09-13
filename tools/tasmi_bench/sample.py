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


def verify_audio(new_items):
    """⛔ **عيّنةٌ فيها بندٌ بلا صوتٍ تُسقط الشوطَ كلَّه** (‏`complete()` في البوّابة يشترط كلَّ
    المعرّفات) ⇒ تُفحَص روابطُ **الجديد** وحدَها بـHEAD قبل أن تُودَع العيّنة.
    ⛔ **ويُفحص في العدّاء لا في صندوق الوكيل**: R2 محجوبٌ هناك (‏403 مقيس) فيردّ الغيابَ كاذباً.
    """
    import urllib.error
    import urllib.request
    missing, checked = [], 0
    for it in new_items:
        src = it["source"]
        if src.get("kind") != "ayah_file":
            continue                      # المقصوصُ من سورةٍ لا رابطَ آيةٍ له
        req = urllib.request.Request(src["url"], method="HEAD",
                                     headers={"User-Agent": "Mozilla/5.0 (QuranRafiq sample)"})
        checked += 1
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                if int(r.headers.get("Content-Length") or 0) < 1000:
                    missing.append((it["id"], f"حجمٌ {r.headers.get('Content-Length')}"))
        except Exception as e:                                    # noqa: BLE001
            missing.append((it["id"], str(e)[:60]))
    print(f"🔎 فُحص {checked} رابطاً جديداً · غائبٌ أو مشتبَهٌ: {len(missing)}")
    for i, why in missing[:20]:
        print(f"   ⛔ {i}: {why}")
    return missing


def build(quota=None, extend="", out=None, verify=False):
    """[quota] حصصٌ تُبدّل `QUOTA` · [extend] عيّنةٌ قائمةٌ **تُحفظ بنودُها بحروفها** ويُبنى عليها.

    ⛔⛔ **ولِمَ `--extend` ولا يُكتفى برفع الحصّة** (‏درسُ D-415 حرفاً): المخزونُ يُخلَط
    ويُمشى فيه بالترتيب، فرفعُ الحصّة **يزحزح البنودَ القديمةَ نفسَها** (وقد قِيس في نظيرتها
    `inject_riwaya.py`: من 5 إلى 8 لكلّ عملية **سقط 32 بنداً من 40** و**ثلاثةٌ حفظت معرّفَها
    وتغيّر محتواها**) ⇒ **فتفقد كلُّ أرقام اللوحة المبنيّةِ على `g1`/`g2` مقارنتَها بما قبلها**.
    ⇒ **التوسيعُ فائقٌ (superset) أو لا يكون.**
    """
    quota = dict(quota or QUOTA)
    # ⛔ **ومخرَجٌ صريحٌ يُسمّى:** كانت الدالّةُ تكتب فوق `sample.json` دائماً، فتجربةٌ واحدةٌ
    # تُفسد سندَ كلِّ رقمٍ في اللوحة. ⇒ يُجرَّب في مسارٍ آخرَ ويُودَع بعد الفحص.
    out = out or SAMPLE
    index = load_index()
    ids = ayah_ids(index)
    rng = random.Random(SEED)
    items, used_keys = [], set()

    keep, old_meta = [], {}
    if extend:
        old = json.load(open(extend, encoding="utf-8"))
        keep, old_meta = old["items"], old.get("meta") or {}
        for it in keep:
            used_keys.add((it["riwaya"], it["globalIndex"]))
        have = {}
        for it in keep:
            have[(it["riwaya"], it["stratum"])] = have.get((it["riwaya"], it["stratum"]), 0) + 1
        print(f"🧩 توسيعٌ فائقٌ فوق {len(keep)} بنداً قائماً")
    else:
        have = {}

    # ⭐ **وفهرسُ قالون لا يُنزَّل إلّا إن احتاجته الحصّة:** توسيعُ **ورشٍ** وحدَه نصٌّ خالصٌ
    # (‏لا قصَّ ولا فهرس) ⇒ فيصير مُنتَجاً **في صندوق الوكيل** بلا R2 المحجوب، بدل شوطٍ في العدّاء.
    # ⛔ وإن احتاجته الحصّةُ فالغيابُ يُسمّى باسمه ولا يُتجاوز صامتاً.
    need_qalun = any(have.get(("qalun", st), 0) < round(quota.get("qalun", 0) * share)
                     for st, share in STRATUM_SHARE.items())
    if need_qalun:
        cut, ti = qalun_cuttable(index)
    else:
        cut, ti = {}, None
        print("ℹ️ حصّةُ قالون مكتملةٌ في العيّنة القائمة ⇒ لا يُنزَّل فهرسُ التوقيتات")

    for riwaya, quota_r in quota.items():
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
        print(f"   📊 {riwaya}: مخزونٌ مؤهَّلٌ " +
              " · ".join(f"{st}={len(pool[st])}" for st, _, _ in STRATA))
        for st, share in STRATUM_SHARE.items():
            want = round(quota_r * share)
            cand = pool[st]
            rng.shuffle(cand)
            # ⛔ **المحفوظُ يُحسب من النصيب ولا يُنقَص:** وإلّا أضافَ التوسيعُ فوق الحصّة كاملةً
            # فاختلّت نسبُ الطبقات التي وُضعت من توزيع المصحف لا من الذوق.
            picked = have.get((riwaya, st), 0)
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

    if verify and items:
        bad = verify_audio(items)
        if bad:
            # ⛔ ولا تُكتب عيّنةٌ فيها بندٌ لا صوتَ له: خيرٌ أن تُصغَّر الحصّةُ من أن يسقط شوط.
            raise SystemExit(f"⛔ {len(bad)} بنداً جديداً بلا صوتٍ متحقَّق ⇒ لا تُكتب العيّنة")

    out_items = keep + items
    ids_seen = [i["id"] for i in out_items]
    if len(set(ids_seen)) != len(ids_seen):
        raise SystemExit("⛔ معرّفٌ مكرَّرٌ في العيّنة المبنيّة — لا تُكتب")
    # ⛔ **حارسُ التوسيع الفائق:** القائمُ أوّلاً وبنصّه — فإن تزحزح بندٌ فالعيّنتان مختلفتان
    # ولا يُقارن رقمٌ برقمٍ في اللوحة كلِّها.
    if keep and out_items[:len(keep)] != keep:
        raise SystemExit("⛔ التوسيعُ ليس فائقاً: بندٌ قائمٌ تغيّر ⇒ لا تُكتب العيّنة")

    meta = {
        "seed": SEED, "total": len(out_items), "quota": quota,
        "strata": {n: [lo, hi] for n, lo, hi in STRATA}, "stratumShare": STRATUM_SHARE,
        "groundTruth": "core/quran/src/main/assets/quran/text_{riwaya}.jz (عدّ كوفي 6236)",
        "reciters": {k: [r[0] for r in v] for k, v in RECITERS.items()},
        # ⛔ وترويسةُ فهرس قالون تُحفظ كما كانت إن لم يُنزَّل الفهرسُ — ولا تُكتب فراغاً يُقرأ «لا فهرس».
        "qalunTimingIndex": ({k: ti[k] for k in ("reciterId", "engineVersion", "generatedAt", "ayahCounting")}
                             if ti is not None else old_meta.get("qalunTimingIndex")),
        "limits": [
            "التلاوة المرجعية مفترضة صحيحة ⇒ المقياس يقيس الإنذار الكاذب لا كشف الخطأ.",
            "آيات قالون مقصوصة من ملفات سور بفهرسنا (±300م.ث هامش) — مصدر خطأ زائد.",
            "الحركات والتجويد خارج v1 (D-006).",
        ],
    }
    json.dump({"meta": meta, "items": out_items}, open(out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"✅ {len(out_items)} بنداً ({len(keep)} محفوظاً + {len(items)} جديداً) → {out}")
    for r in quota:
        sub = [i for i in out_items if i["riwaya"] == r]
        dist = {st: sum(1 for i in sub if i["stratum"] == st) for st, _, _ in STRATA}
        print(f"   {r}: {len(sub)} {dist}")
    return 0


def parse_quota(text):
    """`warsh=140,qalun=120` ⇒ حصصٌ تُبدّل الافتراض. ⛔ ورواية لا نعرفها تسقط باسمها."""
    q = dict(QUOTA)
    for part in [p for p in text.split(",") if p.strip()]:
        k, _, v = part.partition("=")
        k = k.strip()
        if k not in QUOTA:
            raise SystemExit(f"⛔ روايةٌ لا تُعرف في الحصص: {k!r} — والمعروفةُ {list(QUOTA)}")
        if not v.strip().isdigit() or not (1 <= int(v) <= 2000):
            raise SystemExit(f"⛔ حصّةٌ غيرُ مقبولة لـ{k}: {v!r}")
        q[k] = int(v)
    return q


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--quota", default="", help="حصصٌ تُبدّل الافتراض: warsh=140,qalun=120")
    ap.add_argument("--extend", default="", help="عيّنةٌ قائمةٌ تُحفظ بنودُها ويُبنى عليها (توسيعٌ فائق)")
    ap.add_argument("--out", default="", help="مسارُ المخرَج (الافتراضُ sample.json نفسُه)")
    ap.add_argument("--verify-audio", action="store_true",
                    help="افحصْ روابطَ البنود الجديدة بـHEAD قبل الكتابة (في العدّاء — R2 محجوبٌ عن الصندوق)")
    a = ap.parse_args()
    raise SystemExit(build(parse_quota(a.quota) if a.quota else None, a.extend, a.out or None,
                           a.verify_audio))
