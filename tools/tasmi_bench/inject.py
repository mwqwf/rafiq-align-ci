# -*- coding: utf-8 -*-
"""عيّنة **التلاوة المُخطئة** — لقياس الكشف لا الإنذار الكاذب.

عيّنة `sample.json` تلاواتٌ صحيحة، فرقمها يقيس ألّا نُنبّه على خطأ لم يقع.
والنصف الآخر من بوابة G1: هل نُمسك الخطأ إذا وقع؟ ولا نملك تسجيلات تلاواتٍ
مُخطئة موسومة — فنصنعها **بجراحةٍ صوتية بحقيقةٍ أرضية معلومة بالبناء**:

  OMIT       حذف صوت كلمة          ⇒ تُحكم MISSED عند موضعها
  SUBSTITUTE إبدال صوتها بكلمة أخرى ⇒ تُحكم SUBSTITUTED أو MISSED
  SWAP       تبديل مقطعَي كلمتين متجاورتين ⇒ خللٌ عند إحدى الموضعين
  INSERT     إقحام كلمة زائدة بينهما ⇒ تظهر في additions

الحدود الكلمية من `segments_husary.jz` (أصل QUL، مضبوط على **الحصري المعلّم**
حصراً — لا يصلح لقارئٍ آخر: نسبة مدى الكلام بين تسجيلاته 1.25×).

⚠️ **حدُّ العيّنة المعلن:** الخطأ المصنوع قطعٌ نظيف على حدٍّ مقيس، والخطأ
البشري يجيء بتردّدٍ وإعادةٍ ونَفَسٍ مقطوع. فأرقام الكشف هنا **حدٌّ أعلى
متفائل**، ولا تُقدَّم بديلاً عن تسجيلاتٍ بشرية مخطئة حين تتوفر.

    python tools/tasmi_bench/inject.py            # يكتب inject_plan.json
"""
import argparse
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))
from common import QURAN_ASSETS, load_index, load_text, read_jz  # noqa: E402

BASE = "https://everyayah.com/data/Husary_Muallim_128kbps/"
SEED = 1447
PER_OP = 40                      # لكل نوع خطأ
MIN_WORDS, MAX_WORDS = 4, 14     # آياتٌ قصيرة/متوسطة: الجراحة فيها لا لبس فيها
PAD_MS = 30                      # هامش القطع حول حدّ الكلمة


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "inject_plan.json"))
    args = ap.parse_args()
    seg = read_jz(os.path.join(QURAN_ASSETS, "segments_husary.jz"))
    text = load_text("hafs")
    index = load_index()
    pos = {}
    for s in index["surahs"]:
        for a in range(s["ayahs"]):
            pos[s["start"] + a] = (s["n"], a + 1)

    ok = []
    for k, words in seg.items():
        gi = int(k)
        ref = text[gi].split()
        # لا نأخذ إلا آيةً عدد مقاطعها = عدد كلماتها (وإلا فالإسناد ملتبس)
        if len(ref) == len(words) and MIN_WORDS <= len(ref) <= MAX_WORDS:
            ok.append((gi, ref, words))
    rng = random.Random(SEED)
    rng.shuffle(ok)

    items, used = [], 0
    for op in ("OMIT", "SUBSTITUTE", "SWAP", "INSERT"):
        picked = 0
        while picked < PER_OP and used < len(ok):
            gi, ref, words = ok[used]; used += 1
            wi = rng.randrange(1, len(ref) - 1)      # كلمة داخلية: لا أول ولا آخر
            w = words[wi]
            if w[1] - w[0] < 200:                     # مقطعٌ أقصر من 200م.ث ملتبس
                continue
            s, a = pos[gi]
            it = {"id": f"inj_{op.lower()}_{s:03d}{a:03d}", "op": op,
                  "surah": s, "ayah": a, "globalIndex": gi, "wordIndex": wi,
                  "riwaya": "hafs", "reciter": "husary_muallim",
                  "refText": " ".join(ref), "wordCount": len(ref),
                  "targetWord": ref[wi],
                  "url": f"{BASE}{s:03d}{a:03d}.mp3",
                  "cutMs": [max(0, w[0] - PAD_MS), w[1] + PAD_MS]}
            if op == "SWAP":
                if wi + 1 >= len(ref):
                    continue
                nxt = words[wi + 1]
                if nxt[1] - nxt[0] < 200 or nxt[0] - w[1] > 400:
                    continue          # لا نبدّل عبر سكتةٍ طويلة (يصير قطعاً لا تبديلاً)
                it["swapMs"] = [max(0, nxt[0] - PAD_MS), nxt[1] + PAD_MS]
                it["targetWord"] = ref[wi] + " ↔ " + ref[wi + 1]
            if op in ("SUBSTITUTE", "INSERT"):
                # كلمةٌ من آيةٍ أخرى، مغايرةٌ هيكلياً للمستبدَلة
                for _ in range(50):
                    gj, refj, wj = ok[rng.randrange(len(ok))]
                    j = rng.randrange(len(refj))
                    if refj[j] != ref[wi] and wj[j][1] - wj[j][0] >= 200:
                        sj, aj = pos[gj]
                        it["donor"] = {"url": f"{BASE}{sj:03d}{aj:03d}.mp3",
                                       "cutMs": [max(0, wj[j][0] - PAD_MS), wj[j][1] + PAD_MS],
                                       "word": refj[j], "ayah": f"{sj}:{aj}"}
                        break
                if "donor" not in it:
                    continue
            items.append(it)
            picked += 1
    json.dump({"seed": SEED, "source": "segments_husary.jz (الحصري المعلّم)",
               "padMs": PAD_MS, "items": items},
              open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"✅ {len(items)} بنداً ({PER_OP} لكل نوع) → {args.out}")


if __name__ == "__main__":
    main()
