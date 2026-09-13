#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⚖️ نفعُ «الأزواج الحرجة» مقيساً — الوجهُ الثاني من قرارٍ لم يكن له إلّا وجهٌ واحد (‏D-424)

**القرارُ المعلَّقُ على المالك** (‏D-414 · D-416 · D-419): إمّا يُشدَّد حاكمُ اللوحة ليطابق
المشحون، وإمّا يُطفأ `criticalPairsUncertain` في المحرك. و**D-419 سعّر الكلفةَ وحدَها**:
اللوحةُ تُعلن دقّةً أعلى ممّا يحكم به التطبيقُ بـ2.9–3.3 نقطةٍ في بابِ الخطأ الأشيَع.
⇒ **فقرارٌ بنصف ميزان.** وهذا يقيس النصفَ الآخر: **ما الذي يشتريه العلمُ بهذا الثمن؟**

## ما يُقاس — والفرقُ عن بابِ `typo` في D-419
`typo` يقلب حرفاً فيُنتج **غالباً غيرَ كلمة** (‏«رت» · «يبم»)، فالمرآةُ تُخضِرُّه والمحركُ
يشكّ — وذاك ثمنُ شكٍّ في غير محلّه. **أمّا هنا فالمقيسُ أضيقُ وأخطر:** المواضعُ التي لو زلّ
فيها القارئُ حرفاً واحداً **لنطق كلمةً قرآنيّةً أخرى موجودةً في المصحف** (‏لم/لن · من/مع ·
هو/هي). في هذه المواضع **إخضرارُ المرآة ليس تسامحاً بل عمى**: كلمةٌ غيرُ التي في المصحف
تُحسب صحيحةً، والمعنى ينقلب.

شرطُ الرخصة في المحرك (`matches`): `n = max(len(ref), len(hyp)) <= 3 && d <= 1`.
فيُبحَث لكلِّ موضعٍ مرجعيٍّ صورتُه المطبَّعةُ `≤ 3` عن **صورةٍ قرآنيّةٍ أخرى** تستوفي الشرطَ نفسَه.

    python critical_pairs_census.py --all
    python critical_pairs_census.py --riwaya hafs --top 30

## ⚖️ الحدودُ تُقال قبل الأرقام
- **الجوارُ إمكانٌ لا وقوع:** «موضعٌ له جارٌ قرآنيّ» يعني أنّ الزلّةَ **ممكنةٌ** فيه، لا أنّ
  القارئَ يزلّها. فالرقمُ **سقفُ النفع** لا النفعُ المحقَّق — وقياسُ الوقوع يقتضي صوتاً.
- **المقارنةُ على `norm` لا على `variants`:** المحركُ يقارن صورَ الرواية كلَّها، وهذا يقارن
  الصورةَ المطبَّعةَ وحدَها ⇒ قد يفوته جوارٌ يراه المحرك. **فالعدُّ حدٌّ أدنى من هذا الوجه.**
- ⛔ ولا يُشحن بهذا شيء ولا يُغيَّر افتراض: **قياسٌ يُسلَّم للمالك**.
"""
import argparse
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))

import scorer  # noqa: E402
import detect_score  # noqa: E402
from common import load_text  # noqa: E402

RIWAYAT = ("hafs", "warsh", "qalun", "shuba", "douri", "sousi")
CAP = 3   # سقفُ الرخصة المشحون (`short_cap` في المرآة · `n <= 3` في الكوتلن)


def edit1(a, b):
    """أفرقُ بينهما حرفٌ واحدٌ على الأكثر؟ — مرآةُ `_edit(...) <= 1` لسلاسلَ قصيرة."""
    if a == b:
        return False
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:                       # إبدالُ حرف
        return sum(1 for x, y in zip(a, b) if x != y) == 1
    if la > lb:                        # حذفُ حرفٍ من a
        a, b, la, lb = b, a, lb, la
    i = 0
    while i < la and a[i] == b[i]:
        i += 1
    return a[i:] == b[i + 1:]


def census(riw, top=12):
    cfg = detect_score.cfg_for(riw)
    text = load_text(riw)
    forms = collections.Counter()      # الصورةُ المطبَّعة ⇒ تكرارُها في المصحف
    for a in text:
        for w in a.split():
            n = scorer.norm(w, cfg)
            if n:
                forms[n] += 1
    short = [f for f in forms if len(f) <= CAP]
    # الجوارُ يُحسب مرّةً واحدةً لكلِّ صورةٍ لا لكلِّ موضع.
    nbrs = {}
    for f in short:
        nbrs[f] = [g for g in short if edit1(f, g)]

    tot_pos = sum(forms.values())
    short_pos = sum(forms[f] for f in short)
    risk_pos = sum(forms[f] for f in short if nbrs[f])
    pairs = collections.Counter()
    for f in short:
        for g in nbrs[f]:
            if f < g:
                # وزنُ الزوج: أقلُّ الطرفَين تكراراً — فهو حدُّ ما يمكن أن يقع فيه الالتباس.
                pairs[(f, g)] += min(forms[f], forms[g])
    return dict(riwaya=riw, tot=tot_pos, short=short_pos, risk=risk_pos,
                vocab=len(forms), vshort=len(short),
                vrisk=sum(1 for f in short if nbrs[f]), pairs=pairs, top=top,
                forms=forms)


def show(r):
    print(f"\n=== {r['riwaya']} ===")
    print(f"  مواضعُ الكلمات: {r['tot']:,} · منها قصيرةٌ (‏≤{CAP}): **{r['short']:,}** "
          f"({100 * r['short'] / r['tot']:.2f}٪)")
    print(f"  **ومنها ما له جارٌ قرآنيٌّ بحرفٍ واحد: {r['risk']:,}** "
          f"({100 * r['risk'] / r['tot']:.2f}٪ من المصحف · "
          f"{100 * r['risk'] / max(r['short'], 1):.1f}٪ من القصيرات) 🚨")
    print(f"  الصورُ المتمايزة: {r['vocab']:,} · قصيرةٌ {r['vshort']} · "
          f"ولها جارٌ **{r['vrisk']}**")
    print(f"  أثقلُ الأزواج (‏الوزنُ = أقلُّ الطرفَين تكراراً):")
    for (a, b), w in r["pairs"].most_common(r["top"]):
        print(f"     {a} ⇔ {b}  ({w:,} · {r['forms'][a]:,} / {r['forms'][b]:,})")
    print(f"CENSUS\t{r['riwaya']}\t{r['tot']}\t{r['short']}\t{r['risk']}\t{r['vrisk']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--riwaya", choices=RIWAYAT)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--top", type=int, default=12)
    args = ap.parse_args()
    for riw in (RIWAYAT if args.all else (args.riwaya or "hafs",)):
        show(census(riw, args.top))


if __name__ == "__main__":
    main()
