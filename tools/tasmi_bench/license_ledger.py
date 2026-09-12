# -*- coding: utf-8 -*-
"""📒 **دفترُ حسابِ رخصِ المِسطرة** — كلُّ رخصةٍ في بابِ القبول، بعملةٍ واحدةٍ يقارن بها المالك.

الخلفيّة: بابُ القبول في الحاكم (`RecitationScorer.matches` ومرآتُه `scorer._matches`،
ومعهما `norm`/`variants`/`_riwaya_forms`) ليس قاعدةً واحدةً بل **حزمةَ رخصٍ** تراكمت
واحدةً بعد أخرى: عتبةُ الخُمس · رخصةُ الكلمة القصيرة (‏≤3) · الخنجريّةُ الاختيارية ·
مدُّ الخنجريّة (‏D-274/275) · صلةُ ۦ/ۥ · النقلُ وصلةُ الميم في الروايتين · ے⇒ي.

وقد وُزنت **واحدةٌ منها فقط** وزناً كاملاً — رخصةُ القصيرة (‏D-277 · D-282 · D-284 · D-285) —
وعليها قرارٌ معلَّقٌ عند المالك. وسؤالُ هذا الملفّ: **وأخواتُها؟** فلا معنى لقبول رخصةٍ
أو ردِّها بمعزلٍ عن جاراتها في البابِ نفسِه: قد تكون في الحزمة رخصةٌ أغلى ثمناً وأقلَّ
فائدةً من التي يتردّد فيها، فيكون ترتيبُ الأولويات مقلوباً.

## العملةُ الواحدة — طرفا الميزان لكلِّ رخصة

    الفائدة (أ) · كم موضعاً في المصحف كلِّه **ينقلب إنذاراً كاذباً** لو أُلغيت الرخصة؟
                  (‏تلاوةٌ صحيحةٌ بروايتها، والمسموعُ صورةُ whisper الحتميّة لكلمتها)
    التكلفة (ب) · كم **زلّةً روائيةً حقيقيةً** تبتلعها الرخصةُ فلا تُكشف؟
                  (‏مرجعُ رواية E والمسموعُ صورةُ الكلمة الموازية من رواية S)

فلكلِّ رخصةٍ سعرٌ صريح: **كم زلّةً نعمى عنها ثمناً لكلِّ إنذارٍ كاذبٍ نمنعه.** وبهذا
يُقارَن التفّاحُ بالتفّاح: رخصةُ القصيرة وخنجريّةُ D-276 وصلةُ الميم في جدولٍ واحد.

## لِمَ المقياسُ هنا **زوجيّ** (كلمةٌ إلى كلمة) لا حكمُ آيةٍ كاملة
البابُ المفحوصُ `_matches` يعمل على الزوج (صورُ المرجع، المسموع) وحدَه؛ فالقياسُ الزوجيُّ
يصيب موضعَ السؤال بلا وسائط. والمحاذاةُ وحارسُ الانهيار طبقتان **فوقَه** تُخفيان أثرَه
ولا تُنشئانه (‏الحارسُ يحوّل اتّهاماً إلى «غير متبيَّن»، والمحاذاةُ قد تزيح موضعاً).
⇒ أرقامُ (ب) هنا **سقفُ** ما يمكن كشفُه، وأرقامُ (أ) **سقفُ** ما يمكن منعُه.

🧪 **وضابطُ التصديق يقيس هذا الفارق بدل أن يفترضه:** ذراعُ `short_cap=2` قِيس على
**المحرك نفسِه** بالمحاذاة وحارسِ الانهيار في D-285 (‏+48 زلّةً على الاتّجاهات الستّة،
وصفرُ انقلابٍ في الأرضيّة). فإن أعاد هذا الملفُّ للذراع نفسِه رقماً مطابقاً أو أعلى قليلاً
بقدرِ ما تبتلعه الطبقاتُ الفوقيّة، فالعدّادُ مصدَّقٌ على قياسٍ محرَكيٍّ مستقلّ.

⚠️ **مصدرُ الأرقام:** المرآةُ البايثونية — وهي في بابِ القبول **مصدَّقةٌ على المحرك**
(‏D-279: 2,408/2,408 حالةً حرفاً بحرف · D-285: أعادت أرقامَ D-281 المحرَكيّة بلا فرق).
والتوليدُ دائماً بالإعدادِ **المشحون** والفحصُ بالإعدادِ المعطوب ⇒ لا دائريّة (‏قاعدةُ `parity_full`).

    python license_ledger.py --control      # 🧪 الضوابطُ أوّلاً (موجَبٌ وسالب)
    python license_ledger.py                # المصحفُ كلُّه · كلُّ الرخص
    python license_ledger.py --examples 6   # مع أمثلةٍ لكلِّ رخصة
"""
import argparse
import itertools
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))

import scorer  # noqa: E402
import parity_full as P  # noqa: E402  (‏whisper_forms + config_for — مصدرٌ واحدٌ للقاعدة)
from common import load_text  # noqa: E402

RIWAYAT = ("hafs", "warsh", "qalun")


def shipped(riwaya):
    """الإعدادُ المشحون لكلِّ رواية — نفسُه الذي تُبنى به حزمةُ التماثل."""
    return P.config_for(riwaya)


def arm(riwaya, **kw):
    """إعدادُ الفحص: المشحونُ وقد أُلغيت منه رخصةٌ واحدة."""
    base = dict(naql=(riwaya == "warsh"), sila=(riwaya in ("warsh", "qalun")))
    base.update(kw)
    return scorer.Config(**base)


# الرخصُ الموزونة: (المفتاح، الاسم، إعدادُ الإلغاء، الرواياتُ التي تعنيها)
LICENSES = (
    ("short2",  "رخصةُ القصيرة تضيق ≤2 (‏ذراعُ D-285)", dict(short_cap=2),          RIWAYAT),
    ("short0",  "رخصةُ القصيرة تُلغى بالكلّية",          dict(short_cap=0),          RIWAYAT),
    ("dagger",  "الخنجريّةُ الاختيارية (‏D-276)",         dict(dagger_optional=False), RIWAYAT),
    ("madd",    "مدُّ الخنجريّة `ىٰ`/`اٰ` (‏D-274/275)",   dict(dagger_madd=False),     RIWAYAT),
    ("khanj",   "الخنجريّةُ تُنطق ألفاً",                 dict(khanjariya=False),      RIWAYAT),
    ("marksila", "صلةُ ۦ/ۥ المرسومة (‏D-248)",           dict(mark_sila=False),       RIWAYAT),
    ("naql",    "النقلُ (ورشٌ وحدَه)",                    dict(naql=False),            ("warsh",)),
    ("sila",    "صلةُ ميم الجمع (ورشٌ وقالون)",          dict(sila=False),            ("warsh", "qalun")),
    ("yehb",    "ے ⇒ ي (رسمُ الروايتين)",               dict(strip_yeh_barree=False), RIWAYAT),
    ("sixth",   "العتبةُ تضيق: الخُمس ⇒ السدس",          dict(match_den=6),           RIWAYAT),
)


def accepts(cfg, raw, hyp):
    """هل يقبل بابُ القبول هذا المسموعَ لهذه الكلمةِ المرجعية بهذا الإعداد؟"""
    forms = tuple(f for f in scorer._riwaya_forms(scorer.variants(raw, cfg), cfg) if f)
    if not forms:
        return True          # رمزُ وقفٍ أو ما يُطبَّع فراغاً: ليس موضعَ حكم
    return scorer._matches(forms, hyp, cfg)


def prepare(limit=0):
    """لكلِّ رواية: الرموزُ الخام · صورةُ whisper المشحونة لكلِّ رمز · مواضعُ الكلمات الحقيقية.

    الصورةُ المختارة هي **الأبعدُ عن الرسم** — أقربُ ما يكتبه whisper فعلاً (قاعدةُ D-279).
    """
    out = {}
    for r in RIWAYAT:
        cfg = shipped(r)
        rows = []
        ayat = load_text(r)
        if limit:
            ayat = ayat[:limit]
        for ayah in ayat:
            toks = ayah.split()
            nw = [scorer.norm(x, cfg) for x in toks]
            ww = [P.whisper_forms(x, cfg)[-1] if n else "" for x, n in zip(toks, nw)]
            real = [i for i, x in enumerate(nw) if x]
            rows.append((toks, ww, real))
        out[r] = rows
    return out


def population_a(text):
    """أزواجُ التلاوةِ الصحيحة: (رواية، الكلمةُ الخام، صورتُها المسموعة)."""
    for r in RIWAYAT:
        for toks, ww, real in text[r]:
            for i in real:
                yield r, toks[i], ww[i]


def population_b(text):
    """أزواجُ الزلّة الروائية: مرجعُ E والمسموعُ صورةُ الكلمةِ الموازية من S (حيث تختلفان)."""
    for e, s in itertools.permutations(RIWAYAT, 2):
        rows_e, rows_s = text[e], text[s]
        for (toks_e, ww_e, real_e), (_, ww_s, real_s) in zip(rows_e, rows_s):
            if len(real_e) != len(real_s) or not real_e:
                continue      # آيةٌ لا تُحاذى كلمةً بكلمة
            for ie, isx in zip(real_e, real_s):
                if ww_s[isx] == ww_e[ie] or not ww_s[isx]:
                    continue  # لا زلّةَ: الروايتان تتّفقان في هذه الكلمة
                yield e, s, toks_e[ie], ww_s[isx]


def measure(text, examples=0):
    pa = list(population_a(text))
    pb = list(population_b(text))

    ship = {r: shipped(r) for r in RIWAYAT}
    # الأساسُ المشحون: يجب أن يقبل كلَّ (أ) — وما لا يقبله أرضيّةُ اتّهامٍ كاذبٍ قائمةٌ اليوم.
    base_a = [(r, raw, hyp) for r, raw, hyp in pa if not accepts(ship[r], raw, hyp)]
    base_b_blind = [(e, s, raw, hyp) for e, s, raw, hyp in pb if accepts(ship[e], raw, hyp)]

    print("👥 المجتمعان (المصحفُ كلُّه):")
    print("   أ · تلاوةٌ صحيحة: %d زوجٍ (الروايات الثلاث)" % len(pa))
    print("      ⇒ أرضيّةُ الاتّهام الكاذب بالمشحون: **%d**" % len(base_a))
    print("   ب · زلّةٌ روائية: %d زوجٍ على الاتّجاهات الستّة" % len(pb))
    print("      ⇒ يبتلعها المشحون (عمىً): **%d** (%.2f٪) · يكشف %d"
          % (len(base_b_blind), 100.0 * len(base_b_blind) / max(len(pb), 1),
             len(pb) - len(base_b_blind)))
    print()

    rows = []
    for key, name, kw, riws in LICENSES:
        cfgs = {r: (arm(r, **kw) if r in riws else ship[r]) for r in RIWAYAT}
        lost, lost_ex = 0, []
        for r, raw, hyp in pa:
            if r in riws and accepts(ship[r], raw, hyp) and not accepts(cfgs[r], raw, hyp):
                lost += 1
                if len(lost_ex) < examples:
                    lost_ex.append("%s: %s ⇜ «%s»" % (r, raw, hyp))
        gain, gain_ex = 0, []
        for e, s, raw, hyp in base_b_blind:
            if e in riws and not accepts(cfgs[e], raw, hyp):
                gain += 1
                if len(gain_ex) < examples:
                    gain_ex.append("%s⇜%s: %s ⇜ «%s»" % (e, s, raw, hyp))
        rows.append((key, name, lost, gain, lost_ex, gain_ex))

    w = max(len(n) for _, n, *_ in rows) + 2
    print("📒 الدفتر — لكلِّ رخصةٍ: ما تمنعه من إنذارٍ كاذب · ما تُعمي عنه من زلّة · السعر")
    print("%-*s %12s %12s %14s" % (w, "الرخصة (إلغاؤها)", "إنذارٌ كاذب", "زلّةٌ تُكشف", "زلّة/إنذار"))
    for key, name, lost, gain, _, _ in sorted(rows, key=lambda x: -x[3]):
        price = ("%.2f" % (gain / lost)) if lost else ("∞" if gain else "—")
        print("%-*s %12d %12d %14s" % (w, name, lost, gain, price))
    print()
    print("   «إنذارٌ كاذب» = مواضعُ تلاوةٍ صحيحةٍ تنقلب اتّهاماً لو أُلغيت الرخصة ⇒ فائدتُها.")
    print("   «زلّةٌ تُكشف»  = زلّاتٌ روائيةٌ حقيقيةٌ تبتلعها الرخصةُ اليومَ ⇒ تكلفتُها.")
    print("   «زلّة/إنذار» = كم زلّةً نعمى عنها ثمناً لكلِّ إنذارٍ كاذبٍ نمنعه (الأعلى أغلى).")

    if examples:
        print()
        for key, name, lost, gain, lex, gex in rows:
            print("— %s" % name)
            for x in lex:
                print("   إنذارٌ يُمنع:  %s" % x)
            for x in gex:
                print("   زلّةٌ تُبتلع: %s" % x)
    return rows


def real_text(examples=0):
    """🎙️ الطرفُ الذي لا يقيسه مجتمعُ (أ): الفائدةُ على **نصِّ تعرّفٍ حقيقيّ**.

    مجتمعُ (أ) مسموعُه صورةُ whisper **الحتميّة** للكلمة الصحيحة ⇒ فيه فروقُ الرسم كلُّها
    ولا شيءَ من ضجيج التعرّف. فهو يقيس الرخصَ **الرسميّة** (الخنجريّة · الصلة · النقل ·
    ے) قياساً تامّاً، ويعطي **صفراً بالبناء** لرخصتَي التسامح مع خطأ التعرّف (عتبةُ الخُمس ·
    رخصةُ القصيرة): لا خطأَ تعرّفٍ في المسموع أصلاً فلا شيءَ لهما تُنقذانه.

    فتُقاسان هنا على الحزمتين المودَعتين: `parity_fixture.tsv` (‏212 حالةً مصدَّقةً على
    المحرك) و`long_anchor_fixture.tsv` (‏60 تفريغاً حقيقيّاً) — تلاواتٌ صحيحةٌ بقرّاءِ مرجع
    ⇒ كلُّ سقوطٍ من CORRECT إلى اتّهامٍ مؤكَّدٍ **إنذارٌ كاذبٌ** بلا استثناء.
    """
    import short_word_benefit as B  # noqa: E402  (مصدرٌ واحدٌ لقراءة الحزمتين)

    rows = B.load_fixture() + B.load_long()

    def judge(kw):
        out = {}
        for r in rows:
            base = dict(naql=(r["riwaya"] == "warsh"), sila=(r["riwaya"] in ("warsh", "qalun")))
            base.update(kw)
            cfg = scorer.Config(**base)
            words = r["ref"].split()
            res = scorer.score(words, r["hyp"], cfg)
            for i, (w, v) in enumerate(zip(words, res["words"])):
                out[(r["name"], i)] = (w, v[1], v[2])
        return out

    base = judge({})
    total, bad = B.validate(B.load_fixture(), base)
    print("🧪 ضابطُ التصديق · الحزمةُ المصدَّقةُ على المحرك: %d/%d حكماً مطابقاً %s"
          % (total - bad, total, "✅" if bad == 0 else "🚨"))
    n_correct = sum(1 for v in base.values() if v[1] == scorer.CORRECT)
    print("🎙️ نصٌّ حقيقيّ: %d كلمةً مرجعية (%d منها CORRECT بالمشحون)\n" % (len(base), n_correct))

    print("%-42s %14s" % ("الرخصة (إلغاؤها)", "إنذارٌ كاذب"))
    for key, name, kw, riws in LICENSES:
        arm_j = judge(kw)
        lost, ex = 0, []
        for k, (w, v, heard) in base.items():
            if v == scorer.CORRECT and arm_j[k][1] in (scorer.MISSED, scorer.SUBSTITUTED):
                lost += 1
                if len(ex) < examples:
                    ex.append("%s ⇜ «%s»" % (w, heard))
        print("%-42s %14d%s" % (name, lost, ("   " + " · ".join(ex)) if ex else ""))
    print("\n   ⚠️ الحزمتان صغيرتان (%d كلمة) ⇒ الرقمُ **حدٌّ أدنى** لا حصر." % len(base))


def control(limit=400):
    """🧪 الضوابط: موجَبٌ (المشحونُ يساوي نفسَه) وسالبٌ (رخصةٌ موسَّعةٌ تحرّك العدّاد)."""
    text = prepare(limit)
    pa, pb = list(population_a(text)), list(population_b(text))
    ship = {r: shipped(r) for r in RIWAYAT}

    same = sum(1 for r, raw, hyp in pa
               if accepts(ship[r], raw, hyp) != accepts(arm(r), raw, hyp))
    print("🧪 موجَب · إعدادٌ مطابقٌ للمشحون على %d زوجاً ⇒ %d اختلاف %s"
          % (len(pa), same, "✅" if same == 0 else "🚨"))

    wide = sum(1 for r, raw, hyp in pa
               if accepts(ship[r], raw, hyp) != accepts(arm(r, short_cap=9), raw, hyp))
    wide_b = sum(1 for e, s, raw, hyp in pb
                 if accepts(ship[e], raw, hyp) != accepts(arm(e, short_cap=9), raw, hyp))
    print("🧪 سالب · رخصةٌ موسَّعةٌ (‏≤9) ⇒ حرّكت %d في (أ) و%d في (ب) %s"
          % (wide, wide_b, "✅ العدّادُ حيّ" if (wide + wide_b) else "🚨 العدّادُ أخرس"))

    # ضابطُ الاتّجاه: مرجعُ رواية بمسموعِ روايةٍ أخرى يجب أن يختلف عن مرجعها بنفسها
    print("🧪 اتّجاه · مجتمعُ (ب) على %d آيةٍ أولى = %d زوجاً (غيرُ فارغ) %s"
          % (limit, len(pb), "✅" if pb else "🚨"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="عددُ الآيات (0 = المصحف كلُّه)")
    ap.add_argument("--examples", type=int, default=0)
    ap.add_argument("--control", action="store_true")
    ap.add_argument("--real", action="store_true", help="الفائدةُ على نصِّ تعرّفٍ حقيقيّ")
    a = ap.parse_args()
    if a.control:
        control(a.limit or 400)
        return
    if a.real:
        real_text(a.examples)
        return
    measure(prepare(a.limit), a.examples)


if __name__ == "__main__":
    main()
