# -*- coding: utf-8 -*-
"""خطة حقنٍ لقالون — تعميم قياس الكشف على روايةٍ ثانية.

الفرق عن `inject.py`: قالون ليس له ملفات آيات، فالآية تُقتطع من ملف السورة
بحدود فهرس التوقيتات (‏HIGH غير تقديري)، والكلمة تُقتطع بحدود الكلام من
`speech_bounds_sample_husary_qalun.json` (‏rafiq-words/github-1e).

⛔ **قيدٌ فرضه مصدر الحدود، وقياسٌ حسمه:** الحدود الكلمية المنشورة **ملصوقة**
(بداية الكلمة = نهاية سابقتها)، وVAD إنما يشذّب الصمت داخل المدى. فأردنا ألّا
نحقن إلا في كلمةٍ عليها صمتٌ مقيس من الطرفين — **فوجدنا 5 كلمات فقط من 1036،
وصفراً منها داخلية**. أي أن الشرط النظيف **يُفرغ العيّنة**، فتلاوة قالون
المرتّلة موصولة النَفَس.

**الحلّ المعتمد بدل تعطيل القياس:** نقطع عند **علامة نهاية الكلمة نفسها**
(‏t_dtw، وهي المقيسة أصلاً وهي التي يظلّل بها التطبيق)، ثم **نتحقّق من
الجراحة بعدها لا نفترض صحّتها**: يُقاس الكشف على البنود التي أثبت التفريغ
أن جراحتها وقعت حيث أُريد لها (‏`detect_score.py --validate`) — والباقي
يُعلن مرفوضاً بعدده. فالحقيقة الأرضية تبقى **متحققة** لا مفترضة.

    python tools/tasmi_bench/inject_qalun.py
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

BOUNDS = os.path.join(ROOT, "tools", "alignment_v2", "out",
                      "speech_bounds_sample_husary_qalun.json")
TIMINGS = os.path.join(HERE, "work", "timings_qalun.jz")
R2_KEY = "audio/qalun/husary_qalun/{surah:03d}.mp3"
SEED = 1448
PER_OP = 25
PAD_MS = 30
AYAH_PAD_MS = 300


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "inject_plan_qalun.json"))
    args = ap.parse_args()
    bounds = json.load(open(BOUNDS, encoding="utf-8"))["entries"]
    ti = read_jz(TIMINGS)
    span = {e["ayahId"]: e for e in ti["entries"]}
    text = load_text("qalun")
    index = load_index()
    gi_of = {}
    for s in index["surahs"]:
        for a in range(s["ayahs"]):
            gi_of[(s["n"], a + 1)] = s["start"] + a

    cand = []
    for e in bounds:
        s, a = (int(x) for x in e["ayahId"].split(":"))
        cur, nxt = span.get(e["ayahId"]), span.get(f"{s}:{a+1}")
        if not cur or cur.get("confBand") != "HIGH" or cur.get("startApprox"):
            continue
        if nxt and (nxt.get("confBand") != "HIGH" or nxt.get("startApprox")):
            continue
        ref = text[gi_of[(s, a)]].split()
        words = e["words"]
        if len(words) != len(ref) or not (4 <= len(ref) <= 14):
            continue
        # كلمات داخلية عليها صمتٌ مقيس من الطرفين فقط
        usable = [i for i, w in enumerate(words)
                  if 0 < i < len(ref) - 1 and w["endMs"] - w["startMs"] >= 250]
        if usable:
            cand.append((s, a, ref, words, usable,
                         max(0, cur["startMs"] - AYAH_PAD_MS), cur["endMs"] + AYAH_PAD_MS))
    rng = random.Random(SEED)
    rng.shuffle(cand)
    print(f"مخزونٌ صالح: {len(cand)} آية (بكلمةٍ صالحة فأكثر)")

    items, used = [], 0
    for op in ("OMIT", "SUBSTITUTE", "SWAP", "INSERT"):
        picked = 0
        while picked < PER_OP and used < len(cand):
            s, a, ref, words, usable, t0, t1 = cand[used]; used += 1
            wi = usable[rng.randrange(len(usable))]
            w = words[wi]
            # القطع على حدّي الكلمة المقيسين (‏t_dtw) لا على تشذيب VAD:
            # الأخير غائب في 96% من الكلمات (موصولة)، والأول هو الحدّ المنشور.
            cut = [w["startMs"] - t0, w["endMs"] - t0]
            it = {"id": f"injq_{op.lower()}_{s:03d}{a:03d}", "op": op, "riwaya": "qalun",
                  "reciter": "husary_qalun", "surah": s, "ayah": a,
                  "globalIndex": gi_of[(s, a)], "wordIndex": wi, "wordCount": len(ref),
                  "refText": " ".join(ref), "targetWord": ref[wi],
                  "r2Key": R2_KEY.format(surah=s), "trimMs": [t0, t1], "cutMs": cut}
            if op == "SWAP":
                if wi + 1 >= len(ref):
                    continue
                n2 = words[wi + 1]
                if n2["endMs"] - n2["startMs"] < 250:
                    continue
                it["swapMs"] = [n2["startMs"] - t0, n2["endMs"] - t0]
                it["targetWord"] = ref[wi] + " ↔ " + ref[wi + 1]
            if op in ("SUBSTITUTE", "INSERT"):
                for _ in range(60):
                    s2, a2, ref2, w2, u2, _, _ = cand[rng.randrange(len(cand))]
                    j = u2[rng.randrange(len(u2))]
                    if ref2[j] != ref[wi]:
                        it["donor"] = {"r2Key": R2_KEY.format(surah=s2),
                                       "cutMs": [w2[j]["startMs"], w2[j]["endMs"]],
                                       "word": ref2[j], "ayah": f"{s2}:{a2}"}
                        break
                if "donor" not in it:
                    continue
            items.append(it)
            picked += 1
        if picked < PER_OP:
            print(f"⚠️ {op}: {picked}/{PER_OP} (نفد المخزون)")
    json.dump({"seed": SEED, "source": os.path.basename(BOUNDS),
               "constraint": "القطع على حدّي t_dtw المقيسين؛ صحة الجراحة تُتحقَّق بعدياً لا تُفترض",
               "silenceBothSides": "5 كلمات من 1036 فقط (صفر داخلية) ⇒ الشرط النظيف يُفرغ العيّنة",
               "padMs": PAD_MS, "ayahPadMs": AYAH_PAD_MS, "items": items},
              open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"✅ {len(items)} بنداً → {args.out}")


if __name__ == "__main__":
    main()
