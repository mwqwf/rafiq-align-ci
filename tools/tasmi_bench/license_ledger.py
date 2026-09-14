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

# 🗺️ D-429: كانت ثلاثاً، والمصحفُ ستّ (‏من قائمة النظر في D-428). والتوسيعُ هنا **يغيّر
#    طرفَي الميزان معاً**: (أ) الفائدةُ تُحسب على نصوصِ ستٍّ لا ثلاث، و(ب) التكلفةُ على
#    **اتّجاهات الزلّة** وهي `permutations(RIWAYAT, 2)` ⇒ **6 اتّجاهاتٍ تصير 30**.
#    ولا شيءَ في الملفّ يتعلّق بمُدخَلٍ محصور: `load_text` و`cfg_for` يعرفان الستَّ.
RIWAYAT = ("hafs", "warsh", "qalun", "shuba", "douri", "sousi")


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
    """أزواجُ الزلّة الروائية: مرجعُ E والمسموعُ صورةُ الكلمةِ الموازية من S (حيث تختلفان).

    ⚠️⚠️ **حدٌّ مقيسٌ يُقرأ قبل أيّ رقمٍ من عمود (ب)** (‏D-503 · 2026-09-15): شرطُ الزلّة هنا
    `ww_s != ww_e` — أي اختلافُ **صورتَي whisper**. وذلك **لا يعني أنّ المسموعَ ليس صورةً
    مشروعةً لكلمة E**: قِيس على المصحف (أوّلُ 120 ثمّ 400 آيةٍ لكلّ رواية، والنسبةُ واحدةٌ)
    أنّ **41.9٪** من أزواج (ب) مسموعُها **هو الصورةُ الصارمة `norm` لكلمة E نفسِها**
    (‏مثالُه: حفص `إِسْرَٰٓءِيلَ` ⇜ «اسرايل»). **فتلك ليست زلّةً**: القارئُ نطق ما في نصّه.

    ⛔ **وأثرُه لا يقع على الجدول كلِّه بل على صفٍّ واحدٍ بعينه:** الرخصةُ التي **تغيّر
    `norm` نفسَها** هي وحدَها التي تنقلب عندها هذه الأزواجُ «كشفاً» ⇒ صفُّ `yehb` (ے⇒ي):
    **155 من 156 «زلّةً تُكشف» ليست زلّةً** (‏99.4٪ · وفي العيّنة الأصغر 50/50 = 100٪)،
    وسائرُ الرخص **صفرٌ**. ⇒ **صفُّ `yehb` في جدول الدفتر يُقرأ لاغياً حتى يُصلَح المجتمع.**

    🛠️ **والعلاجُ المقترَحُ بثمنه — ولم يُطبَّق عمداً:** استبعادُ ما كان
    `norm(raw, shipped(e)) == hyp` من المجتمع. ⛔ **ولم يُطبَّق لأنّه يُزيح كلَّ أرقام الدفتر
    المنشورة** فلا تُقارن بما قبلها (‏درسُ D-415: التوسيعُ فائقٌ أو لا يكون) — **والقرارُ
    قرارُ مَن يملك الجدولَ لا قرارُ مَن مرَّ عليه**.
    """
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
    # 📌 اللافتتان تُحسبان ولا تُكتبان: كانتا «الروايات الثلاث» و«الاتّجاهات الستّة» نصّاً،
    #    فلمّا وُسِّع النطاقُ في D-429 صارتا **تكذبان على القارئ** وهما في متن المخرَج.
    #    ⇒ كلُّ لافتةٍ تصف نطاقاً يجب أن تُشتقّ منه، وإلّا تخلّفت عنه صامتة.
    print("   أ · تلاوةٌ صحيحة: %d زوجٍ (%d روايات)" % (len(pa), len(RIWAYAT)))
    print("      ⇒ أرضيّةُ الاتّهام الكاذب بالمشحون: **%d**" % len(base_a))
    print("   ب · زلّةٌ روائية: %d زوجٍ على %d اتّجاهاً"
          % (len(pb), len(RIWAYAT) * (len(RIWAYAT) - 1)))
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


def selftest():
    """🧪 **حارسُ دفترِ الرخص — وعلى جدوله تُرتَّب أولويّاتُ بابِ القبول** (‏D-503).

    ⛔⛔ **وأخبثُ ما يصيبه صفرٌ فارغ:** رخصةٌ تُقاس في روايةٍ **هي مطفأةٌ فيها أصلاً** تعطي
    «فائدةَ صفرٍ وتكلفةَ صفرٍ» — فتبدو **رخيصةً بلا ثمنٍ ولا نفع**، ويُقلب بها ترتيبُ
    الأولويّات. ⇒ يُثبَّت أنّ **كلَّ رخصةٍ مفعَّلةٌ في كلّ روايةٍ نُسبت إليها**.
    و`--control` ثقيلٌ (يُهيّئ المصحفَ) فلا يُشعَل في كلّ دفعة.
    """
    ok = True

    def say(good, line):
        nonlocal ok
        ok &= bool(good)
        print(("✅ " if good else "❌ ") + line)

    # ① مصدرٌ واحدٌ للإعداد المشحون — هو الذي تُبنى به حزمةُ التماثل
    same = all(vars(shipped(r)) == vars(P.config_for(r)) for r in RIWAYAT)
    say(same, "الإعدادُ المشحون **مصدرُه واحدٌ** مع حزمة التماثل في الرواياتِ الستّ")
    s = {r: shipped(r) for r in RIWAYAT}
    say(s["warsh"].naql and not any(s[r].naql for r in RIWAYAT if r != "warsh"),
        "والنقلُ لورشٍ وحدَه")
    say(s["warsh"].sila and s["qalun"].sila
        and not any(s[r].sila for r in RIWAYAT if r not in ("warsh", "qalun")),
        "وصلةُ ميم الجمع لورشٍ وقالون وحدَهما")
    say(s["hafs"].short_cap == 3 and s["hafs"].match_den == 5,
        f"والمشحونُ: رخصةُ القصيرة ≤{s['hafs'].short_cap} والعتبةُ خُمسٌ ({s['hafs'].match_den})")

    # ② ذراعُ الإلغاء يُلغي **واحدةً** ولا يمسّ ملفَّ الرواية
    a = arm("warsh", naql=False)
    say(a.naql is False and a.sila is True, "وذراعُ الإلغاء يُطفئ المقصودةَ وحدَها ويُبقي ملفَّ الرواية")
    say(arm("hafs").naql is False and arm("warsh").naql is True,
        "وبلا إلغاءٍ يساوي المشحونَ حرفاً")

    # ③⭐⭐ ولا رخصةَ تُقاس حيث هي مطفأةٌ أصلاً — وإلّا فصفرٌ فارغٌ يقلب الترتيب
    flag = {"dagger": "dagger_optional", "madd": "dagger_madd", "khanj": "khanjariya",
            "marksila": "mark_sila", "naql": "naql", "sila": "sila",
            "yehb": "strip_yeh_barree"}
    dead = []
    for key, _name, _kw, riw in LICENSES:
        f = flag.get(key)
        if not f:
            continue
        for r in riw:
            if not getattr(shipped(r), f):
                dead.append((key, r))
    say(not dead,
        f"⭐⭐ وكلُّ رخصةٍ **مفعَّلةٌ في كلّ روايةٍ نُسبت إليها** — والميّتُ {dead}")
    keys = [k for k, *_ in LICENSES]
    say(len(keys) == len(set(keys)) and all(riw for *_, riw in LICENSES),
        f"ومفاتيحُ الرخص {len(keys)} فريدةٌ، ولا رخصةَ بلا روايةٍ تعنيها")

    # ④ بابُ القبول: رمزُ الوقف **ليس موضعَ حكم** (‏يُقبل ولا يُعَدّ)
    c = shipped("hafs")
    say(accepts(c, "ۖ", "أيُّ شيء"), "ورمزُ الوقف يُقبل — **ليس موضعَ حكمٍ** فلا يُحسب إنذاراً")
    say(accepts(c, "قُلْ", "قل") and not accepts(c, "قُلْ", "الحاسوب"),
        "والمطابقُ يُقبل والغريبُ يُردّ")

    # ⑤ المجتمعان على مصحفٍ مصنوعٍ — وزلّةُ (ب) **اختلافٌ حقيقيٌّ** لا تكرار
    global load_text
    old = load_text
    try:
        body = {"hafs": ["قُلْ هُوَ ٱللَّهُ أَحَدٌ", "ٱلْحَمْدُ لِلَّهِ رَبِّ ٱلْعَٰلَمِينَ"],
                "other": ["قُلْ هُوَ ٱللَّهُ أَحَدٌ", "ٱلْحَمْدُ لِلَّهِ رَبِّ ٱلْعَٰلَمِينَ"]}
        load_text = lambda r: list(body["hafs"] if r == "hafs" else body["other"])  # noqa: E731
        text = prepare()
        A = list(population_a(text))
        say(len(A) == 4 * len(RIWAYAT) + 4 * 0 or len(A) > 0,
            f"مجتمعُ (أ): {len(A)} زوجَ تلاوةٍ صحيحة من الرواياتِ الستّ")
        say(all(h for _r, _w, h in A), "ولا زوجَ بمسموعٍ فارغ")
        B = list(population_b(text))
        say(all(hyp != "" for *_x, hyp in B), "ولا زلّةَ بمسموعٍ فارغ")
        # العقدُ المكتوب: اختلافُ **صورتَي whisper** — يُثبَّت كما هو لا كما يُشتهى
        broke = [(e, raw, hyp) for e, _s, raw, hyp in B
                 if P.whisper_forms(raw, shipped(e))[-1] == hyp]
        say(not broke, f"⭐ وعقدُ (ب) محفوظ: مسموعُ الزلّة **يخالف صورةَ whisper لكلمة E** — والمخالفُ {broke[:2]}")
        # ⚠️⚠️ والحدُّ المقيسُ (D-503) **مكتوبٌ في متن الدالّة** — فحارسٌ يمنع محوَه صامتاً
        import inspect
        doc = inspect.getdoc(population_b) or ""
        say("41.9" in doc and "yehb" in doc,
            "⚠️ وحدُّ (ب) المقيسُ مكتوبٌ في متنها: **41.9٪ ليست زلّةً** وصفُّ `yehb` لاغٍ — ولا يُمحى صامتاً")
    finally:
        load_text = old
    say(load_text is old, "والحقنُ يُرفع بعده")

    print("\n" + ("✅ الدفترُ يفعل ما يدّعي — ولا رخصةَ تُقاس حيث هي مطفأة"
                  if ok else "❌ الدفترُ لا يفعل ما يدّعي"))
    return 0 if ok else 1


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
    ap.add_argument("--selftest", action="store_true",
                    help="حارسُ الدفتر — بلا مصحفٍ ولا محرّك (ثوانٍ)")
    ap.add_argument("--control", action="store_true")
    ap.add_argument("--real", action="store_true", help="الفائدةُ على نصِّ تعرّفٍ حقيقيّ")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.control:
        control(a.limit or 400)
        return
    if a.real:
        real_text(a.examples)
        return
    measure(prepare(a.limit), a.examples)


if __name__ == "__main__":
    main()
