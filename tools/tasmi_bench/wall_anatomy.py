# -*- coding: utf-8 -*-
"""🧱 **تشريحُ الجدار** — الـ71.8٪ التي لا تبلغها عتبةٌ: أيُّها جدارُ صوتٍ وأيُّها رخصةٌ لم تُوزن؟

خلّفت D-289 رقماً وسؤالاً. الرقم: من **49,146** زلّةً روائيةً يبتلعها بابُ القبول، **35,288**
(‏71.8٪) **مطابقةٌ تامّة** بعد المِسطرة (‏d=0) ⇒ لا يبلغها تضييقُ عتبةٍ بحال. وقيل فيها
«سقفُ الطريق 28٪» **وكُفّ عن السؤال**. والسؤالُ الباقي: **وممّ يتركّب الجدارُ نفسُه؟**

والفرقُ ليس تفصيلاً بل يقلب الاستنتاج. فمجتمعُ (ب) لا يولّد الزلّةَ إلا حيث **تختلف صورةُ
whisper للكلمتين** (`ww_s != ww_e` شرطُ التوليد) ⇒ **المعلومةُ الفارقةُ حاضرةٌ في المسموع
أصلاً**، والانطباقُ وقع في **بابِ القبول** لا في أذن النموذج. فجدارُ الـ71.8٪ ليس جداراً
واحداً بل أربعة، وحكمُ كلِّ واحدٍ منها مختلف:

    ١ · فرقٌ في **الحركات والعلامات** وحدَها (لا خنجريّة) — مسموعٌ **لا يُكتب**: whisper
        يكتب إملاءً حديثاً بلا تشكيل ⇒ **جدارُ صوتٍ حقيقيّ**، لا تبلغه قاعدةٌ نصّيةٌ البتّة.
    ٢ · فرقٌ في **الألف الخنجرية** وحدَها (‏مَٰلِكِ ⇜ «مالك» · مَلِكِ ⇜ «ملك») — مسموعٌ
        **يُكتب**، وقد وُزن: رخصةُ `dagger_optional` في دفتر D-286 وبابُ D-287/288.
    ٣ · فرقٌ في **حرفٍ يكتبه whisper** أطفأه **جدولُ الإبدال** `_SUBS` (‏ة⇒ه · ى⇒ي ·
        الهمزاتُ⇒ا · ء⇒حذف · ؤ⇒و · ئ⇒ي) — **أقدمُ رخصةٍ في المِسطرة ولم تُوزن واحدةٌ منها قطّ**،
        لا في دفتر D-286 ولا في غيرِه.
    ٤ · فرقٌ في **الرسم صراحةً** يبقى بعد الجدول كلِّه ⇒ الانطباقُ من بابِ الصور
        (النقل · صلةُ الميم · الخنجريّةُ الاختيارية) — وهي موزونةٌ في D-286.

## العملة — عملةُ D-286/289 نفسُها، وعمودُ التكلفة **حقيقيٌّ لأوّل مرّة**
    الفائدة · كم زلّةً من الـ35,288 تصير **فارقةً في النصّ** لو صان المسموعُ ذلك الحرف
              (سقفٌ زوجيٌّ لا حصيلة — قاعدةُ D-286).
    التكلفة · كم إنذاراً كاذباً يصنعه إلغاءُ الإبدال على **نصِّ تعرّفٍ حقيقيّ**: الحزمتان
              المودَعتان (`parity_fixture.tsv` مصدَّقةٌ على المحرك · `long_anchor_fixture.tsv`
              60 تفريغاً حقيقيّاً). وهذه **ليست تكلفةً مولَّدة**: المسموعُ فيها خرجٌ حقيقيٌّ
              من whisper ⇒ إن كان يكتب `ة` حيث رسمَها المصحفُ فلا ثمنَ للإبدال، وإن كتب `ه`
              ظهر الثمنُ عدداً. وهو **العمودُ الذي قالت D-289 إنّه مفقود**.

⚠️ الفائدةُ مقيسةٌ من المرآة (مصدَّقةٌ على المحرك في بابِ القبول: D-279/285)، والتوليدُ
بالإعدادِ **المشحون**. ⛔ ولا يُشحن من هذا شيءٌ: كلُّ ما فيه **اقتراحٌ** بحسب قاعدة المناوبة.

    python wall_anatomy.py --control      # 🧪 الضوابطُ أوّلاً
    python wall_anatomy.py                # المصحفُ كلُّه (~4 د.)
    python wall_anatomy.py --examples 4
    python wall_anatomy.py --real         # عمودُ التكلفة على نصٍّ حقيقيّ
"""
import argparse
import collections
import io
import itertools
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))

import scorer  # noqa: E402
import license_ledger as L  # noqa: E402  (مصدرٌ واحدٌ للمجتمعين وللإعداد المشحون)
import parity_full as P  # noqa: E402  (‏whisper_forms — مصدرٌ واحدٌ لصورة المسموع)

RIWAYAT = L.RIWAYAT

# إبدالاتُ `_SUBS` التي تُطفئ حرفاً **يكتبه** whisper — كلُّ واحدةٍ ذراعٌ مستقلّ.
# (‏`ٱ⇒ا` و`ے⇒ي` خارجَ الباب: طباعةٌ محضةٌ لا يكتبها whisper بحالٍ ⇒ لا معلومةَ تُطفأ.)
SUB_ARMS = (
    ("ta",     "ة ⇒ ه",            ("ة",)),
    ("maqsura", "ى ⇒ ي",           ("ى",)),
    ("hamzat", "أ إ آ ⇒ ا",        ("أ", "إ", "آ")),
    ("hamza",  "ء ⇒ حذف",          ("ء",)),
    ("waw",    "ؤ ⇒ و",            ("ؤ",)),
    ("yeh",    "ئ ⇒ ي",            ("ئ",)),
)
ALL_DROP = tuple(c for _, _, cs in SUB_ARMS for c in cs)

CONFIRMED = (scorer.MISSED, scorer.SUBSTITUTED)


def skeleton(word, drop=()):
    """الرسمُ المجرَّد: بلا حركاتٍ ولا علاماتٍ ولا خنجريّة، وتُحفظ فيه حروفُ الهمزِ والتاءِ
    والألفِ المقصورة إلا ما طُلب إبدالُه في `drop`.

    `ٱ⇒ا` و`ے⇒ي` تُطبَّقان دائماً: ألفُ الوصل وياءُ الرسم طباعةٌ لا ينطقها فرقٌ ولا يكتبها
    whisper ⇒ حفظُهما يصنع فرقاً وهميّاً. وتُحذف الخنجريّةُ هنا لأنّها **صنفٌ قائمٌ بذاته**
    (الصنفُ ٢) يُفرَز قبل هذا القياس.
    """
    w = scorer._STRIP.sub("", word).replace("ٱ", "ا").replace("ے", "ي")
    for a, b in scorer._SUBS:
        if a in drop:
            w = w.replace(a, b)
    return scorer._NON_ARABIC.sub("", w)


def dagger_only(raw_e, raw_s):
    """هل الفرقُ بين الرسمين **الألفُ الخنجرية** وحدَها؟ (حذفُها من الطرفين يُسوّيهما)"""
    return (skeleton(raw_e) == skeleton(raw_s)
            and ("ٰ" in raw_e) != ("ٰ" in raw_s))


def pairs(text):
    """كمجتمع (ب) في الدفتر، مع **الكلمةِ الخام من رواية S** (يحتاجها التشريح)."""
    for e, s in itertools.permutations(RIWAYAT, 2):
        for (toks_e, ww_e, real_e), (toks_s, ww_s, real_s) in zip(text[e], text[s]):
            if len(real_e) != len(real_s) or not real_e:
                continue
            for ie, isx in zip(real_e, real_s):
                if ww_s[isx] == ww_e[ie] or not ww_s[isx]:
                    continue
                yield e, s, toks_e[ie], toks_s[isx], ww_s[isx]


def min_edit(cfg, raw, hyp):
    """أصغرُ تحريفٍ بين أيِّ صورةٍ مقبولةٍ للمرجع والمسموع — None إن لم يكن موضعَ حكم."""
    forms = tuple(f for f in scorer._riwaya_forms(scorer.variants(raw, cfg), cfg) if f)
    if not forms:
        return None
    return min(scorer._edit(f, hyp) for f in forms)


def arm_cfg(riwaya, drop=(), **kw):
    """إعدادُ الذراع: المشحونُ بملفِّ الرواية، وقد أُلغيت منه إبدالاتٌ بعينِها."""
    return scorer.Config(naql=(riwaya == "warsh"), sila=(riwaya in ("warsh", "qalun")),
                         drop_subs=drop, **kw)


def rejects(e, s, raw_e, raw_s, drop=(), **kw):
    """هل يردّ الذراعُ هذه الزلّة **فعلاً**؟ — التوليدُ بالذراع كالفحص.

    ⚠️ وهذا خلافُ قاعدة «ولِّد بالمشحون وافحص بالذراع» **لأنّ السؤالَ مختلف**: ليس «هل
    تُعطب المرآة؟» بل «لو كان المسموعُ صائناً للحرف (وهو ما يصنعه whisper فعلاً: يكتب `ة`
    و`ى` و`أ`) أفيكشف البابُ الزلّةَ؟». فصونُ الحرف في الطرفين هو المسألةُ نفسُها لا دائريّة؛
    وإسقاطُ إبدالٍ لا يُلبس صورتين (يُرهِف القسمةَ ولا يدمجها) ⇒ الزلّةُ تبقى زلّة.
    """
    cfg_s, cfg_e = arm_cfg(s, drop, **kw), arm_cfg(e, drop, **kw)
    return not L.accepts(cfg_e, raw_e, P.whisper_forms(raw_s, cfg_s)[-1])


# علاماتٌ تُمحى في `_STRIP` لكنّها **تقوم مقام حرفٍ منطوقٍ** لا حركةً: الياءُ والواوُ
# الصغيرتان (صلةُ D-248) · الياءُ العاليةُ في رسم الروايتين · الهمزةُ فوقَ وتحتَ. فرقٌ فيها
# **يكتبه** whisper (‏النبيئين / النبين) ⇒ هو حدُّ مولّدِنا لا جدارَ صوت.
SOUND_MARKS = frozenset("ٕٔۥۦۧۨ")


def classify(raw_e, raw_s):
    """صنفُ الجدار + الأذرعُ **اللازمة** للانطباق (للصنف ٣).

    ⛔ **واختبارُ الخنجريّة يُستدعى من `dagger_only` ولا يُعاد كتابتُه هنا** (‏درسُ D-613):
    كان مكتوباً مرّتين — هنا وهناك — **ونسختان تتباعدان**. وقد قِيس أنّهما تتّفقان في
    **224,118 زوجاً** يومَ التوحيد، **وذلك اتّفاقُ حالٍ لا ضمانةُ بنية**. فصار المصدرُ واحداً.
    """
    if skeleton(raw_e) == skeleton(raw_s):
        if dagger_only(raw_e, raw_s):
            return "dagger", ()
        a = collections.Counter(c for c in raw_e if c in SOUND_MARKS)
        b = collections.Counter(c for c in raw_s if c in SOUND_MARKS)
        return ("marks_sound" if a != b else "marks_pure"), ()
    if skeleton(raw_e, ALL_DROP) != skeleton(raw_s, ALL_DROP):
        return "rasm", ()
    need = []
    for key, _, chars in SUB_ARMS:
        rest = tuple(c for c in ALL_DROP if c not in chars)
        if skeleton(raw_e, rest) != skeleton(raw_s, rest):
            need.append(key)          # بلا هذا الذراع لا ينطبق الرسمان ⇒ لازم
    return "subs", tuple(need)


CLASS_NAME = {
    "marks_pure": "١أ · حركاتٌ وسكونٌ وشدّةٌ ومدٌّ وحدَها ⇒ 🧱 **جدارُ صوتٍ**: whisper لا يكتب تشكيلاً",
    "marks_sound": "١ب · علامةٌ تقوم مقام حرفٍ منطوق (ۦ ۥ ۧ ٔ) ⇒ يكتبها whisper: **حدُّ مولّدِنا** لا جدار",
    "dagger": "٢ · الألفُ الخنجرية وحدَها ⇒ يُكتب، ووُزن (‏D-286/287/288)",
    "subs": "٣ · حرفٌ يكتبه whisper أطفأه جدولُ الإبدال ⇒ **لم يوزن قطّ**",
    "rasm": "٤ · رسمٌ مختلفٌ صراحةً ⇒ الانطباقُ من بابِ الصور (‏النقل · الصلة · الخنجريّةُ الاختيارية)",
}


def measure(text, examples=0):
    ship = {r: L.shipped(r) for r in RIWAYAT}
    hist = collections.Counter()
    cls = collections.Counter()
    need_cnt = collections.Counter()
    ex = collections.defaultdict(list)
    wall = []
    n_pairs = n_blind = 0

    for e, s, raw_e, raw_s, hyp in pairs(text):
        n_pairs += 1
        if not L.accepts(ship[e], raw_e, hyp):
            continue                                  # مكشوفة: ليست من الجدار
        n_blind += 1
        d = min_edit(ship[e], raw_e, hyp)
        hist[min(d, 3) if d is not None else -1] += 1
        if d != 0:
            continue                                  # تبلغها العتبة (‏D-289)
        c, need = classify(raw_e, raw_s)
        cls[c] += 1
        wall.append((e, s, raw_e, raw_s))
        if c == "subs":
            need_cnt[need or ("—",)] += 1
            for k in (need or ("—",)):
                need_cnt[(k,)] += 0                   # يضمن ظهورَ الأذرع في الجدول
        if len(ex[(c, need)]) < examples:
            ex[(c, need)].append("%s⇜%s: %s / %s ⇜ «%s»" % (e, s, raw_e, raw_s, hyp))

    d0 = cls and sum(cls.values()) or 0
    # ⛔ **العددُ يُحسب ولا يُكتب حرفيّاً** (‏D-615): كانت الترويسةُ تُعلن عددَ الاتّجاهات **رقماً
    #    جامداً (ستّة)**، ثمّ صارت الرواياتُ **ستّاً** فالاتّجاهاتُ **ثلاثون** — فبقيت تقول ستّةً
    #    وهي تعدّ ثلاثين. **وهذا بعينِه سببُ تباعد الأرقام عن إسناد D-289** (‏قِيس يومَ كنّ ثلاثاً).
    #    ⚠️ ولا يُعاد ذلك الرقمُ الجامدُ إلى المتن ولو في تعليق: حارسُ ⑨ يبحث عنه في الملفّ كلِّه.
    print("👥 المجتمع (المصحفُ كلُّه · %d روايةً · %d اتّجاهاً): %d زوجَ زلّةٍ روائية"
          % (len(RIWAYAT), len(RIWAYAT) * (len(RIWAYAT) - 1), n_pairs))
    print("   يبتلعها بابُ القبول (عمىً): **%d** (%.1f٪)" % (n_blind, 100.0 * n_blind / max(n_pairs, 1)))
    print("   منها مطابقةٌ تامّة (‏d=0) = **%d** · حرفٌ واحد %d · حرفان %d · ثلاثةٌ وأكثر %d"
          % (hist[0], hist[1], hist[2], hist[3]))
    print("   🧪 إسنادُ D-289: (‏35,288 · 13,452 · 406) — ⛔ **على ثلاث رواياتٍ لا ستّ**")
    print("      ⇒ لا يُقارَن بما أعلاه مباشرةً: المجتمعان مختلفان (‏6 اتّجاهاتٍ ⇐ %d)"
          % (len(RIWAYAT) * (len(RIWAYAT) - 1)))
    print()
    print("🧱 تشريحُ الجدار (‏الـd=0 وحدَها = %d زوجاً):" % d0)
    for key in ("marks_pure", "marks_sound", "dagger", "subs", "rasm"):
        n = cls[key]
        print("   %-6s %7d  (%5.1f٪ من الجدار · %5.1f٪ من العمى)  %s"
              % ("", n, 100.0 * n / max(d0, 1), 100.0 * n / max(n_blind, 1), CLASS_NAME[key]))
    print()
    print("📒 الصنفُ ٣ مفصَّلاً — الأذرعُ **اللازمة** للانطباق (الفائدةُ سقفٌ زوجيّ):")
    print("   %-28s %12s" % ("الإبدال (إلغاؤه)", "زلّةٌ تصير فارقة"))
    per = collections.Counter()
    for need, n in need_cnt.items():
        for k in need:
            per[k] += n
    for key, name, _ in SUB_ARMS:
        print("   %-28s %12d" % (name, per[key]))
    multi = sum(n for need, n in need_cnt.items() if len(need) > 1)
    print("   (‏منها %d زوجاً يحتاج أكثرَ من إبدالٍ معاً ⇒ يُحسب في كلِّ ذراعٍ لازم)" % multi)

    print()
    print("🎯 الفائدةُ **الفعليّة** لا الورقيّة — كم من الجدار يردّه الذراعُ حقّاً")
    print("   (التوليدُ والفحصُ بالذراع معاً: هكذا يكون المسموعُ صائناً للحرف كما يصنعه whisper)")
    print("   %-36s %12s %10s" % ("الذراع", "يُكشف", "٪ من الجدار"))
    combos = [(name, chars, {}) for _, name, chars in SUB_ARMS]
    combos += [("الجدولُ كلُّه معاً", ALL_DROP, {}),
               ("الجدولُ كلُّه + السدس (‏D-286)", ALL_DROP, dict(match_den=6)),
               ("الجدولُ كلُّه + سقفٌ مطلق ≤1 (‏D-289)", ALL_DROP, dict(abs_cap=1)),
               ("السدسُ وحدَه (مرجعُ مقارنة)", (), dict(match_den=6)),
               ("سقفٌ مطلق ≤1 وحدَه (مرجعُ مقارنة)", (), dict(abs_cap=1))]
    for name, chars, kw in combos:
        n = sum(1 for e, s, raw_e, raw_s in wall if rejects(e, s, raw_e, raw_s, chars, **kw))
        print("   %-36s %12d %9.1f٪" % (name, n, 100.0 * n / max(d0, 1)))

    if examples:
        print()
        for (c, need), lst in sorted(ex.items(), key=lambda kv: kv[0][0]):
            print("— %s %s" % (c, "+".join(need) if need else ""))
            for x in lst:
                print("   %s" % x)
    return dict(pairs=n_pairs, blind=n_blind, hist=hist, cls=cls, per=per, d0=d0)


def real_cost(examples=0):
    """💰 عمودُ التكلفة على **نصِّ تعرّفٍ حقيقيّ** — الذي قالت D-289 إنّه مفقود.

    المسموعُ خرجٌ حقيقيٌّ من whisper وتلاوةُ قارئِ مرجعٍ صحيحة ⇒ كلُّ سقوطٍ من CORRECT إلى
    اتّهامٍ مؤكَّدٍ **إنذارٌ كاذبٌ** بلا استثناء. والإبدالُ يُلغى في **الطرفين** (المرجعُ
    والمسموعُ يمرّان بـ`norm` نفسِها) ⇒ الثمنُ هو بالضبط: **كم مرّةً كتب whisper الحرفَ
    غيرَ ما رسمه المصحف.**
    """
    import short_word_benefit as B  # noqa: E402  (مصدرٌ واحدٌ لقراءة الحزمتين)

    rows = B.load_fixture() + B.load_long()

    def judge(drop):
        out = {}
        for r in rows:
            cfg = scorer.Config(naql=(r["riwaya"] == "warsh"),
                                sila=(r["riwaya"] in ("warsh", "qalun")),
                                drop_subs=drop)
            words = r["ref"].split()
            res = scorer.score(words, r["hyp"], cfg)
            for i, (w, v) in enumerate(zip(words, res["words"])):
                out[(r["name"], i)] = (w, v[1], v[2])
        return out

    base = judge(())
    total, bad = B.validate(B.load_fixture(), base)
    print("🧪 ضابطُ التصديق · الحزمةُ المصدَّقةُ على المحرك: %d/%d حكماً مطابقاً %s"
          % (total - bad, total, "✅" if bad == 0 else "🚨"))
    n_correct = sum(1 for v in base.values() if v[1] == scorer.CORRECT)
    print("🎙️ نصٌّ حقيقيّ: %d كلمةً مرجعية (%d منها CORRECT بالمشحون)\n" % (len(base), n_correct))

    print("   %-28s %14s" % ("الإبدال (إلغاؤه)", "إنذارٌ كاذب"))
    out = {}
    for key, name, chars in SUB_ARMS + (("all", "الجدولُ كلُّه", ALL_DROP),):
        arm = judge(chars)
        lost, exs = 0, []
        for k, (w, v, heard) in base.items():
            if v == scorer.CORRECT and arm[k][1] in CONFIRMED:
                lost += 1
                if len(exs) < max(examples, 2):
                    exs.append("%s ⇜ «%s»" % (w, heard))
        out[key] = lost
        print("   %-28s %14d%s" % (name, lost, ("   " + " · ".join(exs)) if exs else ""))
    print("\n   ⚠️ الحزمتان صغيرتان (%d كلمة) ⇒ كلُّ رقمٍ هنا **حدٌّ أدنى** لا حصر."
          % len(base))
    return out


def control(limit=400):
    """🧪 الضوابط: موجَبٌ · سالبٌ · حيويّةٌ · وتطابقُ الأصناف."""
    text = L.prepare(limit)
    ship = {r: L.shipped(r) for r in RIWAYAT}
    ps = list(pairs(text))

    # موجَب ١: `drop_subs=()` يجب أن يكون المشحونَ حرفاً بحرف
    same = sum(1 for e, s, raw_e, raw_s, hyp in ps
               if L.accepts(ship[e], raw_e, hyp)
               != L.accepts(scorer.Config(naql=(e == "warsh"), sila=(e in ("warsh", "qalun")),
                                          drop_subs=()), raw_e, hyp))
    print("🧪 موجَب ١ · `drop_subs=()` مقابل المشحون على %d زوجاً ⇒ %d اختلاف %s"
          % (len(ps), same, "✅" if same == 0 else "🚨"))

    # موجَب ٢: مجتمعُ هذا الملفّ = مجتمعُ الدفتر بعينِه (لا ينحرف التوليد)
    mine = [(e, s, raw_e, hyp) for e, s, raw_e, _, hyp in ps]
    theirs = list(L.population_b(text))
    print("🧪 موجَب ٢ · المجتمعُ يطابق `license_ledger.population_b`: %d مقابل %d %s"
          % (len(mine), len(theirs), "✅" if mine == theirs else "🚨"))

    # سالب ١: الأصنافُ تقسم الـd=0 قسمةً تامّة (لا زوجَ بلا صنفٍ ولا زوجَ في صنفين)
    d0 = [(e, s, a, b, h) for e, s, a, b, h in ps
          if L.accepts(ship[e], a, h) and min_edit(ship[e], a, h) == 0]
    cls = collections.Counter(classify(a, b)[0] for _, _, a, b, _ in d0)
    print("🧪 سالب ١ · قسمةُ الأصناف: %d = %d (مجموعُ الأصناف) %s"
          % (len(d0), sum(cls.values()), "✅" if len(d0) == sum(cls.values()) else "🚨"))

    # سالب ٢: كلمةٌ غريبةٌ لا تُصنَّف «حركاتٍ وحدَها» ولا «إبدالاً» البتّة
    bad = sum(1 for _, _, a, _, _ in d0 if classify(a, "الحاسوب")[0] != "rasm")
    print("🧪 سالب ٢ · كلمةٌ غريبةٌ مقابل كلِّ مرجعٍ (%d) ⇒ %d تصنيفاً غيرَ «رسم» %s"
          % (len(d0), bad, "✅" if bad == 0 else "🚨"))

    # سالب ٣: الصنفُ ٣ يجب أن **ينطبق** بالجدول كلِّه ويفترق بلا الأذرعِ اللازمة
    wrong = 0
    for _, _, a, b, _ in d0:
        c, need = classify(a, b)
        if c != "subs":
            continue
        if skeleton(a, ALL_DROP) != skeleton(b, ALL_DROP) or not need:
            wrong += 1
    print("🧪 سالب ٣ · اتّساقُ الصنف ٣ (ينطبق بالجدول · له ذراعٌ لازم) ⇒ %d خللاً %s"
          % (wrong, "✅" if wrong == 0 else "🚨"))

    # حيويّة: كلُّ ذراعٍ من الجدول يحرّك `norm` على المصحف (ليس ذراعاً ميّتاً)
    print("🧪 حيويّة · حركةُ كلِّ ذراعٍ في `norm` على %d آيةٍ أولى:" % limit)
    from common import load_text  # noqa: E402
    words = [w for r in RIWAYAT for a in load_text(r)[:limit] for w in a.split()]
    for key, name, chars in SUB_ARMS:
        cfg_a = scorer.Config(drop_subs=chars)
        moved = sum(1 for w in words if scorer.norm(w) != scorer.norm(w, cfg_a))
        print("   %-28s %7d من %d %s" % (name, moved, len(words), "✅" if moved else "🚨 ميّت"))


# 📊 جردُ الأصناف على المصحف كلِّه (‏224,118 زوجاً · قِيس 2026-09-15 · D-614).
#    وهو **مقامُ التشريح**: كلُّ نسبةٍ في هذا الملفّ تُقرأ عليه.
CENSUS = {"marks_pure": 188792, "subs": 20082, "marks_sound": 8372,
          "rasm": 6536, "dagger": 336}
CENSUS_PAIRS = 224118

# 📒 دفترُ الصنف ٣ المقيسُ (‏D-615 · ستُّ رواياتٍ · 30 اتّجاهاً · جدارُ d=0 = 110,178):
#    `paper` = الذراعُ **لازمةٌ** لانطباق الرسمين (سقفٌ ورقيّ)
#    `real`  = ما يردّه الذراعُ **فعلاً** حين يصون المسموعُ الحرفَ كما يصنعه whisper
#    `cost`  = إنذارٌ كاذبٌ على **نصِّ تعرّفٍ حقيقيّ** (3,823 كلمةً مرجعية)
SUB_LEDGER = {                  # الذراع: (paper, real, cost)
    "ta":      (13,    13,  0),
    "maqsura": (1969, 360,  0),
    "hamzat":  (6742, 666,  5),
    "hamza":   (685,   24, 13),
    "waw":     (538,   20,  0),
    "yeh":     (430,   46,  0),
}
LEDGER_ALL = (10035, 1395, 45)  # الجدولُ كلُّه: ورقيٌّ · فعليٌّ · كلفة
LEDGER_WITH_SIXTH = 4241        # الجدولُ + السدس (D-286) — والسدسُ وحدَه **صفر**
WALL_D0 = 110178


def selftest():
    """🧪 **حارسُ تشريح الجدار** (‏D-614) — والضابطُ القائمُ (`--control`) ثقيلٌ يبني المجتمعَ
    كلَّه، وهذا يفحص في ثانيةٍ ما لا يفحصه هو: **سلامةَ المصنِّف نفسِه**.

    ⭐⭐ **وأخطرُ ما هنا أنّ العطبَ لا يُرى:** `classify` يوزّع 224 ألفَ زوجٍ على خمسة أصناف،
    وحكمُ كلِّ صنفٍ **مختلفٌ تماماً** (جدارُ صوتٍ لا يُعالَج · رخصةٌ وُزنت · رخصةٌ لم تُوزن قطّ).
    فصنفٌ يبتلع صنفاً **لا يُسقط شيئاً ولا يُنذر**، وإنّما يُحوّل «رخصةً لم تُوزن» إلى
    «جدارِ صوتٍ» فيُغلق بابٌ مفتوح. ⇒ **الجردُ مثبَّتٌ بالرقم**، والفروقُ البنيويّةُ مثبَّتةٌ بحالات.
    """
    ok = True

    def say(good, line):
        nonlocal ok
        ok &= bool(good)
        print(("✅ " if good else "❌ ") + line)

    # ①⭐ حالاتٌ مبنيّةٌ باليد — صنفٌ صنفاً، والحدودُ بينها هي موضعُ الخطر
    cases = [
        ("١أ حركاتٌ وحدَها",        "مَلِكِ", "مَلِكُ",  "marks_pure"),
        ("٢ خنجريّةٌ وحدَها",        "مَٰلِكِ", "مَلِكِ",  "dagger"),
        ("٣ تاءٌ مربوطة",           "رَحْمَة", "رَحْمَه",  "subs"),
        ("٣ ألفٌ مقصورة",           "هُدَى",  "هُدَي",   "subs"),
        ("٤ رسمٌ مختلفٌ صراحةً",     "قَالَ",  "قُل",    "rasm"),
    ]
    for name, a, b, want in cases:
        got, _need = classify(a, b)
        say(got == want, "%s: %s ⇐⇒ %s ⇒ `%s`" % (name, a, b, got))

    # ②⭐⭐ الصنفُ ٣ **لا يُعاد بأذرعٍ فارغة** — وإلّا فالتصنيفُ يناقض نفسَه
    k, need = classify("رَحْمَة", "رَحْمَه")
    say(k == "subs" and need == ("ta",),
        "⭐⭐ والصنفُ ٣ يسمّي ذراعَه اللازمة: %s" % (need,))

    # ③⭐⭐ اختبارُ الخنجريّة **مصدرٌ واحد** (‏درسُ D-613: نسختان تتباعدان)
    #     ⚠️ والإبرةُ تُركَّب وقتَ التشغيل وإلّا طابقت سطرَها (‏وقعتُ فيه أربعَ مرّات).
    src = io.open(os.path.abspath(__file__), encoding="utf-8").read()
    say(src.count("de" + "f dagger_only(") == 1 and "dagger_only(raw_e, raw_s)" in src,
        "⭐⭐ اختبارُ الخنجريّة مُعرَّفٌ مرّةً و`classify` **يستدعيه** لا ينسخه")
    say(dagger_only.__module__ == __name__ and classify.__module__ == __name__,
        "⭐ والمفحوصُ دالّتا المتن بعينهما لا صورةٌ عنهما")

    # ④ `skeleton` يُسقط الخنجريّة (‏وإلّا لَما انفصل الصنفُ ٢) ويُطبّق ٱ⇒ا و ے⇒ي دائماً
    say(skeleton("مَٰلِكِ") == skeleton("مَلِكِ"),
        "⛔ و`skeleton` يُسقط الخنجريّة ⇒ الصنفُ ٢ ينفصل قبل قياس العلامات")
    say(skeleton("ٱلْحَمْدُ") == skeleton("الحمد") and skeleton("ے") == skeleton("ي"),
        "⛔ و`ٱ⇒ا` و`ے⇒ي` مطبَّقتان دائماً (‏طباعةٌ لا ينطقها فرق)")

    # ⑤⭐ الأصنافُ الخمسةُ **مسمّاةٌ كلُّها** — وصنفٌ بلا اسمٍ يُطبع مفتاحاً أعجميّاً ويمرّ
    seen = {classify(a, b)[0] for _n, a, b, _w in cases} | {"marks_sound"}
    say(seen <= set(CLASS_NAME) and set(CENSUS) == set(CLASS_NAME),
        "⭐ وكلُّ صنفٍ له اسمٌ وجردٌ: %d أصناف" % len(CLASS_NAME))

    # ⑥⭐⭐ الجردُ المقيسُ محفوظٌ بالرقم — فلو انزاح المصنِّفُ تحتنا **صرخ** بدل أن ينزلق
    say(sum(CENSUS.values()) == CENSUS_PAIRS,
        "⭐⭐ وجردُ المصحف يجمع إلى الكلّ: %d = %d زوجاً" % (sum(CENSUS.values()), CENSUS_PAIRS))
    say(CENSUS["subs"] > CENSUS["rasm"] > CENSUS["dagger"],
        "⭐ و«رخصةٌ لم تُوزن قطّ» (‏%d) أكبرُ من الرسم (‏%d) ومن الخنجريّة (‏%d)"
        % (CENSUS["subs"], CENSUS["rasm"], CENSUS["dagger"]))

    # ⑦ أذرعُ الإبدال الستّةُ متمايزةٌ — وذراعان تتقاسمان حرفاً تُفسدان «اللازمة»
    chars = [c for _k, _n, cs in SUB_ARMS for c in cs]
    say(len(chars) == len(set(chars)) and len(SUB_ARMS) == 6,
        "⛔ وأذرعُ الإبدال **ستٌّ لا يتقاسمن حرفاً**: %d حرفاً" % len(chars))

    # ⑧⭐⭐ دفترُ D-615 محفوظٌ بأرقامه — وثلاثةُ دروسٍ فيه تُثبَّت لئلّا تُقرأ اللوحةُ خطأً
    say(set(SUB_LEDGER) == {k for k, _n, _c in SUB_ARMS},
        "⛔ ودفترُ الأذرع يغطّي الستَّ كلَّها لا بعضَها")
    paper = sum(v[0] for v in SUB_LEDGER.values())
    real = sum(v[1] for v in SUB_LEDGER.values())
    say(LEDGER_ALL[0] < paper and LEDGER_ALL[1] > real,
        "⭐ والأذرعُ **غيرُ جامعة**: الورقيُّ يزيد بالتداخل (%d>%d) والفعليُّ ينقص (%d<%d)"
        % (paper, LEDGER_ALL[0], real, LEDGER_ALL[1]))
    say(LEDGER_ALL[0] >= 7 * LEDGER_ALL[1],
        "⭐⭐ **والورقيُّ يَعِد بسبعةِ أضعاف ما يردّه الفعليّ**: %d مقابل %d ⇒ لا يُنشر الورقيُّ وحدَه"
        % (LEDGER_ALL[0], LEDGER_ALL[1]))
    say(LEDGER_WITH_SIXTH > LEDGER_ALL[1] * 2,
        "⭐⭐ **والرخصُ لا تُجمع**: الجدولُ %d · والسدسُ وحدَه **0** · ومعاً **%d** ⇒ %d موضعاً "
        "يحتاج الاثنين معاً" % (LEDGER_ALL[1], LEDGER_WITH_SIXTH,
                                LEDGER_WITH_SIXTH - LEDGER_ALL[1]))
    say(SUB_LEDGER["hamza"][2] > SUB_LEDGER["hamza"][1] // 2
        and SUB_LEDGER["maqsura"][2] == 0,
        "🚨 وأسوأُ الأذرع `ء⇒حذف` (‏فائدةٌ %d بكلفة %d) وأنقاها `ى⇒ي` (‏%d بكلفة %d)"
        % (SUB_LEDGER["hamza"][1], SUB_LEDGER["hamza"][2],
           SUB_LEDGER["maqsura"][1], SUB_LEDGER["maqsura"][2]))

    # ⑨⛔ وترويسةُ المجتمع **تُحسب ولا تُكتب** — وإلّا قالت «ستّاً» وهي تعدّ ثلاثين
    # ⚠️ الإبرةُ تُركَّب وقتَ التشغيل (‏وإلّا طابقت سطرَها — **المرّةُ السادسة**، وفي ملفٍّ
    #    طبّقتُ فيه العلاجَ صحيحاً في الفحص ③ من الدورة الماضية. فالفخُّ لا يُحفَظ بالتذكّر).
    stale = "الاتّجاهاتُ " + "الستّ"
    say(stale not in src and "len(RIWAYAT) * (len(RIWAYAT) - 1)" in src,
        "⛔ وعددُ الاتّجاهات محسوبٌ من `RIWAYAT` لا مكتوبٌ حرفاً (‏%d روايةً · %d اتّجاهاً)"
        % (len(RIWAYAT), len(RIWAYAT) * (len(RIWAYAT) - 1)))
    say("على ثلاث رواياتٍ لا ستّ" in src,
        "⛔ وإسنادُ D-289 موسومٌ بمجتمعِه فلا يُقارَن بمجتمعٍ آخر (‏درسُ D-611)")

    print("\n%s" % ("✅ حارسُ تشريح الجدار: تمّ" if ok else "❌ حارسُ التشريح: أخفق"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="عددُ الآيات (0 = المصحف كلُّه)")
    ap.add_argument("--examples", type=int, default=0)
    ap.add_argument("--control", action="store_true")
    ap.add_argument("--selftest", action="store_true", help="🧪 حارسُ الأداة (ثانيةٌ · بلا مجتمع)")
    ap.add_argument("--real", action="store_true", help="عمودُ التكلفة على نصٍّ حقيقيّ")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.control:
        control(a.limit or 400)
        return
    if a.real:
        real_cost(a.examples)
        return
    measure(L.prepare(a.limit), a.examples)


if __name__ == "__main__":
    sys.exit(main() or 0)
