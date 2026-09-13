# -*- coding: utf-8 -*-
"""🔎 بحثٌ مقيسٌ عن حالةٍ يكون فيها **الأعلى صوتاً غيرَ الصحيح** — دَينُ D-320/D-324.

السؤال: `QuranLocator.TOP = 8` (البند 3: «أفضلُ TOP مرشّحين يُحاذَون فعلاً ويُختار أعلاهم
جودةً») يمرّ أخضرَ حين يُجعل 1 ⇒ لا حارسَ له. وسببُه معلومٌ: عيّنةُ `QuranLocatorTest` ستّةَ
عشرَ آيةً، الأعلى صوتاً فيها هو الصحيحُ دائماً. فالحارسُ المطلوب حالةٌ **من المصحف كلِّه**
يكون فيها ترتيبُ الصوت خاطئاً وترتيبُ الجودة (البند 3) هو ما يُصيب.

  python tools/tasmi_bench/locator_top_probe.py --riwaya hafs [--limit N] [--full]

المرحلةُ الأولى (رخيصة · تصويتٌ فقط): لكلِّ آية، ما رتبةُ الآية الصحيحة في `candidates`؟
المرحلةُ الثانية (`--full` · محاذاةٌ كاملة): للحالات التي رتبتُها > 1، هل `locate` بـ`top=8`
يُصيب و`top=1` يُخطئ؟ ⇒ تلك هي الثغرةُ التي يعضُّها الحارس.

⚠️ الأرقامُ كلُّها من المرآة البايثونية (`locator.py` · `scorer.py`) لا من المحرك.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))

import scorer  # noqa: E402
from common import load_text  # noqa: E402
from locator import Locator  # noqa: E402

WS = scorer.re.compile(r"\s+") if hasattr(scorer, "re") else None


def norm_words(text, cfg):
    return [w for w in (scorer.norm(x, cfg) for x in text.split()) if w]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--riwaya", default="hafs")
    ap.add_argument("--limit", type=int, default=0, help="عددُ الآيات المفحوصة (0 = الكلّ)")
    ap.add_argument("--full", action="store_true", help="المرحلةُ الثانية: locate كاملاً على المرشَّحات")
    ap.add_argument("--max-full", type=int, default=40, help="سقفُ حالات المرحلة الثانية")
    ap.add_argument("--pair", action="store_true", help="الفرضيّةُ آيتان متتاليتان لا آيةً واحدة")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    cfg = scorer.DEFAULT
    text = load_text(args.riwaya)
    ayah_words = [a.split() for a in text]
    loc = Locator(ayah_words, cfg)
    n_all = len(ayah_words)

    # 🔁 المتشابهاتُ التامّة: بدايةٌ نصُّها مطابقٌ حرفاً بحرف ليست «خطأً» بل بديلٌ مشروع (البند 5).
    ident = {}
    for i, ws in enumerate(ayah_words):
        ident.setdefault(" ".join(scorer.norm(w, cfg) for w in ws), []).append(i)

    rng = range(n_all if not args.limit else min(args.limit, n_all))
    ranks = {}
    suspects = []
    for f in rng:
        if args.pair:
            if f + 1 >= n_all:
                continue
            hyp_text = " ".join(text[f].split() + text[f + 1].split())
        else:
            hyp_text = text[f]
        core = norm_words(hyp_text, cfg)
        cut = loc.strip_preamble(core)
        core = core[cut:]
        if len(core) < 2:
            continue
        cands = loc.candidates(core)
        order = [c[0] for c in cands]
        r = order.index(f) + 1 if f in order else 0   # 0 = خارج الثمانية
        ranks[r] = ranks.get(r, 0) + 1
        if r != 1:
            twin = len(ident[" ".join(scorer.norm(w, cfg) for w in ayah_words[f])]) > 1
            suspects.append({"flat": f, "rank": r, "top": order[:3],
                             "votes": [round(c[1], 3) for c in cands[:3]], "twin": twin})

    print(f"# {args.riwaya} · آياتٌ مفحوصة {sum(ranks.values())} · الفرضيّة "
          f"{'آيتان' if args.pair else 'آيةٌ واحدة'}")
    for r in sorted(ranks):
        print(f"  رتبةُ الصحيح = {r if r else 'خارج الثمانية'} : {ranks[r]}")
    print(f"# مرشَّحاتٌ للحارس (رتبة ≠ 1): {len(suspects)}")
    for s in suspects[:60]:
        print("   ", s)

    hits = []
    if args.full and suspects:
        for s in suspects[:args.max_full]:
            f = s["flat"]
            if args.pair:
                hyp_text = " ".join(text[f].split() + text[f + 1].split())
            else:
                hyp_text = text[f]
            r8 = loc.locate(hyp_text)
            # top=1 بالحقن المؤقّت على دالّة الترشيح (لا تعديلَ في `locator.py`)
            orig = Locator.candidates
            Locator.candidates = lambda self, hyp, top=1, _o=orig: _o(self, hyp, 1)
            try:
                r1 = loc.locate(hyp_text)
            finally:
                Locator.candidates = orig
            g8 = None if r8 is None else r8["start"]
            g1 = None if r1 is None else r1["start"]
            alts8 = [] if r8 is None else r8.get("alternatives", [])
            ok8 = g8 == f or (g8 is not None and f in alts8)
            ok1 = g1 == f
            print(f"  ▸ {f} رتبة={s['rank']} · top8⇒{g8} ({'✔' if ok8 else '✘'}) · "
                  f"top1⇒{g1} ({'✔' if ok1 else '✘'}) · بدائل={alts8[:4]}")
            if ok8 and not ok1:
                hits.append({"flat": f, "rank": s["rank"], "top8": g8, "top1": g1,
                             "alts": alts8, "hyp": hyp_text,
                             "quality8": None if r8 is None else round(r8["quality"], 4)})
        print(f"# 🎯 ثغراتٌ مقيسة (top8 يُصيب · top1 يُخطئ): {len(hits)}")
        for h in hits:
            print("   ", json.dumps(h, ensure_ascii=False))

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump({"riwaya": args.riwaya, "ranks": {str(k): v for k, v in ranks.items()},
                       "suspects": suspects, "hits": hits}, fh, ensure_ascii=False, indent=1)
        print(f"# كُتب {args.out}")


if __name__ == "__main__":
    main()
