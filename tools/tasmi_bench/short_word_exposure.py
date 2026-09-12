# -*- coding: utf-8 -*-
"""📏 قياسُ تعرُّضِ الكلمةِ القصيرة — كم موضعاً مرجعيّاً يقبل **كلمةً قرآنيةً أخرى**؟

الخلفيّة: في `scorer._matches` (ومرآتُها في `RecitationScorer.matches`) رخصةٌ
أُضيفت 2026-09-05 بأمرِ المالك «أقلَّ حساسية»:

    if (_d * cfg.match_den <= cfg.match_num * _n) or (_n <= 3 and _d <= 1)

فالكلمةُ التي أقصرُ صورةٍ مقبولةٍ لها ≤ 3 أحرفٍ **تحتمل حرفاً كاملاً**. وهذا
القياسُ يجيب سؤالاً واحداً بلا صوتٍ ولا نموذج: **كم موضعاً في المصحف تُقبل فيه
كلمةٌ قرآنيةٌ أخرى مكانَ الكلمة الصحيحة؟** — أي كم خطأَ تلاوةٍ حقيقيٍّ تبتلعه الرخصة.

لا يقيس هذا ما **تكسبه** الرخصة (احتمالَ فروقِ رسمِ المصحف عمّا يكتبه whisper)؛
ذاك لا يُقاس إلا على مخرَجِ تعرّفٍ حقيقيّ. فالمخرَجُ هنا **نصفُ الميزان: التكلفة**.

    python short_word_exposure.py              # الروايات الثلاث
    python short_word_exposure.py --riwaya hafs --examples 20
"""
import argparse
import collections
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "../alignment")

import scorer  # noqa: E402
from common import load_text  # noqa: E402

RIWAYAT = ("hafs", "warsh", "qalun")


def config_for(riwaya):
    """الإعدادُ المشحون لكلِّ رواية — هو نفسُه الذي يبني به `make_parity_fixture` حزمةَ التماثل."""
    return scorer.Config(naql=(riwaya == "warsh"), sila=(riwaya in ("warsh", "qalun")))


def accepted_forms(word, cfg):
    return tuple(f for f in scorer._riwaya_forms(scorer.variants(word, cfg), cfg) if f)


def measure(riwaya, examples=0):
    cfg = config_for(riwaya)
    ayat = load_text(riwaya)

    # مفرداتُ المصحف: الصورةُ الأولى لكلِّ كلمة — فالبديلُ الذي قد ينطقه القارئ كلمةٌ قرآنيةٌ
    # حقيقيةٌ لا صورةً من صورِ التسامح.
    vocab = collections.Counter()
    for aya in ayat:
        for w in aya.split():
            fs = accepted_forms(w, cfg)
            if fs:
                vocab[fs[0]] += 1
    short_vocab = [v for v in vocab if len(v) <= 3]

    # لكلِّ صورةٍ قصيرة: أيُّ كلماتِ المصحف تُقبل مكانَها بالرخصة (‏_n ≤ 3 و _d ≤ 1)؟
    accepts = {}
    for r in short_vocab:
        alts = [h for h in short_vocab if h != r and scorer._edit(r, h) <= 1]
        if alts:
            accepts[r] = sorted(alts, key=lambda h: -vocab[h])

    occ = licensed = exposed = hit_ayat = 0
    band = collections.Counter()
    hot = collections.Counter()
    for aya in ayat:
        touched = False
        for w in aya.split():
            occ += 1
            fs = accepted_forms(w, cfg)
            if not fs:
                band[0] += 1          # رمزُ وقفٍ يُطبَّع إلى فراغ — يبتلعه الدمجُ ١↔٢
                continue
            band[min(min(len(f) for f in fs), 7)] += 1
            if not any(len(f) <= 3 for f in fs):
                continue
            licensed += 1
            alt = next((f for f in fs if accepts.get(f)), None)
            if alt:
                exposed += 1
                touched = True
                hot[alt] += 1
        if touched:
            hit_ayat += 1

    return dict(riwaya=riwaya, occ=occ, licensed=licensed, exposed=exposed,
                ayat=len(ayat), hit_ayat=hit_ayat, band=band, accepts=accepts,
                vocab=vocab, hot=hot, examples=examples)


def report(res):
    r = res
    print(f"\n=== {r['riwaya']} ===")
    print(f"مواضعُ مرجعية: {r['occ']}")
    print(f"  تحت رخصةِ القصيرة (أقصرُ صورةٍ ≤3): {r['licensed']} ({100*r['licensed']/r['occ']:.2f}٪)")
    print(f"  يقبل كلمةً قرآنيةً أخرى:            {r['exposed']} ({100*r['exposed']/r['occ']:.2f}٪)")
    print(f"  آياتٌ فيها موضعٌ كهذا: {r['hit_ayat']}/{r['ayat']} ({100*r['hit_ayat']/r['ayat']:.1f}٪)")
    print("  انقطاعُ المِسطرة (أقصرُ صورةٍ مقبولة × ما تحتمله):")
    for L in range(8):
        if L == 0:
            note = "رمزُ وقفٍ — لا يُتّهم"
        elif L <= 3:
            note = "حرفٌ واحد ← رخصةُ القصيرة"
        elif L == 4:
            note = "**لا شيء** ⛔ أشدُّ نطاقٍ في المِسطرة"
        else:
            note = "حرفٌ واحد ← عتبةُ الخُمس"
        print(f"    {L if L < 7 else '7+':>3} : {r['band'][L]:6d}  {note}")
    if r["examples"]:
        print(f"  أمثلة (الأكثرُ وروداً، وما يُقبل مكانَها):")
        for form, _ in r["hot"].most_common(r["examples"]):
            alts = r["accepts"].get(form, [])[:6]
            shown = "، ".join(f"{h}(×{r['vocab'][h]})" for h in alts)
            print(f"    {form:5s} (×{r['vocab'][form]:5d}) ← {shown}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--riwaya", choices=RIWAYAT, help="رواية واحدة (الافتراض: الثلاث)")
    ap.add_argument("--examples", type=int, default=12, help="عددُ الأمثلة المعروضة")
    args = ap.parse_args()
    for riwaya in ([args.riwaya] if args.riwaya else RIWAYAT):
        report(measure(riwaya, args.examples))


if __name__ == "__main__":
    main()
