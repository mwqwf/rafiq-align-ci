# -*- coding: utf-8 -*-
"""⚖️ النصفُ الثاني من ميزان «رخصة الكلمة القصيرة» — **ما تكسبه** لا ما تكلّفه (‏D-282).

`short_word_exposure.py` (‏D-277) قاس **التكلفة**: 34–39٪ من مواضع المصحف تقبل كلمةً
قرآنيةً أخرى بسبب الرخصة `(_n <= 3 and _d <= 1)`. وختم بأن ما **تكسبه** الرخصةُ
«لا يُقاس إلا على مخرَجِ تعرّفٍ حقيقيّ» — وهو متعذّرٌ في السحابة (لا صوتَ ولا نموذج).

**وهذا غيرُ صحيح: مخرَجُ التعرّفِ الحقيقيّ مودَعٌ في المستودع.**
`engine/recitation/src/test/resources/parity_fixture.tsv` فيه **212 حالةً** نصُّها
المسموعُ ناتجُ whisper المشحون على صوتٍ حقيقيّ من عيّنة G1 (‏يولّدها
`make_parity_fixture.py` من `work/hyps_ar.json`)، وأحكامُها **مصدَّقةٌ على المحرك نفسِه**
باختبار `RecitationScorerParityTest`. فهي أصغرُ من G1 كلِّها لكنّها **حقيقيةٌ لا مولَّدة**.

ويُضاف إليها `long_anchor_fixture.tsv`: **60 تفريغاً حقيقيّاً** آخرَ من `hyps_shipped_g4.json`.

فيقيس هذا الملفُّ الذراعَ بالذراع على ذلك النصِّ الحقيقيّ:

    أ) `short_cap=3` — المشحون          ج) `short_cap=0` — بلا رخصةٍ البتّة
    ب) `short_cap=2` — ذراعُ D-277

والمقيسُ: **كم كلمةً مرجعيةً تفقد حكمَ CORRECT** إذا ضُيِّقت الرخصة؟ تلك بعينِها هي
الكلماتُ التي تشتريها الرخصةُ بثمنِ التعرّض المقيس في D-277 — لا أكثر.

🔑 **ومفتاحُ قراءة الرقم:** التلاواتُ في الحزمتين **صحيحةٌ** (قرّاءُ مرجعٍ لا متعلّمين)،
فكلُّ اتّهامٍ مؤكَّدٍ فيهما **إنذارٌ كاذب** بلا استثناء، وكلُّ كلمةٍ تنقذها الرخصةُ
**إنذارٌ كاذبٌ مُنع**. فالفائدةُ حقيقيةٌ لا صوريّة — والسؤالُ مقدارُها لا وجودُها.
وتصنيفُ «المسموعُ كلمةٌ قرآنيةٌ أخرى» لا ينفي الفائدةَ هنا، بل يعيّن **أيَّ الإنقاذات
يقع في النافذة نفسِها التي تبتلع زلّةً حقيقيةً لو أخطأ الطالب** — وهو موضعُ المقايضة.

⚠️ ولا يُتّقى شرُّ هذا الفقد بـ«غير متبيَّن»: `_near` يشترط `len(hyp) >= 4`، والكلمةُ
هنا ≤3 ⇒ فالفاقدُ يسقط إلى **اتّهامٍ مؤكَّد** (‏MISSED/SUBSTITUTED) لا إلى تحفّظ.

الضوابط (‏قاعدةُ D-279: حارسٌ لا يسقط على عطبٍ مزروعٍ لا يُصدَّق أخضرُه):
  • **ضابطُ التصديق:** الذراعُ (أ) يجب أن يعيد إنتاج أحكامِ الحزمة المودَعة **حرفاً بحرف**؛
    وتلك الأحكامُ صدّقها المحركُ الحقيقيّ ⇒ فالمقياسُ هنا هو المشحون لا تقريبُه.
  • **الضابطُ السالب (`--control`):** رخصةٌ موسَّعةٌ إلى ≤9 يجب أن تُغيّر أحكاماً (وإلا
    فالعدّادُ ميّت)، وذراعٌ مطابقٌ للمشحون يجب أن يعطي صفرَ فرق.

    python short_word_benefit.py
    python short_word_benefit.py --control --examples 30
"""
import argparse
import collections
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))

import scorer  # noqa: E402

RES = os.path.join(ROOT, "engine", "recitation", "src", "test", "resources")
FIXTURE = os.path.join(RES, "parity_fixture.tsv")
LONG_FIXTURE = os.path.join(RES, "long_anchor_fixture.tsv")
CODE = {scorer.CORRECT: "C", scorer.MISSED: "M", scorer.SUBSTITUTED: "S", scorer.UNCERTAIN: "U"}
CONFIRMED = (scorer.MISSED, scorer.SUBSTITUTED)


def config_for(riwaya, short_cap=3):
    """الإعدادُ المشحون لكلِّ رواية — نفسُه الذي تُبنى به حزمةُ التماثل، بسقفِ رخصةٍ معلَم."""
    return scorer.Config(naql=(riwaya == "warsh"), sila=(riwaya in ("warsh", "qalun")),
                         short_cap=short_cap)


def load_fixture():
    """حالاتُ الحزمة المودَعة: مرجعٌ ومسموعٌ **حقيقيّ** وأحكامٌ صدّقها المحرك."""
    rows = []
    with open(FIXTURE, encoding="utf-8") as fh:
        for row in csv.reader((ln for ln in fh if not ln.startswith("#")), delimiter="\t"):
            if len(row) < 5:
                continue
            rows.append(dict(name=row[0], ref=row[1], hyp=row[2], riwaya=row[3],
                             verdicts=row[4]))
    return rows


def load_long():
    """`long_anchor_fixture.tsv`: 60 تفريغاً **حقيقيّاً** من `hyps_shipped_g4.json`،
    كلٌّ ستُّ آياتٍ متّصلة (‏وسيطُ التسجيل 50 ثانية). الأعمدة: اسم · رواية · مسموع · آياتٌ بـ`|`.

    ⚠️ **حدُّه:** لا أحكامَ مودَعةً فيه ⇒ لا ضابطَ تصديقٍ حالةً بحالة كما في حزمة التماثل،
    وتُحكَم الآياتُ الستُّ مرجعاً واحداً متّصلاً (التطبيقُ يرسيها آيةً آيةً). فهو **يُوسِّع
    عيّنةَ النصِّ الحقيقيّ** ويصلح لفرقِ الذراعين، ولا يُخلط برقمِ الحزمة المصدَّقة.
    """
    rows = []
    with open(LONG_FIXTURE, encoding="utf-8") as fh:
        for line in fh:
            p = line.rstrip("\n").split("\t")
            if len(p) < 4 or not line.strip():
                continue
            ref = " ".join(p[3].split("|"))
            rows.append(dict(name=p[0], ref=ref, hyp=p[2], riwaya=p[1], verdicts=""))
    return rows


def judge(rows, short_cap):
    """أحكامُ كلِّ حالةٍ تحت سقفِ رخصةٍ معيّن — مفتاحُها (اسمُ الحالة، رقمُ الكلمة)."""
    out = {}
    for r in rows:
        cfg = config_for(r["riwaya"], short_cap)
        words = r["ref"].split()
        res = scorer.score(words, r["hyp"], cfg)
        # `words` عناصرُها ثلاثيّاتُ (الموضع، الحكم، المسموع) — والمسموعُ يُحفظ لأنّه الدليل.
        for i, (w, v) in enumerate(zip(words, res["words"])):
            out[(r["name"], i)] = (w, v[1], scorer.norm(w, cfg), v[2])
    return out


def validate(rows, base):
    """ضابطُ التصديق: الذراعُ المشحون يطابق أحكامَ الحزمة المصدَّقةَ على المحرك حرفاً بحرف."""
    total = bad = 0
    for r in rows:
        for i, ch in enumerate(r["verdicts"]):
            v = base.get((r["name"], i))
            if v is None:
                continue
            total += 1
            if CODE.get(v[1], "?") != ch:
                bad += 1
    return total, bad


def diff(base, arm):
    """الكلماتُ التي كانت CORRECT في المشحون وسقطت في الذراع — ومصيرُها."""
    lost, moved = [], collections.Counter()
    for k, (w, v, n, heard) in base.items():
        v2 = arm[k][1]
        if v == v2:
            continue
        moved[(CODE.get(v, "?"), CODE.get(v2, "?"))] += 1
        if v == scorer.CORRECT and v2 in CONFIRMED:
            lost.append((k, w, n, heard, v2))
    return lost, moved


def mushaf_vocab():
    """مفرداتُ المصحف مطبَّعةً (الروايات الثلاث) — بها يُصنَّف ما «تنقذه» الرخصة.

    والتلاوةُ هنا صحيحةٌ ⇒ فكلُّ إنقاذٍ إنذارٌ كاذبٌ مُنع. لكنّ الإنقاذ الذي **مسموعُه كلمةٌ
    قرآنيةٌ أخرى** يقع في النافذة عينِها التي كانت ستبتلع **زلّةَ تلاوةٍ حقيقية** لو أخطأ
    الطالبُ في ذلك الموضع — فهو الوجهُ الآخرُ لتعرُّضِ D-277 لا وجهٌ ثالث. وهذا التصنيفُ
    يقيس **أيُّ الإنقاذات مقايضةٌ وأيُّها ربحٌ خالص**.
    """
    from common import load_text  # noqa: E402  (يُستورد هنا كي تعمل الأداةُ بلا نصٍّ لو تعذّر)
    vocab = collections.Counter()
    for riw in ("hafs", "warsh", "qalun"):
        cfg = config_for(riw)
        for aya in load_text(riw):
            for w in aya.split():
                n = scorer.norm(w, cfg)
                if n:
                    vocab[n] += 1
    return vocab


def classify(lost, vocab):
    """يقسم ما أنقذته الرخصةُ ثلاثةَ أقسام: كلمةٌ قرآنيةٌ أخرى · رمزُ وقف · فرقُ رسمٍ/تعرّف."""
    buckets = collections.defaultdict(list)
    for _, w, n, heard, _ in lost:
        h = heard or ""
        if not n:
            buckets["رمزُ وقفٍ (لا كلمةَ أصلاً)"].append((w, n, h))
        elif h in vocab:
            buckets["🚨 المسموعُ **كلمةٌ قرآنيةٌ أخرى** ⇒ ابتلاعُ زلّةٍ محتملة"].append((w, n, h))
        else:
            buckets["فرقُ رسمٍ أو خطأُ تعرّفٍ لا يقابل كلمةً"].append((w, n, h))
    return buckets


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--examples", type=int, default=25, help="عددُ الكلمات الفاقدة المعروضة")
    ap.add_argument("--control", action="store_true", help="تشغيلُ الضابطِ السالب أيضاً")
    ap.add_argument("--corpus", choices=("parity", "long", "both"), default="both",
                    help="حزمةُ التماثل المصدَّقة · تفريغاتُ المرساة الطويلة · كلتاهما")
    args = ap.parse_args()

    rows = []
    if args.corpus in ("parity", "both"):
        rows += load_fixture()
    if args.corpus in ("long", "both"):
        rows += load_long()
    by_riw = collections.Counter(r["riwaya"] for r in rows)
    print(f"الحزمةُ المودَعة: {len(rows)} حالةً — " +
          " · ".join(f"{k} {v}" for k, v in sorted(by_riw.items())))

    base = judge(rows, 3)
    words_n = len(base)
    short_n = sum(1 for _, _, n, _ in base.values() if len(n) <= 3)
    print(f"كلماتٌ مرجعية: {words_n} — منها قصيرةٌ (‏≤3 بعد التطبيع): {short_n} "
          f"({100*short_n/max(words_n,1):.1f}٪)")

    total, bad = validate(rows, base)
    print(f"\n✅ ضابطُ التصديق: {total - bad}/{total} حكماً مطابقاً لأحكامِ الحزمة "
          f"(المصدَّقةِ على المحرك) — انحرافٌ {bad}")
    if bad:
        print("🚨 انحرافٌ في الذراع المشحون ⇒ **كلُّ ما تحته ساقط**. أوقف واقرأ السبب.")
        return 1

    conf0 = sum(1 for _, v, _, _ in base.values() if v in CONFIRMED)
    print(f"أرضيّةُ الإنذار الكاذب في المشحون (التلاواتُ صحيحةٌ ⇒ كلُّ اتّهامٍ كاذب): "
          f"{conf0}/{words_n} ({100*conf0/max(words_n,1):.2f}٪)")
    vocab = mushaf_vocab()
    print(f"مفرداتُ المصحف للتصنيف: {len(vocab)} صورةً مطبَّعة\n")

    for cap, name in ((2, "ب) رخصةٌ ≤2"), (0, "ج) بلا رخصةٍ البتّة")):
        arm = judge(rows, cap)
        lost, moved = diff(base, arm)
        conf = sum(1 for _, v, _, _ in arm.values() if v in CONFIRMED)
        print(f"=== {name} (‏short_cap={cap}) ===")
        print(f"  إنذاراتٌ كاذبةٌ جديدة (‏CORRECT ⇒ اتّهامٌ مؤكَّد): **{len(lost)}** من {words_n} "
              f"({100*len(lost)/max(words_n,1):.2f}٪)")
        print(f"  الإنذارُ الكاذب جملةً: {100*conf0/max(words_n,1):.2f}٪ ⇐ "
              f"{100*conf/max(words_n,1):.2f}٪ (‏{100*(conf-conf0)/max(words_n,1):+.2f} نقطة)")
        print("  حركةُ الأحكام: " +
              ("، ".join(f"{a}⇒{b}×{c}" for (a, b), c in moved.most_common()) or "لا شيء"))
        if lost and args.examples:
            print("  ما تشتريه الرخصةُ (المرجعُ ⇐ ما سمعه whisper فعلاً)، مصنَّفاً:")
            for title, items in sorted(classify(lost, vocab).items(), key=lambda kv: -len(kv[1])):
                print(f"    • {title}: {len(items)}")
                for w, n, h in items[:args.examples]:
                    print(f"        {w}  («{n}»)  ⇐ سُمعت «{h}»")
        print()

    if args.control:
        print("=== الضابطُ السالب ===")
        same = judge(rows, 3)
        _, moved_same = diff(base, same)
        print(f"  ذراعٌ مطابقٌ للمشحون (‏cap=3): فرقٌ {sum(moved_same.values())} "
              f"(يجب أن يكون 0){' ✅' if not moved_same else ' 🚨'}")
        wide = judge(rows, 9)
        lost_w, moved_w = diff(base, wide)
        n_w = sum(moved_w.values())
        print(f"  رخصةٌ موسَّعةٌ (‏cap=9): تغيّر {n_w} حكماً "
              f"(يجب أن يكون > 0 وإلا فالعدّادُ ميّت){' ✅' if n_w else ' 🚨'}")
        print("    حركتُها: " + ("، ".join(f"{a}⇒{b}×{c}" for (a, b), c in moved_w.most_common())
                                 or "لا شيء"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
