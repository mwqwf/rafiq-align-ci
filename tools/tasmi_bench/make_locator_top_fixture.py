# -*- coding: utf-8 -*-
"""🧭 بصمةُ **إعادةِ ترتيب المرشّحين بالجودة** (البند 3 في `QuranLocator`) — تُولَّد من المصحف
كلِّه بلا صوتٍ ولا شبكة، وتُحفظ في موارد اختبار المحرك.

لماذا: `QuranLocator.TOP = 8` كان يمرّ أخضرَ حين يُجعل **1** (‏دَينُ D-320 · D-324) — أي أنّ
البند 3 («أفضلُ TOP مرشّحين يُحاذَون فعلاً ويُختار أعلاهم جودةً») بلا حارسٍ يعضُّ. وسببُه
معلومٌ: عيّنةُ `QuranLocatorTest` ستّةَ عشرَ آيةً، الأعلى صوتاً فيها هو الصحيحُ دائماً.

والحالةُ المطلوبة وُجدت بالقياس على المصحف كلِّه (`locator_top_probe.py`): **آيةٌ قصيرةٌ نصُّها
داخلَ آيةٍ أطولَ في موضعٍ آخر**. فالتصويتُ يعطي الطويلةَ مثلَ القصيرة (الثلاثيّاتُ نفسُها)
فتسبقها بكسر التعادل أو بترجيح التوالي، ثم **المحاذاةُ وحدَها** تُظهر أنّ الطويلةَ لم تُقرأ:
تغطيتُها للتفريغ ناقصةٌ ⇒ الجودةُ تردُّها. مقيسٌ في المصحف كلِّه: **227 آيةً من 6207**
(‏3.66٪) رتبةُ الصحيح فيها ليست الأولى، و**27** خارجَ الثمانية أصلاً.

  python tools/tasmi_bench/make_locator_top_fixture.py [--check]

⚠️ الأرقامُ من المرآة البايثونية (`locator.py`) — والبصمةُ تُلزم المحركَ بها حرفاً بحرف.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))

import scorer  # noqa: E402
from common import load_text  # noqa: E402
from locator import Locator  # noqa: E402

OUT = os.path.join(ROOT, "engine", "recitation", "src", "test", "resources",
                   "locator_top_fixture.tsv")

# الحالاتُ المقيسةُ على المصحف كلِّه: (الصحيحُ، الأعلى صوتاً الخاطئ، وصفٌ).
# ⛔ لا تُكتب حالةٌ هنا بالظنّ: كلُّ سطرٍ أثبته `locator_top_probe.py --full` على 6207 آية
#    بأنّ `top=8` يُصيب و`top=1` يُخطئ (‏لا موضعَ أو موضعاً آخرَ).
CASES = [
    (294, 261, "آل عمران ٢ نصُّها صدرُ آية الكرسي (البقرة ٢٥٥) — تعادلُ صوتٍ يكسره الأصغرُ فهرساً"),
    (153, 1457, "البقرة ١٤٧ نصُّها ذيلُ يونس ٩٤ — وترجيحُ التوالي يرفع الطويلةَ فوقها"),
]
WINDOW = 2   # آياتٌ قبلَ كلِّ آيةٍ معنيّةٍ وبعدَها (سياقُ التوالي يدخل البصمة كما هو)


def build_subset(flats, n_all):
    keep = sorted({f + d for f in flats for d in range(-WINDOW, WINDOW + 1)
                   if 0 <= f + d < n_all})
    return keep, {f: i for i, f in enumerate(keep)}


def locate_with_top(loc, hyp_text, top):
    orig = Locator.candidates
    Locator.candidates = lambda self, hyp, _t=top, _o=orig: _o(self, hyp, _t)
    try:
        return loc.locate(hyp_text)
    finally:
        Locator.candidates = orig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="تحقّقٌ بلا كتابة")
    args = ap.parse_args()

    cfg = scorer.DEFAULT
    text = load_text("hafs")
    keep, remap = build_subset([f for c in CASES for f in c[:2]], len(text))
    subset = [text[f] for f in keep]
    loc = Locator([a.split() for a in subset], cfg)

    rows = []
    for correct, wrong, why in CASES:
        hyp_text = text[correct]
        core = [w for w in (scorer.norm(x, cfg) for x in hyp_text.split()) if w]
        core = core[loc.strip_preamble(core):]
        cands = loc.candidates(core)
        top1 = cands[0][0]
        r8 = loc.locate(hyp_text)
        r1 = locate_with_top(loc, hyp_text, 1)
        got8 = None if r8 is None else r8["start"]
        got1 = None if r1 is None else r1["start"]
        ok = (top1 == remap[wrong] and got8 == remap[correct] and got1 != remap[correct])
        print(f"{'✅' if ok else '🚨'} {correct}→{remap[correct]} · الأعلى صوتاً "
              f"{top1} (المنتظر {remap[wrong]}) · top8⇒{got8} · top1⇒{got1} · "
              f"الجودة {None if r8 is None else round(r8['quality'], 6)} · {why}")
        if not ok:
            raise SystemExit(f"🚨 الحالةُ لا تتحقّق على العيّنةِ المصغّرة: {correct}")
        rows.append((hyp_text, remap[correct], remap[wrong], r8["quality"],
                     len(r8["anchored"]), why))

    if args.check:
        return
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("# بصمةُ إعادةِ ترتيب المرشّحين بالجودة (QuranLocator البند 3) — "
                 "تُولَّد بـ tools/tasmi_bench/make_locator_top_fixture.py · ⛔ لا تُحرَّر يدوياً\n")
        fh.write("# مصدرُها نصُّ حفصٍ من أصول المستودع؛ الأرقامُ من المرآة locator.py\n")
        fh.write("# A\t<فهرسٌ في العيّنة>\t<فهرسُ المصحف>\t<نصُّ الآية>\n")
        fh.write("# C\t<التفريغ>\t<البدايةُ الصحيحة>\t<الأعلى صوتاً الخاطئ>\t<الجودة>\t"
                 "<عددُ الآيات المحاذاة>\t<الوصف>\n")
        for i, f in enumerate(keep):
            fh.write(f"A\t{i}\t{f}\t{text[f]}\n")
        for hyp, c, w, q, n, why in rows:
            fh.write(f"C\t{hyp}\t{c}\t{w}\t{q:.6f}\t{n}\t{why}\n")
    print(f"# كُتب {OUT} · آياتٌ {len(keep)} · حالاتٌ {len(rows)}")


if __name__ == "__main__":
    main()
