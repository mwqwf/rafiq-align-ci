# -*- coding: utf-8 -*-
"""🔪 **مجموعةُ حقنٍ لورشٍ وقالون** — نظيرةُ `inject.py` الحفصيّة.

⚠️ **لِمَ وُجدت:** `inject_plan.json` الحفصيّة **حفصٌ خالصٌ كلُّها** (‏160 بنداً، صفرُ ورشٍ
وقالون). فكانت بوّابةُ الإنذار الكاذب **عمياءَ عن الروايتين** اللتين ضُبط لهما النموذجُ الثاني،
فحُكم عليه بما لم يُقَس فيه. (‏2026-09-08 — وهو نظيرُ الدرس: لا يُحكم بعيّنةٍ جزئية.)

**المصدر:** فهارسُ توقيتات الكلمات من جلسة الفهرسة `github-17`:
`wordtimings/<riwaya>/husary_<riwaya>.jz` على R2.

⭐ **والقارئُ واحدٌ في الروايات الثلاث** (الحصريّ) — وهو أيضاً صاحبُ `segments_husary.jz`
الحفصيّة. ⇒ **الصوتُ ثابتٌ والروايةُ وحدَها تتغيّر**، فأيُّ فارقٍ يظهر يُنسب إليها لا إلى
اختلاف القارئ. (ضبطُ متغيّرٍ نبّهت إليه جلسةُ الفهرسة ولم أطلبه.)

⛔ **ثلاثةُ قيودٍ من ترويسة الفهرس، وإهمالُ أوّلِها يُفسد القياس كلَّه:**

1. **`endsPolicy: contiguous`** — `startMs` **ليس بدايةً مقيسة** بل نهايةَ الكلمة السابقة،
   والنهاياتُ ملصوقةٌ عمداً. ⇒ **لا حشوةَ في الأمام أبداً**: حشوةٌ عند القطع تسحب ذيلَ الجارة
   إلى المقطع، **فتقيس البوّابةُ إنذاراً كاذباً سببُه السكّينُ لا النموذج**.
2. **`fullEvidence: true` شرطٌ لازم** — وإلا فبعضُ الحدود مستنتَجٌ لا مقيس.
3. **التغطيةُ جزئية** — جزءُ 30 أوثقُها (‏449/463 ورشاً · 524/527 قالوناً)، والكهفُ صفرٌ في
   ورش. ⇒ تُؤخذ السورُ 78 فما فوق، وهي أيضاً **ملفّاتٌ صغيرة** فلا تُثقل شبكةَ المالك.

    python tools/tasmi_bench/inject_riwaya.py            # يبني الخطّة
"""
import argparse
import gzip
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "alignment"))
from common import load_index, load_text  # noqa: E402

SEED = 1446
PER_OP = 20                 # لكل رواية ⇒ 4 عمليات × 20 × روايتان = 160 بنداً
MIN_WORDS, MAX_WORDS = 5, 20
MIN_WORD_MS = 200           # مقطعٌ أقصر ملتبسُ الحدّ
FIRST_SURAH = 78            # جزءُ 30 — أوثقُ تغطيةً وأخفُّ تنزيلاً

R2 = "https://pub-2c2e1dcd92e84a2898820dd38d3e09e6.r2.dev/"
AUDIO = {
    "warsh": "https://server13.mp3quran.net/husr/Rewayat-Warsh-A-n-Nafi/",
    "qalun": "https://server13.mp3quran.net/husr/Rewayat-Qalon-A-n-Nafi/",
}


def load_timings(riwaya, work):
    """ينزّل فهرسَ التوقيتات مرّةً واحدة ويكيشه (شبكةُ المالك موردٌ شحيح)."""
    name = f"husary_{riwaya}.jz"
    dst = os.path.join(work, name)
    if not os.path.isfile(dst):
        import urllib.request
        op = urllib.request.build_opener()
        op.addheaders = [("User-Agent", "Mozilla/5.0 (QuranRafiq tools)")]
        os.makedirs(work, exist_ok=True)
        with op.open(R2 + f"wordtimings/{riwaya}/{name}", timeout=180) as r, open(dst, "wb") as o:
            o.write(r.read())
    d = json.loads(gzip.open(dst, "rt", encoding="utf-8").read())
    assert d["endsPolicy"] == "contiguous", d["endsPolicy"]  # ⛔ حارسُ الافتراض
    return d


def bounds(words):
    """حدودُ كل كلمةٍ بترتيبها. ⛔ بلا حشوة — النهاياتُ ملصوقة (`contiguous`)."""
    out = {}
    for w in words:
        i = int(w["wordId"].split(":")[2]) - 1
        a, b = w["startMs"], w["endMs"]
        if i in out:                      # كلمةٌ ذاتُ مقاطع (`subIndex`)
            a, b = min(a, out[i][0]), max(b, out[i][1])
        out[i] = (a, b)
    return [out[i] for i in sorted(out)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "inject_plan_riwaya.json"))
    ap.add_argument("--work", default=os.path.join(HERE, "work"))
    ap.add_argument("--per-op", type=int, default=PER_OP,
                    help="عددُ البنود لكلِّ عمليةٍ في كلِّ رواية (الافتراضُ المقيسُ 20)")
    # ⛔⛔ **ولِمَ `--extend` ولا يُكتفى برفع `--per-op`** (‏درسُ D-415): المسبحُ يُمشى فيه
    # **بالترتيب** (‏`used` يتقدّم ولا يعود)، فرفعُ `PER_OP` يُطيل نصيبَ `OMIT` فيتزحزح
    # مبدأُ `SUBSTITUTE` ومَن بعده ⇒ **البنودُ القديمةُ نفسُها تتغيّر**، فلا تُقارن العيّنةُ
    # الكبرى بالصغرى ولا يُقال «العيّنةُ نفسُها موسَّعة». ⇒ **التوسيعُ فائقٌ (superset) أو لا يكون:**
    # تُحفظ البنودُ القائمةُ حرفاً وتُضاف إليها آياتٌ **لم تُستعمل** من المسبح عينِه.
    ap.add_argument("--extend", default="",
                    help="مسارُ خطّةٍ قائمةٍ تُحفظ بنودُها كما هي ويُبنى عليها (توسيعٌ فائق)")
    args = ap.parse_args()

    keep, kept_ayat, kept_count = [], set(), {}
    if args.extend:
        old = json.load(open(args.extend, encoding="utf-8"))
        keep = old["items"]
        ids = [i["id"] for i in keep]
        if len(set(ids)) != len(ids):
            raise SystemExit("⛔ الخطّةُ القائمةُ فيها معرّفٌ مكرَّر — لا يُبنى على أصلٍ مشتبَه")
        for i in keep:
            kept_ayat.add((i["riwaya"], i["surah"], i["ayah"]))
            kept_count[(i["riwaya"], i["op"])] = kept_count.get((i["riwaya"], i["op"]), 0) + 1
        print(f"🧩 توسيعٌ فائقٌ فوق {len(keep)} بنداً قائماً ⇒ الهدفُ {args.per_op} لكلِّ عملية")

    index = load_index()
    start = {s["n"]: s["start"] for s in index["surahs"]}
    rng = random.Random(SEED)
    items = []
    census, deficit = {}, []

    for riwaya in ("warsh", "qalun"):
        d = load_timings(riwaya, args.work)
        text = load_text(riwaya)
        pool = []
        for e in d["entries"]:
            if not e["evidence"].get("fullEvidence"):
                continue
            s, a = map(int, e["ayahId"].split(":"))
            if s < FIRST_SURAH:
                continue
            ref = text[start[s] + a - 1].split()
            wb = bounds(e["words"])
            if len(wb) != len(ref) or not (MIN_WORDS <= len(ref) <= MAX_WORDS):
                continue
            pool.append((s, a, ref, wb))
        rng.shuffle(pool)
        census[riwaya] = {"مسبحٌ مؤهَّل": len(pool),
                          "مستعمَلٌ سابقاً": sum(1 for p in pool if (riwaya, p[0], p[1]) in kept_ayat)}

        used = 0
        for op in ("OMIT", "SUBSTITUTE", "SWAP", "INSERT"):
            picked = kept_count.get((riwaya, op), 0)         # المحفوظُ يُحسب من النصيب
            target = max(args.per_op, picked)                 # ⛔ ولا يُنقَص محفوظٌ بحال
            while picked < target and used < len(pool):
                s, a, ref, wb = pool[used]
                used += 1
                # ⛔ آيةٌ في الخطّة القائمة **لا تُؤخذ ثانيةً**: بندان في آيةٍ واحدةٍ يتشاركان
                # الصوتَ نفسَه فلا يكونان شاهدَين مستقلَّين.
                if (riwaya, s, a) in kept_ayat:
                    continue
                wi = rng.randrange(1, len(ref) - 1)          # داخليّة: لا أولى ولا أخيرة
                a0, b0 = wb[wi]
                if b0 - a0 < MIN_WORD_MS:
                    continue
                it = {
                    "id": f"inj_{riwaya}_{op.lower()}_{s:03d}{a:03d}",
                    "op": op, "surah": s, "ayah": a, "wordIndex": wi,
                    "riwaya": riwaya, "reciter": f"husary_{riwaya}",
                    "refText": " ".join(ref), "wordCount": len(ref),
                    "targetWord": ref[wi],
                    "url": AUDIO[riwaya] + f"{s:03d}.mp3",
                    "ayahMs": [wb[0][0], wb[-1][1]],          # مدى الآية داخل ملفّ السورة
                    "cutMs": [a0, b0],                        # ⛔ بلا حشوة
                }
                if op == "SWAP":
                    if wi + 1 >= len(ref):
                        continue
                    a1, b1 = wb[wi + 1]
                    if b1 - a1 < MIN_WORD_MS:
                        continue
                    it["swapMs"] = [a1, b1]
                    it["targetWord"] = ref[wi] + " ↔ " + ref[wi + 1]
                if op in ("SUBSTITUTE", "INSERT"):
                    for _ in range(60):
                        sj, aj, refj, wbj = pool[rng.randrange(len(pool))]
                        j = rng.randrange(len(refj))
                        aj0, bj0 = wbj[j]
                        if refj[j] != ref[wi] and bj0 - aj0 >= MIN_WORD_MS:
                            it["donor"] = {
                                "url": AUDIO[riwaya] + f"{sj:03d}.mp3",
                                "cutMs": [aj0, bj0], "word": refj[j], "ayah": f"{sj}:{aj}",
                            }
                            break
                    if "donor" not in it:
                        continue
                items.append(it)
                picked += 1
            if picked < target:
                # ⛔ **والنقصُ يُسمّى برقمه:** «وُسِّعت الخطّة» وهي ناقصةٌ في صنفٍ حكمٌ كاذب،
                # والمسبحُ سقفٌ مقيسٌ لا يُتجاوز بتليينِ شرطٍ من شروط البند.
                deficit.append(f"{riwaya}/{op}: {picked} من {target}")

    out = keep + items
    ids = [i["id"] for i in out]
    if len(set(ids)) != len(ids):
        raise SystemExit("⛔ معرّفٌ مكرَّرٌ في الخطّة المبنيّة — لا تُكتب")
    # ⛔ **حارسُ التوسيع الفائق:** البنودُ القائمةُ **أوّلاً وبنصّها** — فإن تزحزحت واحدةٌ
    # فالعيّنتان مختلفتان ولا يُقارن رقمٌ برقم.
    if keep and out[:len(keep)] != keep:
        raise SystemExit("⛔ التوسيعُ ليس فائقاً: بندٌ قائمٌ تغيّر ⇒ لا تُكتب الخطّة")

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"seed": SEED, "endsPolicy": "contiguous", "pad": 0,
                   "note": "⛔ بلا حشوةٍ عند القطع — النهاياتُ ملصوقة، والحشوةُ تسحب ذيلَ الجارة",
                   "items": out}, f, ensure_ascii=False, indent=1)
    print(f"✅ {len(out)} بنداً ({len(keep)} محفوظاً + {len(items)} جديداً) ⇒ {args.out}")
    import collections
    print("  الروايات:", dict(collections.Counter(i["riwaya"] for i in out)))
    print("  العمليات:", dict(collections.Counter(i["op"] for i in out)))
    print("  السور:", len({(i['riwaya'], i['surah']) for i in out}), "ملفَّ سورةٍ للتنزيل")
    print("  المسبح:", json.dumps(census, ensure_ascii=False))
    if deficit:
        print("⛔ نقصٌ عن المطلوب (سقفُ المسبح): " + " · ".join(deficit))
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
