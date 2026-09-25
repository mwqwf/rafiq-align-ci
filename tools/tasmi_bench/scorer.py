# -*- coding: utf-8 -*-
"""منقول حرفياً عن `engine/recitation/.../RecitationScorer.kt` — نسخة القياس.

⚠️ **التماثل شرط صحة كل رقم**: هذا الملف ليس «تقريباً» للحاكم بل صورته. يحرسه
اختبار Kotlin `RecitationScorerParityTest` الذي يعيد تشغيل الحاكم الحقيقي على
`work/parity_fixture.json` (مخرج هذا الملف على العيّنة كاملة) ويطابق النتائج
كلمةً كلمة. فإن انحرف أحدهما سقط الاختبار — لا يمر انحراف صامت.

المتغيّرات القابلة للضبط (تُقاس قبل/بعد على العيّنة كاملة لا على أمثلة):
    match_ratio  — عتبة القبول (الأصل: تحريف ≤ خُمس الطول)
    khanjariya   — معاملة الألف الخنجرية ألفاً (الأصل: نعم)
"""
import os
import re

MISSED, ADDED, CORRECT, SUBSTITUTED, UNCERTAIN = "MISSED", "ADDED", "CORRECT", "SUBSTITUTED", "UNCERTAIN"

# نسخة طبق الأصل من نطاقات الحاكم: النطاق المتصل 064B–0670 يبتلع الأرقام
# الهندية 0660–0669، فتُكتب النطاقات بالهروب كما في Kotlin حرفاً بحرف.
_STRIP = re.compile("[ً-ٰٟۖ-ۭـ]")
_NON_ARABIC = re.compile("[^ء-ي ]")
# ⛔ **D-404:** الصورةُ الخامسةُ لقاعدة D-274 — ياءُ إمالةٍ **مجرّدةٌ** (‏U+064A ثم U+0670)
# لا علامةَ إمالةٍ تحتَها: رسمُ قالونَ وورشٍ. وتُكتب بالهروب لا بالحروف لأنَّ فيها نظرةً
# خلفيّةً سالبةً على علامتي الإمالة (‏U+06ED ميمٌ صغيرة · U+06EA وقفٌ أسفل) فيلتبس اتّجاهُ النصّ.
# 🔒 والنظرةُ الخلفيّةُ **تُبقي قاعدتي D-402/403 عاملتين** لا مستغنًى عنهما، فضابطُهما
# السالبُ في `RecitationNormParityTest` يظلّ صادقاً. (‏الذراع: `imala_bare_norm_arm.py`)
_BARE_IMALA = re.compile("(?<![\u06ed\u06ea])\u064a\u0670")
_SUBS = [("ٱ", "ا"), ("أ", "ا"), ("إ", "ا"), ("آ", "ا"),
         ("ؤ", "و"), ("ئ", "ي"), ("ى", "ي"), ("ة", "ه"), ("ء", "")]

INF = (2 ** 31 - 1) // 4


class Config:
    """إعدادات القياس — الافتراضي = سلوك الحاكم المشحون بالضبط.

    🏷️ **ووسمُ `⛔ENGINE-ABSENT`** على معلَمٍ يعني: **لا نظيرَ له في المحرك** — وُضع
    ليُسعَّر قبل أن يُكتب بالكوتلن. وحارسُ `fixture_audit.py` **يشتقّ هذه المعالمَ من
    الوسم نفسِه** ويسقط إن كان افتراضُ واحدٍ منها **مُشعلاً**: فالمرآةُ حينئذٍ تحكم
    بغير ما يحكم به المحرك، **وكلُّ رقمٍ تطبعه كذبٌ لا يصرخ**.

    تصحيح 2026-09-09: كان strip_yeh_barree=False في الافتراض، والمحرك يحوّل
    ے إلى ي منذ إصلاح سابق (~3000 موضع في رسم ورش وقالون). فكانت المرآة تحذفها
    حذفاً (وَفِے ⇒ وف بدل وفي) فتحسب الكلمة الصحيحة خطأً. لذلك كل رقم مطلق
    للمرآة قبل هذا اليوم يبخس المحرك، وخصوصاً في الروايتين. والمقارنات النسبية
    تبقى صحيحة لأن الذراعين مرّتا بالإعداد نفسه.
    القاعدة: «المشحون» في المرآة يعني ما في المحرك اليوم لا ما كان فيه.

    ⛔ **D-276 — العطبُ نفسُه عاد في بابين آخرين** (تدقيقُ المِسطرة، مناوبةٌ سحابية 2026-09-11):
    كان `dagger_optional=False` و`mark_sila=False` في الافتراض، و**المحرك يفعلهما بلا شرط**:
        RecitationScorer.variants ⇒ if (word.contains("ٰ")) out += norm(بلا خنجرية)
                                    if (word.contains('ۦ')) out += out[0] + "ي"   (وكذلك ۥ ⇒ "و")
    فكانت المرآةُ **ترفض** ما يقبله المحركُ اليوم: `ذَٰلِكَ` مرجعُها «ذالك» وحدَها، وwhisper يكتب
    «ذلك» ⇒ إبدالٌ مؤكَّد في المرآة، وصحيحٌ في المحرك. والدليلُ قاطعٌ من داخل العدّة نفسِها:
    `make_parity_fixture.py` يولّد حزمةَ التماثل بـ`dagger_optional=True, mark_sila=True`
    والنقل/الصلة بالرواية، ثمّ يطابقها اختبارُ `RecitationScorerParityTest` على المحرك الحقيقي
    حالةً بحالة — فالمقيسُ هناك **هو** المشحون، وما كان في `config_for("shipped")` إعدادٌ مهجور.
    المقيس (المصحف كلُّه، صورُ الكلمة المقبولة): تختلف في 9,226/82,008 كلمةً من حفص (11.25٪)
    و24,395/77,864 من ورش (31.33٪) و15,883/77,857 من قالون (20.40٪)؛ وفي عيّنة G1
    511/2,378 كلمة (21.49٪: حفص 11.36٪ · ورش 33.26٪ · قالون 18.50٪).
    ⇒ كلُّ رقمٍ مطلقٍ للمرآة موسومٍ «المشحون» قبل اليوم **يبخس المحرك**، والروايتان أشدُّ بخساً.
       والمقارناتُ النسبية تبقى صحيحةً لأن الذراعين مرّتا بالإعداد نفسِه.
    ⚠️ ولا يُغيَّر في المحرك شيء: العطبُ في المرآة وحدَها.
    """

    def __init__(self, match_num=1, match_den=5, khanjariya=True, extra_subs=(),
                 strip_yeh_barree=True, dagger_optional=True, naql=False, sila=None, mark_sila=True,
                 learner_tolerant=False, wide_uncertain=False, wide_uncertain_min=6,
                 unheard_lexicon=None, unheard_min_len=0, unheard_need_neighbour=False,
                 pair_forgive=None,
                 collapse_threshold=0.60, short_cap=3, phon=None, phon_cap=3,
                 dagger_madd=True, abs_cap=None, drop_subs=(), strict_short=False, critical_long=None):
        self.match_num, self.match_den = match_num, match_den
        # D-290: جدولُ الإبدال `_SUBS` (‏ة⇒ه · ى⇒ي · الهمزاتُ⇒ا · ء⇒حذف …) هو **أقدمُ رخصةٍ
        # في المِسطرة وأقلُّها فحصاً**: لم تُوزن واحدةٌ منه في دفتر D-286. وهذا المعلَمُ يُلغي
        # إبدالاتٍ بعينِها (بحرفِ المصدر) كي تُوزن كما وُزنت أخواتُها. **`()` = المشحون حرفاً
        # بحرف** (الجدولُ كاملاً) ولا يُغيَّر افتراضُه البتّة؛ الأذرعُ تُمرَّر في أداة القياس وحدَها.
        self.drop_subs = tuple(drop_subs)
        # 🎚️ **D-323 (جلسةُ التطبيق) — `criticalPairsUncertain`:** الزوجُ القصير (‏≤3 أحرف) يفرق بحرفٍ
        # واحدٍ يُحسب **صحيحاً** في المشحون، فـ«لم/لن · لا/ما · هو/هي · قل/كل · من/مع» تمرّ وهي كلماتٌ
        # يقلب إبدالُها المعنى. وبالتفعيل تسقط تلك الرخصةُ من `_matches` ويصير الحكمُ `UNCERTAIN`.
        # ‏`False` = **المشحون حرفاً بحرف** ولا يُغيَّر افتراضُه: كلُّ خطوط الأساس مقيسةٌ عليه.
        # ومرآةُ الكوتلن بنصّها: `matches` تُسقط `(!strictShort && n <= 3 && d <= 1)`، و`shortPairUncertain`
        # تُرجع `max(len(r), len(hyp)) <= 3 && edit(r, hyp) <= 1`.
        self.strict_short = strict_short
        # ⚖️ **خطة 2026-09-23 §4-ج — الأزواجُ الحرجة الطويلة** (مرآةُ `RecitationScorer.criticalPairsLong`):
        # مجموعةُ أزواجٍ `(a, b)` (a<b) من صور المصحف المطبَّعة بمسافة 1 وأطولُها ≥5 (‏`load_critical_long`)؛
        # فإن طابقت الصورةُ المسموعَ بقاعدة الخُمس وهي **غيرُه حرفاً** وكان الزوجُ في المجموعة سقطت
        # الرخصةُ لهذه الصورة ⇒ `_near` يجعلها `UNCERTAIN`. ‏`None` = بلا فهرس.
        self.critical_long = critical_long
        # D-283: بديلُ رخصةِ القصيرة المقترَحُ في D-282 §4 — جدولُ التباسٍ صوتيٍّ ضيّق.
        # None = **المشحون** (لا جدولَ البتّة) ⇒ السلوكُ الافتراضيُّ لا يتغيّر حرفاً.
        # "same" = إبدالُ حرفٍ واحدٍ من **مخرجٍ واحد**؛ "adj" = يضاف إليه المخرجُ المجاور.
        self.phon = phon
        self.phon_cap = phon_cap
        # D-282: سقفُ «رخصة الكلمة القصيرة» في `_matches`. **3 = المشحون** (‏ما في الكوتلن اليوم)؛
        # و0 يُلغيها؛ ولا يُغيَّر افتراضُه هنا البتّة — الأذرعُ تُمرَّر في أداة القياس وحدَها.
        self.short_cap = short_cap
        # D-286: قاعدةُ D-274/275 (‏`ىٰ`⇒`ى` و`اٰ`⇒`ا` قبل تحويل الخنجرية ألفاً) صارت معلَماً
        # كي تُوزن في دفتر الرخص كما تُوزن أخواتُها. **True = المشحون حرفاً بحرف**
        # (‏هو ما في `RecitationScorer.norm` اليوم) ولا يُغيَّر افتراضُه البتّة.
        self.dagger_madd = dagger_madd
        # D-289: سقفٌ **مطلق** لعدد التحريفات يُضاف فوق قاعدة النسبة (لا بدَلها) — ذراعُ
        # «تضييقٌ في الطويلة وحدَها». **None = المشحون حرفاً بحرف** (لا سقفَ البتّة)
        # ولا يُغيَّر افتراضُه البتّة؛ الأذرعُ تُمرَّر في أداة القياس وحدَها.
        self.abs_cap = abs_cap
        self.khanjariya = khanjariya
        self.extra_subs = list(extra_subs)
        self.strip_yeh_barree = strip_yeh_barree
        self.dagger_optional = dagger_optional
        self.naql = naql
        # D-248: صلةُ ميم الجمع مستقلةٌ عن النقل (قالون يصل ولا ينقل)؛ الافتراض القديم: تتبع النقل.
        self.sila = naql if sila is None else sila
        # D-248: صلةُ هاء الكناية/الميم حيث رسمها المصحف (ۦ/ۥ) — لكل الروايات.
        self.mark_sila = mark_sila
        # D-261: احتمالُ سلوك المتعلّم (تكرارٌ · بدايةٌ خاطئة · مقدّمةٌ قبل المدى) — انظر score().
        self.learner_tolerant = learner_tolerant
        # D-268: توسيعُ «غير متبيَّن» للكلمات الطويلة — كبحُ الاتّهام لا إسقاطُ الكشف.
        self.wide_uncertain = wide_uncertain
        self.wide_uncertain_min = wide_uncertain_min
        # مرآةُ حارس الانهيار (D-268) — العتبةُ نفسُها في المحرك.
        self.collapse_threshold = collapse_threshold
        # 🤫 **D-445 — قاعدةٌ تُسعَّر قبل أن تُكتب بالكوتلن، ⛔ ولا نظيرَ لها في المحرك اليومَ.**
        # المقيسُ: **267 من 359** اتّهاماً على الضجيج (74.4٪) مسموعُها **ليس صورةَ أيّ كلمةٍ في
        # المصحف** (`تسفسوا` · `رفهثا`) ⇒ فقولُ «أخطأت» عليها إخبارٌ بما لا يعلمه المحرك، والصوابُ
        # `UNCERTAIN` **وهو صنفٌ قائمٌ مشحونٌ** (D-231: يُعرَض ولا يُحسب زلّة) لا صنفٌ جديد.
        # ⛔⛔ **مطفأةٌ افتراضاً** (`None`): وبها **صفرُ تغييرٍ** فتبقى المرآةُ مرآةً وتبقى
        #     بصماتُ التماثل كما هي — وهذا هو الشرطُ الذي يجعل قياسَها مجّانيّاً.
        # ⛔ و**بعد** المحاذاة لا فيها: تكلفةُ الـDP لا تُلمَس (وإلّا تبدّلت المواضعُ فصار
        #     المقيسُ قاعدةً أخرى)، تماماً كحارس الانهيار — إعادةُ وسمٍ لا إعادةُ محاذاة.
        self.unheard_lexicon = unheard_lexicon      # ⛔ENGINE-ABSENT
        # 🎚️ **وتضييقان يُقاسان** (‏D-445③: القاعدةُ كما هي **مردودةٌ** — تكسب 4.55 من الاتّهام
        # الكاذب وتدفع **18.0 من الكشف**): `unheard_min_len` يقصرها على المسموع الطويل ·
        # و`unheard_need_neighbour` يشترط أن تكون **جارةُ الكلمة متَّهَمةً** أيضاً (‏فيقترب من
        # حارس الانهيار بمقياسٍ أدقَّ من نسبة الآية · وسندُه D-387: خطأُ الضجيج **متكتّلٌ**
        # 50٪ شرطيّاً مقابل 31٪ هامشيّاً، أمّا الإبدالُ المحقونُ فمفردٌ). **وكلاهما مطفأٌ.**
        self.unheard_min_len = unheard_min_len      # ⛔ENGINE-ABSENT
        self.unheard_need_neighbour = unheard_need_neighbour   # ⛔ENGINE-ABSENT
        # 💠 **بابُ D-443 المقفل** — قائمةُ أزواجٍ `(صورةُ المرجع، المسموع)` تُغفَر بأعيانها.
        # ⛔ **ولِمَ صار معلَماً بعد أن سُعّر بالنصّ:** ثمنُه هناك قِيس على **ما تقصده خطّةُ
        # الحقن** (مانحٌ كلمةٌ قرآنيّةٌ ⇒ «صفرُ توافق»)، و**درسُ D-445③ أنّ الثمنَ يُقاس على
        # ما يسمعه المحرك**: في الضجيج يُفرَّغ الموضعُ المحقونُ لا-كلمةً، فقد يوافق زوجاً في
        # القائمة فيُغفر **خطأٌ حقيقيّ**. ⇒ فيُقاس بالمسطرتَين كما قِيست أختُها. **ومطفأٌ.**
        self.pair_forgive = pair_forgive            # ⛔ENGINE-ABSENT

    def label(self):
        bits = [f"عتبة {self.match_num}/{self.match_den}"]
        if self.short_cap != 3:
            bits.append("بلا رخصة القصيرة" if self.short_cap <= 0 else f"رخصةُ القصيرة ≤{self.short_cap}")
        if self.phon:
            bits.append(f"جدولُ التباسٍ صوتيّ ({self.phon}) ≤{self.phon_cap}")
        if not self.dagger_madd:
            bits.append("بلا مدِّ الخنجرية (D-274/275)")
        if not self.khanjariya:
            bits.append("بلا خنجرية")
        if self.strip_yeh_barree:
            bits.append("ے→ي")
        if self.learner_tolerant:
            bits.append("يحتمل المتعلّم")
        if self.dagger_optional:
            bits.append("خنجرية اختيارية")
        if self.naql:
            bits.append("نقل")
        if self.sila:
            bits.append("صلة الميم")
        if self.mark_sila:
            bits.append("صلة ۦ/ۥ")
        if self.extra_subs:
            bits.append("+".join(a + "→" + b for a, b in self.extra_subs))
        return "، ".join(bits)


DEFAULT = Config()


def _apply_subs(w, cfg):
    subs = _SUBS + ([("ے", "ي")] if cfg.strip_yeh_barree else []) + cfg.extra_subs
    if cfg.drop_subs:                      # D-290: ذراعُ «الإبدالُ يُلغى» — افتراضُه فارغ
        subs = [(a, b) for a, b in subs if a not in cfg.drop_subs]
    for a, b in subs:
        w = w.replace(a, b)
    return w


def norm(word, cfg=DEFAULT):
    # ⛔ **D-274:** الخنجريّةُ فوق الألف المقصورة **هي نطقُها لا ألفٌ زائدة**:
    # `عَلَىٰ` تُقرأ «على» ويكتبها whisper «علي». فتحويلُها ألفاً يعطي «عليا» فتُحسب
    # الكلمةُ الصحيحة خطأً. وهي 159 موضعاً في أوّل ألفي آيةٍ من رسم ورش وحدَها.
    # ⛔ **D-275:** والخنجريّةُ فوق الألف كذلك **مدُّها لا ألفٌ ثانية**: `اٰمَنَ` هي «آمَنَ»
    # ويكتبها whisper «آمن» ⇒ «امن»، فتحويلُها ألفاً يعطي «اامن».
    # 📏 **تصحيحُ عددٍ (مناوبةٌ سحابية 2026-09-12 · D-322):** كان مكتوباً هنا وفي المحرك «847 كلمةً في
    # الروايات الثلاث (‏382 ورشاً · 261 قالون · 204 حفصاً)». وقِيس على أصول المستودع اليومَ
    # (‏237,729 كلمةً في الروايات الثلاث): الزوجُ الملتصق `اٰ` — وهو وحدَه ما تمسّه هذه القاعدة —
    # **177 موضعاً · 76 كلمةً فريدة · في ورشٍ وحدَها**، وصفرٌ في حفصٍ وقالون. ولا موضعَ واحدٌ
    # تفصل فيه حركةٌ بين الألف والخنجرية ⇒ ليست القاعدةُ أضيقَ من رسمها، بل العددُ كان أوسعَ منه.
    # ⚠️ والقاعدةُ **عاملةٌ لا زائدة**: حذفُها يقلب `اٰمَنَ` إلى «اامن» — يُثبته الضبطُ السالب في
    # `RecitationNormParityTest` (‏12 انحرافاً).
    # ⛔ **D-402 (مناوبةٌ سحابية 2026-09-12):** وصورةٌ ثالثةٌ للقاعدة نفسِها — **ألفُ الإمالة**
    # في رسم الدوريِّ والسوسيّ: تُكتب ياءً تحتها ميمٌ صغيرةٌ (`ۭ` U+06ED) وفوقها خنجريّة،
    # `مُوسۭيٰ` · `أَنّۭيٰ` · `اِ۬لۡقُرۡبۭيٰ`. والخنجريّةُ هنا **نطقُ الياء المُمالة لا ألفٌ زائدة**،
    # فتحويلُها ألفاً يعطي «موسيا» وwhisper يكتب «موسي» (وحفصٌ `مُوسَىٰ` ⇜ «موسي» بقاعدة D-274).
    # المقيس (المصحف كلُّه · الرواياتُ الستّ): الثلاثيُّ الملتصق `ۭيٰ` — وهو وحدَه ما تمسّه هذه
    # القاعدة — **859 موضعاً** (‏الدوري 446 · السوسي 413 · 380 كلمةً فريدة)، و**صفرٌ** في حفصٍ
    # وورشٍ وقالونَ وشعبةَ (‏`ۭ` فيها علامةُ الإقلاب لا الإمالة) ⇒ رقمُ D-288 سليمٌ بالبناء.
    # وكلفتُها مقيسةٌ صفراً: لا صورةً جديدةً تبتلع كلمةً قرآنيةً أخرى (`imala_norm_arm.py`).
    # ⛔ **D-404 (مناوبةٌ سحابية 2026-09-12):** وصورةٌ **خامسةٌ** للقاعدة نفسِها — ياءُ
    # الإمالة **مجرّدةً** بلا علامةٍ تحتَها في رسم **قالونَ وورش**: `أَدْرَيٰكَ` · `بَنَيٰهَا`.
    # المقيس (‏المصحف كلّه · الرواياتُ الستّ): **360 موضعاً** (‏قالون 335 · ورش 25)
    # و**صفرٌ** في حفصٍ وشعبةَ والدوريِّ والسوسيّ (‏وهذان يكتبان علامةَ الإمالة دائماً).
    # وضابطُها موافقةُ حفص: قبلَ القاعدة **صفرُ** موضعٍ يوافق تطبيعَ حفصٍ للكلمة نفسِها،
    # وبعدَها **149/149**؛ وكلفتُها مقيسةٌ صفراً (`imala_bare_norm_arm.py`).
    w = (word.replace("ىٰ", "ى").replace("اٰ", "ا").replace("ۭيٰ", "ۭي").replace("۪يٰ", "۪ي")
         if cfg.dagger_madd else word)
    w = _BARE_IMALA.sub("ي", w) if cfg.dagger_madd else w
    w = w.replace("ٰ", "ا") if cfg.khanjariya else w
    return _NON_ARABIC.sub("", _apply_subs(_STRIP.sub("", w), cfg))


def _edit(a, b):
    if a == b:
        return 0
    m, n = len(a), len(b)
    prev = list(range(n + 1))
    for i in range(1, m + 1):
        cur = [i] + [0] * n
        for j in range(1, n + 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1,
                         prev[j - 1] + (0 if a[i - 1] == b[j - 1] else 1))
        prev = cur
    return prev[n]


def variants(word, cfg=DEFAULT):
    """صور الكلمة المرجعية المقبولة. الثانية (عند dagger_optional) تُسقط الألف
    الخنجرية بدل نطقها ألفاً: المصحف يكتب ذَٰلِكَ/هَٰذَا/عَلَىٰ بألف فوقية،
    وwhisper يكتبها إملائياً ذلك/هذا/على — والصورتان رسمٌ واحدٌ لكلمة واحدة،
    فردُّ إحداهما خطأً **إنذارٌ كاذب** لا كشف. ولا يمسّ هذا الألف المرسومة
    (قال/قل، كان/كن) فتبقى أخطاء التلاوة الحقيقية مكشوفة."""
    a = norm(word, cfg)
    out = [a]
    if cfg.dagger_optional and "ٰ" in word:
        b = _NON_ARABIC.sub("", _apply_subs(_STRIP.sub("", word.replace("ٰ", "")), cfg))
        if b != a:
            out.append(b)
    if cfg.mark_sila:
        if "ۦ" in word:
            out.append(a + "ي")
        if "ۥ" in word:
            out.append(a + "و")
    return tuple(dict.fromkeys(out))


def _riwaya_forms(forms, cfg):
    """صور نطقية خاصة بورش/قالون (تُفعَّل بعلم الرواية لا دائماً):
    **النقل** — نقل حركة الهمزة إلى الساكن قبلها فتسقط ألف الوصل نطقاً
    (اَ۬لَايْكَةِ تُقرأ «لَيْكة»، اَ۬لَارْضِ «لَرْض»)؛
    **صلة ميم الجمع** — هُمُۥ/كُمُۥ تُشبع واواً (فأخذَهُمُو).
    لا تُفعَّل في حفص: إسقاط «ال» فيه خطأ تلاوة حقيقي يجب أن يُكشف."""
    if not (cfg.naql or cfg.sila):
        return forms
    out = list(forms)
    for f in forms:
        if cfg.naql and f.startswith("ال") and len(f) > 3:
            out.append(f[1:])
            # D-248: كرسيُّ الهمزة يسقط نطقاً مع النقل (اَ۬لَارْض ⇐ «لَرْض»)
            if f.startswith("الا") and len(f) > 4:
                out.append("ل" + f[3:])
        # 2026-09-06 (D-231): تاء الفاعل الجمعية «تم» تُوصَل بالميم أيضاً (زعمتمُو/قلتمُو) — قِيس على العيّنة.
        if cfg.sila and f.endswith(("هم", "كم", "تم")):
            out += [f + "و", f + "وا"]
    return tuple(dict.fromkeys(out))


# 🗣️ D-283 — جدولُ المخارج (بديلُ رخصةِ القصيرة المقترَحُ في D-282 §4).
# مبنيٌّ على **تقسيم المخارج المتعارَف** لا على الحالات التي نريد كسبَها، كي لا يكون
# الجدولُ مفصَّلاً على مقاسِ عيّنته. المجموعاتُ من مقدَّم الفم إلى مؤخَّره، وحروفُها
# **بعد التطبيع** (‏ء تسقط · أإآٱ⇒ا · ؤ⇒و · ئ/ى⇒ي · ة⇒ه):
_MAKHARIJ = (
    "بموف",              # ١ شفويّة
    "ثذظتدطسصزضلنر",     # ٢ طرفُ اللسان (لثويّة · نطعيّة · أسليّة · ذلقيّة)
    "جشي",               # ٣ وسطُ اللسان (شجريّة)
    "كقغخ",              # ٤ أقصى اللسان (لهويّة · طبقيّة)
    "عحه",               # ٥ الحلق والحنجرة
)
# ⚠️ الألفُ **ليست** في أيِّ مجموعة: مخرجُها الجوفُ وهي مدٌّ لا حرفَ احتكاكٍ أو شدّة،
# فإلحاقُها بالحلق يفتح `اه`⇄`عه` وأمثالَه بلا سندٍ صوتيّ.
_PLACE = {c: i for i, grp in enumerate(_MAKHARIJ) for c in grp}


def _phon_ok(r, hyp, cfg):
    """إبدالُ **حرفٍ واحدٍ** بحرفٍ من مخرجه (أو المخرجِ المجاور في `adj`) — وما عداه لا.

    شرطٌ صارم: الطولُ نفسُه وموضعُ اختلافٍ **واحد** (لا حذفَ ولا زيادة)، فالرخصةُ
    تحتمل التباسَ التعرّف في حرفٍ ولا تحتمل نقصَ كلمةٍ ولا زيادتَها.
    """
    if not cfg.phon or len(r) != len(hyp) or max(len(r), len(hyp)) > cfg.phon_cap:
        return False
    diff = [(a, b) for a, b in zip(r, hyp) if a != b]
    if len(diff) != 1:
        return False
    a, b = diff[0]
    pa, pb = _PLACE.get(a), _PLACE.get(b)
    if pa is None or pb is None:
        return False
    return pa == pb if cfg.phon == "same" else abs(pa - pb) <= 1


def _matches(ref, hyp, cfg):
    refs = ref if isinstance(ref, tuple) else (ref,)
    # 🛡️ الذراع V (‏D-819 · مرآةُ `RecitationScorer.matchesAny`): الفهرسُ يُغلق على **كلّ صور المرجع** —
    # إن كان المسموعُ أختاً في الفهرس لأيّ صورةٍ وليس هو إحداها ⇒ لا مطابقة (و`_near` يحكم «غير متبيَّن»).
    if cfg.critical_long and hyp not in refs and any(
            ((r, hyp) if r < hyp else (hyp, r)) in cfg.critical_long for r in refs):
        return False
    for r in refs:
        _n = max(len(r), len(hyp)); _d = _edit(r, hyp)
        # 2026-09-05 (أمر المالك: أقل حساسية): الخُمس يبقى، والقصيرة (≤3) تحتمل حرفاً (المقيس: B) — مطابق للكوتلن.
        # D-282: صار سقفُ الرخصة معلَماً (`short_cap`) وافتراضُه **3 = المشحون حرفاً بحرف**،
        # كي تُقاس الأذرعُ (‏≤2 · بلا رخصة) بلا مساسٍ بالسلوك المشحون ولا بحزمة التماثل.
        # D-289: `abs_cap` سقفٌ مطلقٌ يُضاف **شرطاً** على قاعدة النسبة، وافتراضُه None ⇒
        # التعبيرُ يعود حرفاً بحرف إلى المشحون (`_d * den <= num * _n or قصيرة`).
        if (_d * cfg.match_den <= cfg.match_num * _n
                and (cfg.abs_cap is None or _d <= cfg.abs_cap)):
            return True
        if not cfg.strict_short and _n <= cfg.short_cap and _d <= 1:
            return True
        # D-283: يُضاف **بعد** المشحون لا بدَله ⇒ افتراضُه (`phon=None`) لا يغيّر حكماً واحداً.
        if cfg.phon and _phon_ok(r, hyp, cfg):
            return True
    return False


_CRITICAL_LONG = {}


def load_critical_long(riwaya):
    """فهرسُ الأزواج الحرجة الطويلة للرواية من مورد المحرك (‏`make_critical_pairs_index.py`)."""
    if riwaya not in _CRITICAL_LONG:
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        path = os.path.join(root, "engine", "recitation", "src", "main", "resources", "tasmi", "critical_pairs.tsv")
        # المرآةُ العامّة بلا مورد المحرك: يُقرأ من مستودع الأصل المجاور إن وُجد (‏نسخةُ عملٍ في الجلسة).
        # ويُقدَّم مسارٌ صريحٌ في `CRITICAL_PAIRS_TSV` إن ضُبط.
        path = os.environ.get("CRITICAL_PAIRS_TSV") or path
        if not os.path.isfile(path):
            path = os.path.join(os.path.dirname(root), "QuranRafiq", "engine", "recitation", "src", "main",
                                "resources", "tasmi", "critical_pairs.tsv")
        bit = {"hafs": 1, "warsh": 2, "qalun": 4, "shuba": 8, "douri": 16, "sousi": 32}[riwaya]
        out = set()
        for line in open(path, encoding="utf-8"):
            if not line.strip() or line.startswith("#"):
                continue
            a, b, m = line.rstrip("\n").split("\t")
            if int(m) & bit:
                out.add((a, b))
        _CRITICAL_LONG[riwaya] = frozenset(out)
    return _CRITICAL_LONG[riwaya]


COLLAPSE_MIN_WORDS = 5


def _collapse_guard(words, cfg):
    """مرآةُ `RecitationScorer.collapseGuard` — حين ينهار التعرّف لا يُتَّهم أحد.

    يجب أن تبقى هذه الدالّة مطابقةً للمحرك حرفاً بحرف: العتبةُ نفسُها والحدُّ الأدنى نفسُه.
    (اختبارُ التماثل في المحرك يقارن الحكمَين حالةً بحالة، وقد كشف افتراقَهما ساعةَ فُعِّل.)
    """
    t = getattr(cfg, "collapse_threshold", 0.60)
    ws = [w for w in words if w is not None]
    if t <= 0 or len(ws) < COLLAPSE_MIN_WORDS:
        return words
    confirmed = sum(1 for w in ws if w[1] in (MISSED, SUBSTITUTED))
    if confirmed / len(ws) <= t:
        return words
    return [None if w is None else
            ((w[0], UNCERTAIN) + tuple(w[2:]) if w[1] in (MISSED, SUBSTITUTED) else w)
            for w in words]


def _unheard_guard(words, cfg):
    """🤫 **مرحلةٌ تُسعَّر ولا تُشحن (D-445): «لم أتبيّن» بدل «أخطأت» متى لم يكن المسموعُ كلمةً.**

    ⛔⛔ **ولا نظيرَ لها في المحرك اليومَ** — وهذا مكتوبٌ بقصد: المرآةُ **مرآةٌ**، وهذه المرحلةُ
    موضوعةٌ لتُقاس القاعدةُ على فرضيّاتٍ محفوظةٍ **قبل** أن تُكتب بالكوتلن. ومع `unheard_lexicon
    = None` (الافتراض) تُعيد القائمةَ **بالهويّة** ⇒ صفرُ تغييرٍ في بصمةٍ أو رقم.

    والقاعدةُ: `SUBSTITUTED` مسموعُها **ليس صورةَ أيّ كلمةٍ في المعجم** ⇒ `UNCERTAIN`.
    ⛔ و`MISSED` **لا تُلمَس**: لا مسموعَ لها أصلاً فلا يُقال «لم أتبيّن» عن صمت.

    ⭐ **وإسنادُها إلى صنفٍ قائم:** `UNCERTAIN` مشحونٌ ومعروضٌ ولا يُحسب زلّةً (D-231) ⇒ فليست
    قاعدةً تحتاج نصّاً جديداً في `app/` بل **شرطاً جديداً لصنفٍ قائم**.
    """
    lex = getattr(cfg, "unheard_lexicon", None)
    if not lex:
        return words
    min_len = getattr(cfg, "unheard_min_len", 0)
    need_nb = getattr(cfg, "unheard_need_neighbour", False)
    # ⛔ والجيرةُ تُقرأ من **القائمة قبل التعديل** فلا تتسلسل: كلمةٌ صارت «لم أتبيّن» لا تُصيّر
    #    جارتَها كذلك، وإلّا انهارت الآيةُ كلُّها بحكمٍ واحد (‏وذلك بابُ حارس الانهيار لا هذا).
    accused = {w[0] for w in words if w is not None and w[1] in (MISSED, SUBSTITUTED)}
    out, hit = [], False
    for w in words:
        if (w is not None and w[1] == SUBSTITUTED and w[2]
                and norm(w[2], cfg) not in lex
                and len(norm(w[2], cfg)) >= min_len
                and (not need_nb or (w[0] - 1) in accused or (w[0] + 1) in accused)):
            out.append((w[0], UNCERTAIN) + tuple(w[2:]))
            hit = True
        else:
            out.append(w)
    return out if hit else words


def _pair_forgive_guard(words, ref, cfg):
    """💠 مرآةُ **البابِ المقفل** (D-443) — ⛔ ولا نظيرَ لها في المحرك، وهي **للتسعير وحدَه**.

    `pair_forgive` مجموعةُ `(k, h)`: `k` **صورةُ المرجع الأولى** و`h` المسموعُ مطبَّعاً؛
    فمتى وافق الزوجُ صار الحكمُ `CORRECT` — فهي **رخصةٌ** لا امتناع (‏والفرقُ في الجدول:
    الرخصةُ تُسقط الكشفَ حيث وافقت، والامتناعُ يُحوّله «غيرَ متبيَّن» وكلاهما لا يُعَدّ كشفاً).
    ⛔ ومع `None` تُعاد القائمةُ **بالهويّة** ⇒ صفرُ تغيير.
    ⛔ و`MISSED` لا تُلمَس: لا مسموعَ لها فلا زوجَ يوافقها.
    """
    pf = getattr(cfg, "pair_forgive", None)
    if not pf:
        return words
    out, hit = [], False
    for w in words:
        if (w is not None and w[1] in (SUBSTITUTED, UNCERTAIN) and w[2]
                and 0 <= w[0] < len(ref) and ref[w[0]]
                and (ref[w[0]][0], norm(w[2], cfg)) in pf):
            out.append((w[0], CORRECT) + tuple(w[2:]))
            hit = True
        else:
            out.append(w)
    return out if hit else words


def _uncertain(ref, hyp, cfg):
    """⚠️ **شرطُ «غير متبيَّن» الواحد** — مرآةُ `RecitationScorer.nearAny` بشطرَيه:
    `if (hyp.length < 4) return shortPairUncertain(...)` ثمّ حدُّ التحرير الموسَّع للروايتَين.

    ⛔ **ولماذا دالّةٌ واحدةٌ لا شرطان:** كان الحكمُ يستعمل `_near or _short_pair_uncertain`
    و**تكلفةُ المحاذاة تستعمل `_near` وحدَها** ⇒ مع `strict_short` صار المحركُ يعدّ زوجاً قصيراً
    مشكوكاً **رخيصاً (1)** والمرآةُ تعدّه **إبدالاً (2)**، فاختلف مسارُ الـDP، وضخّم حارسُ الانهيار
    (0.60) الفرقَ فهبط التماثلُ على `g3r` إلى 96.47٪ (‏D-332 §٣). فصار الشرطُ **مصدراً واحداً**:
    من غيّره غيّر الحكمَ والتكلفةَ معاً، ولا يتفارقان.
    """
    return _near(ref, hyp, cfg) or _short_pair_uncertain(ref, hyp, cfg)


def _short_pair_uncertain(ref, hyp, cfg):
    """مرآةُ `RecitationScorer.shortPairUncertain`: زوجٌ قصير (‏≤3) بفارق حرفٍ ⇒ شكٌّ لا صحّة."""
    if not cfg.strict_short:
        return False
    refs = ref if isinstance(ref, tuple) else (ref,)
    return any(max(len(r), len(hyp)) <= 3 and _edit(r, hyp) <= 1 for r in refs)


def _near(ref, hyp, cfg):
    """⚠️ D-231 «غير متبيَّن»: لا تطابق، لكن الفرق حرفٌ واحدٌ في كلمةٍ من أربعة فأكثر — خطأُ تعرّفٍ
    محتمل بقدر ما هو زلّةٌ محتملة؛ يُعرض لا يُخفى ولا يُحسب زلّةً مؤكّدة."""
    refs = ref if isinstance(ref, tuple) else (ref,)
    if len(hyp) < 4:
        return False
    # 🎚️ نطاقُ «غير متبيَّن» بحسب الطول (D-268 مقترَح): الكلمةُ الطويلة يكفي فيها
    # حرفان لأن رسمَ ورشٍ وقالون يفارق ما يكتبه whisper بأكثر من حرفٍ كثيراً،
    # فيصير الحكمُ «إبدالاً» واثقاً على كلمةٍ صحيحة. والحقنُ الحقيقيّ كلمةٌ أخرى
    # كاملة فمسافتُه أكبر بكثير — فلا يُبتلع.
    # مرآةُ المحرك (D-271): التوسيعُ للروايتين الصغريين وحدَهما — يُستدلّ عليهما بالنقل أو الصلة.
    minor = bool(cfg.naql or cfg.sila)
    wide = cfg.wide_uncertain if cfg.wide_uncertain else minor
    limit = 2 if (wide and len(hyp) >= cfg.wide_uncertain_min) else 1
    return any(_edit(r, hyp) <= limit for r in refs)


# 🎛️ **مفتاحٌ مطفأٌ ينتظر قياساً** (‏D-366): «الحمد لله **كتاب** رب العالمين» تُقرأ **إبدالاً**
# (‏رب ⇐ كتاب) + دمجاً، لا إقحاماً — لأنّ الكلفتَين متعادلتان (3 = 2 + 1). فيُقال للقارئ
# «أبدلتَ» وهو **قد قال الكلمةَ صحيحةً وزاد غيرَها**.
#
# ⛔ **وترجيحُ الإقحام عند التعادل ليس قاعدةً محليّة** (جُرِّب ففشل): التعادلُ يظهر في **الخانة
# التي يلتقي فيها المسارانِ**، لا عند خطوة الإقحام. ⇒ فالصوابُ **ترتيبٌ معجميّ**: تُصغَّر الكلفةُ
# أوّلاً، **ثمّ عددُ الإبدالات** — فيُختار عند التساوي المسارُ الذي **لا يتّهم كلمةً صحيحة**.
# ويُنفَّذ بضربِ الكلف في 16 وزيادةِ 1 على الإبدال: الترتيبُ الأوّلُ محفوظٌ حرفاً، والثاني يفصل
# المتعادلات وحدَها. ⛔ ومطفأٌ افتراضاً — يمسّ كلَّ حكمٍ مشحونٍ فلا يُفعَّل إلّا بشوط بوّابة.
PREFER_INSERT_ON_TIE = False
_SC = 16          # مضاعفُ الكلفة — يُبقي الترتيبَ الأوّل سليماً
_SUB_TIE = 1      # ثمنٌ رمزيٌّ للإبدال يفصل المتعادلات وحدَها


def score(ref_words, hyp_text, cfg=DEFAULT):
    """يعيد dict: words (verdict لكل كلمة مرجعية) + additions."""
    ref = [_riwaya_forms(variants(w, cfg), cfg) for w in ref_words]
    hyp = [w for w in (norm(x, cfg) for x in re.split(r"\s+", hyp_text)) if w]
    R, H = len(ref), len(hyp)
    dp = [[INF] * (H + 1) for _ in range(R + 1)]
    back = [[None] * (H + 1) for _ in range(R + 1)]
    dp[0][0] = 0
    for i in range(R + 1):
        for j in range(H + 1):
            d = dp[i][j]
            if d == INF:
                continue

            def relax(ni, nj, cost, op, i=i, j=j, d=d, sub=False):
                if ni > R or nj > H or cost >= INF:
                    return
                # 🎛️ الترتيبُ المعجميّ: الكلفةُ ×16 ثمّ ثمنُ الإبدال الرمزيّ (عند التفعيل وحدَه).
                c = cost * _SC + (_SUB_TIE if (sub and PREFER_INSERT_ON_TIE) else 0) if PREFER_INSERT_ON_TIE else cost
                if d + c < dp[ni][nj]:
                    dp[ni][nj] = d + c
                    back[ni][nj] = (i, j, op)

            if i < R and j < H:
                _c = 0 if _matches(ref[i], hyp[j], cfg) else (1 if _uncertain(ref[i], hyp[j], cfg) else 2)
                relax(i + 1, j + 1, _c, 0, sub=(_c == 2))
            if i < R:
                relax(i + 1, j, 3, 1)
            if j < H:
                # D-261: زيادةٌ يعرفها الشيخ ولا يعدّها خطأً — تكلفتُها 1 لا 3:
                #  (أ) تكرارُ كلمةٍ قيلت للتوّ (المتعلّم يشكّ فيعيد)
                #  (ب) بدايةٌ خاطئة: يقرأ كلمتين ثم يعود إلى أول الآية
                #  (ج) مقدّمةٌ قبل المدى (استعاذة/بسملة) — زوائدُ في الصدر قبل أن تُصاب أيُّ مرجعية
                # ولا تُجعل صفراً: الصفرُ يبتلع الزيادةَ الحقيقية أيضاً.
                cheap = getattr(cfg, "learner_tolerant", False) and (
                    any(_matches(ref[k], hyp[j], cfg) for k in range(max(0, i - 2), i))
                    or any(_matches(ref[k], hyp[j], cfg) for k in range(i, min(R, i + 3)))
                    or (i == 0 and j < 6)
                )
                relax(i, j + 1, 1 if cheap else 3, 2)
            if i < R and j + 1 < H:
                relax(i + 1, j + 2, 1 if _matches(ref[i], hyp[j] + hyp[j + 1], cfg) else INF, 3)
            if i + 1 < R and j < H:
                joined = tuple(a + b for a in ref[i] for b in ref[i + 1])
                relax(i + 2, j + 1, 1 if _matches(joined, hyp[j], cfg) else INF, 4)

    words = [None] * R
    additions = []
    located = []   # 📍 (نصُّ الزائدة، موضعُها من كلمات المرجع) — مرآةُ `Score.locatedAdditions`
    i, j = R, H
    while i > 0 or j > 0:
        b = back[i][j]
        if b is None:
            break
        pi, pj, op = b
        if op == 0:
            words[pi] = (pi, CORRECT if _matches(ref[pi], hyp[pj], cfg) else (UNCERTAIN if _uncertain(ref[pi], hyp[pj], cfg) else SUBSTITUTED), hyp[pj])
        elif op == 1:
            words[pi] = (pi, MISSED, None)
        elif op == 2:
            # 📍 **الموضعُ `pi` لا `pj`:** عمليةُ الزيادة لا تُقدّم المرجعَ، فالزائدةُ تُنطق **قبل**
            # الكلمة المرجعية ذاتِ الفهرس `pi` (و`R` يعني «بعد آخر كلمة»). مرآةُ `RecitationScorer`.
            additions.insert(0, hyp[pj])
            located.insert(0, (hyp[pj], pi))
        elif op == 3:
            words[pi] = (pi, CORRECT, hyp[pj] + " " + hyp[pj + 1])
        elif op == 4:
            words[pi] = (pi, CORRECT, hyp[pj])
            words[pi + 1] = (pi + 1, CORRECT, hyp[pj])
        i, j = pi, pj
    for k in range(R):
        if words[k] is None:
            words[k] = (k, MISSED, None)
    # 🛑 وعلمُ الانهيار **بالهويّة** كما في المحرك: الحارسُ يُعيد القائمةَ نفسَها حين لا يُطلق.
    # (‏يُحتاج إليه لقياس تهدئةٍ مرشَّحة: «لا تُعرَض الزوائدُ حين انهار التعرّفُ أصلاً» · D-369.)
    _pre = words
    words = _collapse_guard(words, cfg)
    # 🛑 **والعلَمُ يُقرأ هنا لا في آخر السطر** (‏تصحيحٌ 2026-09-15 · D-537): كان
    # `collapsed` يُحسب في `return` بمقايسة الهويّة **بعد** المرحلتَين التاليتَين، وهما
    # تُعيدان قائمةً جديدةً متى أطلقت إحداهما ⇒ **فبابُ D-445 وحدَه كان يُرفع علَمَ
    # الانهيار كذباً** (مقيسٌ: بندٌ فيه 32 إبدالاً صار «انهياراً» وما انهار). وبالأبواب
    # مطفأةً (‏وهو المشحون) المرحلتان تُعيدان **الهويّة** ⇒ **صفرُ تغييرٍ في رقمٍ منشورٍ
    # أو بصمةِ تماثل**، والعلَمُ صار يعني ما يقوله اسمُه: **أأطلق حارسُ الانهيار؟**
    _collapsed = words is not _pre
    # 🤫 وبعد الانهيار لا قبلَه (‏D-445): لو سبقته هذه المرحلةُ لهبط عدُّ «المؤكَّد» فما أطلقت
    #    الانهيارَ أصلاً ⇒ قاعدتان تتداخلان ورقمٌ لا يُعرف صاحبُه. والترتيبُ يُقاس لا يُفترض.
    words = _unheard_guard(words, cfg)
    # 💠 وبابُ D-443 بعدهما: غفرانُ زوجٍ بعينه يجعل الكلمةَ **صحيحةً** (لا «غيرَ متبيَّنة»)
    #    فهو **رخصةٌ** لا امتناع — والفرقُ بينهما في الجدول: الرخصةُ تُسقط الكشفَ حيث وافقت.
    words = _pair_forgive_guard(words, ref, cfg)
    return {"words": words, "additions": additions, "located": located, "collapsed": _collapsed,
            "correct": sum(1 for w in words if w[1] == CORRECT), "total": R}
