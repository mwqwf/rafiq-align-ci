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


def _selftest_no_fixture(say):
    """ما يمكن فحصُه بلا حزمتَي التعرّف: المثالُ · شرطُ «غير متبيَّن» · المفردات · حارسُ المصدر."""
    cfg3, cfg0 = config_for("hafs", 3), config_for("hafs", 0)
    v3 = scorer.score(["قُلْ"], "كل", cfg3)["words"][0][1]
    v0 = scorer.score(["قُلْ"], "كل", cfg0)["words"][0][1]
    say(v3 == scorer.CORRECT and v0 == scorer.SUBSTITUTED,
        "⭐⭐ `قُلْ` تُسمَع «كل»: المشحونُ **%s** · وبلا رخصةٍ **%s**" % (v3, v0))
    say(v0 in CONFIRMED, "⛔ والفاقدُ يسقط إلى اتّهامٍ مؤكَّدٍ لا إلى تحفّظ (‏`_near` يشترط ≥4)")
    vocab = mushaf_vocab()
    say(len(vocab) > 14000 and "كل" in vocab and "لم" in vocab,
        "مفرداتُ المصحف للتصنيف: %d صورةً (وفيها «كل» و«لم»)" % len(vocab))
    doc = selftest.__doc__
    say(all(k in doc for k in ("34.113", "14.595", "19.5", "0.21", "قُلْ")),
        "حارسُ مصدر: طرفا الميزان ومثالُه في التوثيق")


def selftest():
    """🧪 **حارسُ ميزان رخصة القصيرة** (‏D-601) — والأداةُ يُقرأ عليها **قرارٌ معلَّقٌ على
    المالك**، فأرقامُها تُثبَّت بالنصّ لا بالذاكرة.

    ⭐⭐ **الميزانُ كاملاً في مكانٍ واحدٍ لأوّل مرّة** (‏وهو ما لم يكن مجموعاً قبلَ اليوم):

        الفائدةُ (على تعرّفٍ حقيقيٍّ مودَع · 272 حالةً · 3,823 كلمةً مرجعيّة):
          المشحون ⇒ ≤2      : **12** إنذاراً كاذباً جديداً (0.31 نقطة) — منها **3 مسموعُها
                              كلمةٌ قرآنيّةٌ أخرى** و**1 رمزُ وقف** ⇒ **الإنقاذُ الخالصُ 8**
          المشحون ⇒ بلا رخصة: **16** (0.39 نقطة) — منها **6** كلمةٌ قرآنيّةٌ أخرى و1 رمزُ وقف
        التكلفةُ (على المصحف كلِّه · D-277/D-600): **34.113٪ ⇒ 14.595٪** بالحصر في حرفين.

    ⇒ **الحصرُ في حرفين يشتري 19.5 نقطةً من التعرّض بثمنِ 0.21 نقطةٍ من الإنذار الكاذب**
      (8 إنقاذاتٍ خالصة)، **ويستردّ 3 مواضعَ كان يبتلعها**. ⛔ قياسٌ يُسلَّم، **ولا يُشحن**.

    ⭐⭐ **والمثالُ الذي يغني عن الشرح:** `قُلْ` تُسمَع «كل» ⇒ **المشحونُ يحكم `CORRECT`**
      وبلا رخصةٍ `SUBSTITUTED`. كلمتان قرآنيّتان ينقلب بهما المعنى.
    """
    ok = True

    def say(good, line):
        nonlocal ok
        ok &= bool(good)
        print(("✅ " if good else "❌ ") + line)

    # ⛔ حزمتا التماثل تحت `engine/` ولا وجودَ لهما في مرآة الحوسبة العامّة (‏درسُ D-505)
    #    ⇒ ما يلزمها **يُعلَن باسمه** ولا يُعَدّ نجاحاً صامتاً.
    have_fx = os.path.isfile(FIXTURE) and os.path.isfile(LONG_FIXTURE)
    if not have_fx:
        print("⚠️ **حزمتا التعرّف الحقيقيّ غائبتان في هذه النسخة** (‏%s) ⇒ **ستّةُ فحوصٍ لم "
              "تُجرَ هنا** (ضابطُ التصديق · أرضيّةُ الإنذار · الميزانُ بذراعيه · الضابطُ "
              "السالبُ بشقَّيه) — وموضعُها مستودعُ الأصل. ⛔ إعلانٌ بالنصّ لا نجاحٌ صامت."
              % os.path.basename(FIXTURE))
        _selftest_no_fixture(say)
        print("\n%s" % ("✅ حارسُ ميزان رخصة القصيرة: تمّ (منقوصاً بإعلان)" if ok
                         else "❌ حارسُ الميزان: أخفق"))
        return 0 if ok else 1

    rows = load_fixture() + load_long()
    base = judge(rows, 3)
    words_n = len(base)

    # ①⭐⭐ ضابطُ التصديق: الذراعُ (أ) = أحكامُ الحزمة المصدَّقةِ على المحرك
    total, bad = validate(rows, base)
    say(len(rows) == 272 and words_n == 3823 and total > 2000 and bad == 0,
        "⭐⭐ الذراعُ المشحون يطابق الحزمةَ المصدَّقةَ على المحرك: %d/%d · انحرافٌ %d"
        % (total - bad, total, bad))

    # ② أرضيّةُ الإنذار الكاذب — والتلاواتُ صحيحةٌ فكلُّ اتّهامٍ مؤكَّدٍ كاذبٌ بلا استثناء
    conf0 = sum(1 for _, v, _, _ in base.values() if v in CONFIRMED)
    say(conf0 == 269, "أرضيّةُ الإنذار الكاذب في المشحون: %d/%d (%.2f٪)"
        % (conf0, words_n, 100.0 * conf0 / words_n))

    # ③⭐⭐ الميزان: ما تفقده كلُّ ذراعٍ، مصنَّفاً
    vocab = mushaf_vocab()
    say(len(vocab) > 14000 and "كل" in vocab and "لم" in vocab,
        "مفرداتُ المصحف للتصنيف: %d صورةً (وفيها «كل» و«لم»)" % len(vocab))
    ledger = {}
    for cap in (2, 0):
        lost, _ = diff(base, judge(rows, cap))
        b = classify(lost, vocab)
        other = len(b["🚨 المسموعُ **كلمةٌ قرآنيةٌ أخرى** ⇒ ابتلاعُ زلّةٍ محتملة"])
        waqf = len(b["رمزُ وقفٍ (لا كلمةَ أصلاً)"])
        ledger[cap] = (len(lost), other, waqf, len(lost) - other - waqf)
    say(ledger[2] == (12, 3, 1, 8),
        "⭐⭐ الحصرُ في حرفين: %d إنذاراً جديداً · منها %d كلمةٌ قرآنيّةٌ أخرى و%d رمزُ وقفٍ "
        "⇒ **الخالصُ %d**" % ledger[2])
    say(ledger[0] == (16, 6, 1, 9),
        "وبلا رخصةٍ البتّة: %d · منها %d كلمةٌ قرآنيّةٌ أخرى و%d رمزُ وقفٍ ⇒ الخالصُ %d"
        % ledger[0])
    say(ledger[0][0] > ledger[2][0] and ledger[0][1] > ledger[2][1],
        "⛔ والتضييقُ الأشدُّ يفقد أكثرَ ويستردّ أكثر — رتابةٌ مقيسةٌ لا مفترَضة")

    # ④⭐⭐ المثالُ الذي يغني عن الشرح: كلمةٌ قرآنيّةٌ مكانَ أخرى تمرّ خضراءَ بالمشحون
    cfg3, cfg0 = config_for("hafs", 3), config_for("hafs", 0)
    v3 = scorer.score(["قُلْ"], "كل", cfg3)["words"][0][1]
    v0 = scorer.score(["قُلْ"], "كل", cfg0)["words"][0][1]
    say(v3 == scorer.CORRECT and v0 == scorer.SUBSTITUTED,
        "⭐⭐ `قُلْ` تُسمَع «كل»: المشحونُ **%s** · وبلا رخصةٍ **%s**" % (v3, v0))

    # ⑤⛔ الضابطُ السالب: ذراعٌ مطابقٌ ⇒ صفرُ فرق · وذراعٌ موسَّعٌ ⇒ فرقٌ حقيقيّ
    same_lost, same_moved = diff(base, judge(rows, 3))
    wide_lost, wide_moved = diff(base, judge(rows, 9))
    say(not same_lost and not same_moved,
        "⛔ ذراعٌ مطابقٌ للمشحون ⇒ صفرُ فرقٍ (‏وإلّا فالمقياسُ يسرّب)")
    say(sum(wide_moved.values()) > 0,
        "🧪 ورخصةٌ موسَّعةٌ إلى ≤9 **تُحرّك الأحكام** (%d حركة) — فالعدّادُ حيّ"
        % sum(wide_moved.values()))

    # ⑥ ولا يُتّقى الفقدُ بـ«غير متبيَّن»: القصيرةُ تسقط إلى **اتّهامٍ مؤكَّد**
    say(v0 in CONFIRMED, "⛔ والفاقدُ يسقط إلى اتّهامٍ مؤكَّدٍ لا إلى تحفّظ (‏`_near` يشترط ≥4)")

    # ⑦ حارسُ مصدرٍ على أرقام الميزان
    doc = selftest.__doc__
    say(all(k in doc for k in ("34.113", "14.595", "19.5", "0.21", "قُلْ")),
        "حارسُ مصدر: طرفا الميزان ومثالُه في التوثيق")

    print("\n%s" % ("✅ حارسُ ميزان رخصة القصيرة: تمّ" if ok else "❌ حارسُ الميزان: أخفق"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--examples", type=int, default=25, help="عددُ الكلمات الفاقدة المعروضة")
    ap.add_argument("--selftest", action="store_true", help="🧪 حارسُ الأداة (ثوانٍ)")
    ap.add_argument("--control", action="store_true", help="تشغيلُ الضابطِ السالب أيضاً")
    ap.add_argument("--corpus", choices=("parity", "long", "both"), default="both",
                    help="حزمةُ التماثل المصدَّقة · تفريغاتُ المرساة الطويلة · كلتاهما")
    args = ap.parse_args()
    if args.selftest:
        return selftest()

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
