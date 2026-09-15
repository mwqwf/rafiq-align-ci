# -*- coding: utf-8 -*-
"""⏱️ **زمنُ الفكّ بذراعَين على العتاد الذي تُشغَّل عليه** — بلا تطبيقٍ وبلا جهاز المالك.

⛔ **لماذا وُجدت** (‏D-334): محاكي العدّاء `x86_64` **لا يُظهر انهيارَ `greedy`** أصلاً (صفرُ بندٍ من
ستّين)، وعلى هاتف المالك `arm64` انهار في بندَين من عشرةٍ فبلغ RTF 1.63 — ونسبةُ بطءِ الهاتف عن
العدّاء تتراوح **×1.77 إلى ×9.26** في `greedy` و×1.32 إلى ×2.86 في `beam 5`. فالسؤالُ «هل يبوّب
الحرسُ أسوأَ الحالات؟» كان مفتوحاً بلا أداة، وإذنُ الهاتف استُنفد. وعدّاءُ `ubuntu-*-arm` يعطينا
**المعماريةَ نفسَها مجّاناً وبلا جهازه** — فإن ظهر الانهيارُ هناك صار السؤالُ مقيساً في كلّ شوط.

    python tools/tasmi_bench/cli_time.py --cli build/bin/whisper-cli --model work/ggml-q8.bin \\
        --src work/g4 --plan work/long_plan.json --threads 2 --md work/arm_time.md

⚠️ **الأمانةُ في الحدود:** هذا ليس أندرويد (‏bionic غيرُ glibc، والمعالجُ غيرُ معالجِه)، فلا يُنقل رقمُه
إلى جهاز المستخدم رقماً مطلقاً. الذي يُقاس هنا **سلوكٌ**: أيتفجّر `greedy` على `arm64` أم لا.
"""
import argparse
import json
import os
import re
import statistics as st
import subprocess
import sys
import time


ARMS = {
    # المشحونُ اليوم: greedy بعتبةِ إنتروبيا 2.40 (افتراضُ المكتبة)
    "greedy": ["-bs", "1", "-et", "2.40"],
    # ‏`decodeGuard`: بحثُ حزمةٍ 5 وعتبةٌ أضيق 1.80.
    # ⛔⛔ **وتصحيحٌ في موضعه — كان مكتوباً هنا «مرآةُ `jni.c` حرفاً بحرف» وهو غيرُ صحيح**
    #    (‏قِيس من المصدر المثبَّت 2026-09-15 · D-522): `whisper_full_default_params` تُعبّئ
    #    `greedy.best_of = 5` **في حالة GREEDY وحدَها**، وفي BEAM_SEARCH تُعبّئ `beam_search`
    #    وتترك `greedy.best_of` على **‎−1** (`whisper.cpp:6087` مقابل 6126). و`jni.c` لا يضبطها
    #    البتّة ⇒ في أشواط **التراجع الحراريّ** (‏`t > 0`) يقرأ المحرّكُ
    #    `n_decoders_cur = greedy.best_of` (‏سطر 7169/7175) فيصير **مفكّاً واحداً**؛
    #    أمّا `whisper-cli` فيضبط `wparams.greedy.best_of = 5` **دائماً** (`cli.cpp:1242`).
    #    ⇒ **هذه الذراعُ أقوى من المشحون** في أصعب النوافذ بعينها، ومرآةُ المشحون هي `shipguard`.
    #    (‏وذراعُ `greedy` مرآةٌ صحيحةٌ: كلاهما 5 هناك.)
    "guard": ["-bs", "5", "-et", "1.80"],
    # 🪞 **مرآةُ المشحون الصحيحة** (‏D-522): حزمةُ 5 + عتبةُ 1.80 + **`-bo 1`** — أي
    #    مفكٌّ واحدٌ في أشواط التراجع كما هي حالُ `jni.c` اليومَ بالضبط. وهي **أرضيّةُ
    #    القياس** التي يُطرح منها نفعُ `best_of`: `shipguard` ⇒ المشحون · `guard` ⇒ المشحونُ
    #    ومعه ترشيحُ خمسةِ مرشَّحين في النوافذ الصعبة. ⛔ والفرقُ بينهما **سطرٌ واحدٌ في `jni.c`**.
    "shipguard": ["-bs", "5", "-et", "1.80", "-bo", "1"],
    # 🔇 **ذراعُ D-513**: المشحونُ نفسُه + **رفعُ إسكاتِ النافذة** (`no_speech_thold`).
    #    المصدرُ المثبَّت (`whisper.cpp@c4ac001:7711`) يُسقط **النافذةَ كلَّها** (ثلاثين ثانية)
    #    حين `no_speech_prob > 0.6` **و**`avg_logprobs < -1.0` ⇒ آياتٌ متتاليةٌ تختفي دفعةً.
    #    و`1.01` احتمالٌ **لا يُبلَغ** ⇒ يُبطل الإسقاطَ وحدَه ولا يمسّ عتبةَ الثقة ولا الإنتروبيا.
    #    ⚠️ وهي **مرآةُ مفتاح `WhisperDecode.hearAll`** لا التطبيقُ نفسُه (‏حدُّ الأداة في رأسها).
    "hearall": ["-bs", "1", "-et", "2.40", "-nth", "1.01"],
    # 🧪 **ذراعُ تثبُّتٍ لا مرشَّح** (‏أُضيفت 2026-09-15 · D-516): شوطُ D-515 أعطى الذراعَين
    #    **متطابقتَين حرفاً** (372 كلمةً · 0/20 فارغ)، وذلك **ما تتوقّعه الآليّةُ إن لم تشتعل
    #    البوّابةُ قطُّ** — ⛔ **وهو أيضاً ما يُتوقَّع لو كانت الرايةُ خاملة**. وذراعان متطابقتان
    #    سؤالٌ لا جواب (D-385) ⇒ فهذه تقلب الشرطَين إلى **الصدق دائماً**:
    #    `no_speech_prob > 0.0` **و**`avg_logprobs < 1.0` (‏واللوغاريتمُ سالبٌ أبداً) ⇒
    #    **كلُّ نافذةٍ تُسكَت**. فإن خرج التفريغُ فارغاً فالمسارُ **حيٌّ** وسالبُ D-515 حكم؛
    #    وإن لم يخرج فارغاً فالرايةُ خاملةٌ و**قياسُ D-515 لاغٍ**.
    #    ⛔⛔ **ولا تُشحن بحال**: هي **أسوأُ** من المشحون بالبناء — تُسكت كلَّ شيء.
    "silenceall": ["-bs", "1", "-et", "2.40", "-nth", "0.0", "-lpt", "1.0"],
    # 🧩 **ذراعا التقطيع** (‏D-530): **رايات المشحون حرفاً** — والفرقُ الوحيدُ أنّ الملفَّ
    #    يُفكّ قِطَعاً (‏عشرَ ثوانٍ = سقفُ `GROUP_CAP_SECONDS` المشحون · وستٌّ للحدّ الأدنى).
    "chunk10": ["-bs", "1", "-et", "2.40"],
    "chunk6": ["-bs", "1", "-et", "2.40"],
    # 🛡️ **والتقطيعُ ومعه حارسُ الذيل** (‏D-532): الرايات نفسُها والتقطيعُ نفسُه،
    #    **والفرقُ الوحيدُ** تشذيبُ المقطوعات التي تبدأ بعد آخر صوتٍ في المقطع —
    #    وهو ما يفعله `LongAudioTranscriber.tailGuard` في التطبيق ولا تملكه أداةُ المقعد.
    #    ⇒ `chunk10` مقابل `chunk10g` **يقيس ما يوفّره الحارسُ من هَلوَسةِ الحشو** (D-531).
    "chunk10g": ["-bs", "1", "-et", "2.40"],
    "chunk6g": ["-bs", "1", "-et", "2.40"],
}

# 🧩 **أذرعٌ تُفكُّ الملفَّ قِطَعاً لا دفعةً** (‏أُضيفت 2026-09-15 · D-530): القيمةُ **ثوانيَ
#    المقطع**. ⛔ **ولِمَ لزمت:** مربّعُ D-528 قاس أنّ **الطويلَ المضجَّج ينهار** (36.5٪) و**القصيرَ
#    المضجَّج لا ينهار** (82.4٪)، وD-529 وجد الآليّةَ في التطبيق: في الضجيج **لا سكتةَ تُكتشف**
#    فيتوقّف التقطيعُ ويُفرَّغ التسجيلُ كلُّه. **وعلاجُه بُني مطفأً** (`FALLBACK_CAP_SECONDS`)
#    ⇒ والسؤالُ الباقي: **كم يستعيد التقطيعُ فعلاً على مفكٍّ حقيقيّ؟** ويُقاس **بلا محاكٍ ولا
#    APK**: `whisper-cli` يقبل `-ot` (إزاحة) و`-d` (مدّة) ⇒ المقطعُ يُفكّ من الملفّ نفسِه.
#    ⚠️ **وحدُّها يُقال:** القطعُ هنا **عند حدودٍ ثابتةٍ** لا عند أهدأ نقطةٍ كما يفعل التطبيق
#    (`quietestCut`) ⇒ **ما تعطيه هذه الذراعُ أرضيّةٌ لا سقفٌ**: التطبيقُ يقطع أرحمَ منها.
ARM_CHUNK = {"chunk10": 10, "chunk6": 6, "chunk10g": 10, "chunk6g": 6}

# 🛡️ **وأذرعٌ تُطبّق حارسَ الذيل بعد كلّ مقطع** — مرآةُ `tailGuard` بسماحه المشحون.
ARM_TAILGUARD = {"chunk10g", "chunk6g"}

# 🏷️ عنوانُ كلّ ذراعٍ في الجدول — والمجهولُ يُسمّى باسمه لا بفراغ.
ARM_LABEL = {
    "greedy": "greedy",
    "guard": "beam 5 + et 1.8 + bo 5",
    "shipguard": "🪞 المشحون: beam 5 + et 1.8 + bo 1",
    "hearall": "greedy + nth 1.01",
    "silenceall": "⚠️ تثبُّتٌ: إسكاتٌ دائم",
    "chunk10": "🧩 قِطَعُ 10ث (سقفُ التطبيق)",
    "chunk6": "🧩 قِطَعُ 6ث",
    "chunk10g": "🧩🛡️ قِطَعُ 10ث + حارسُ الذيل",
    "chunk6g": "🧩🛡️ قِطَعُ 6ث + حارسُ الذيل",
}
_NUM = re.compile(r"([0-9]+\.[0-9]+)")


def silence_stats(rows_arm):
    """🔇 **بنودٌ خرج تفريغُها فارغاً** — وهي بصمةُ إسقاطِ النافذة (‏D-513).

    ترجع (‏عددَ الفارغة · عددَ الكلمات كلِّها). ⛔ و«فارغٌ» يعني **لا كلمةَ واحدة** بعد
    التشذيب — لا «قليلٌ»: فالقليلُ حكمُ دقّةٍ لا حكمُ إسكات.
    """
    empty = sum(1 for r in rows_arm.values() if not (r.get("text") or "").strip())
    words = sum(len((r.get("text") or "").split()) for r in rows_arm.values())
    return empty, words


def _default_judges():
    """🧭 حاكمُ الصور من أدواتنا نفسِها — لا مسطرةٌ ثانيةٌ تتقادم صامتةً.

    يرجع ثلاثةَ توابع: مرجعُ البند من المصحف · صورُ الكلمة المقبولة · تشذيبُ المسموع.
    ⛔ **والاستيرادُ متأخّرٌ**: `--selftest` يجب أن يعمل في صندوقٍ بلا بيانات (درسُ `soundfile`).
    """
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, here)
    sys.path.insert(0, os.path.join(os.path.dirname(here), "alignment"))
    import error_triage as ET
    import score as SC
    import scorer as SCR
    from common import load_index, load_text
    index = load_index()
    cfgs = {}

    def cfg(riw):
        if riw not in cfgs:
            cfgs[riw] = SC.config_for("proposed", riw)
        return cfgs[riw]

    return (lambda iid: ET.item_words(iid, load_text, index),
            lambda w, riw: ET.forms_of(w, cfg(riw), SCR),
            lambda w, riw: SCR.norm(w, cfg(riw)),
            # ⛔⛔ **وقبولُ الحاكم لا عضويّةُ مجموعة** (‏تصحيحٌ قبل النشر · D-523): `scorer._matches`
            #    هو ما يقبل به المحرّكُ فعلاً — **مسافةُ تحريرٍ ≤ خُمسِ الطول** ومعها رخصةُ
            #    القصيرة (‏≤3 حروفٍ تحتمل حرفاً) — وليس التطابقَ حرفاً. ومن قاس بالعضويّة
            #    **نقَص عدَّه عن حاكمه**: «الرحمان» مقابل «الرحمٰن» يقبلها الحاكمُ وترفضها هي.
            lambda fs, tok, riw: SCR._matches(tuple(fs), tok, cfg(riw)))


def judges_with_plan(plan_ref, base=None):
    """🧭 **ومرجعُ البند من الخطّة حين لا يُقرأ معرّفُه** (‏أُضيف 2026-09-15 · D-523).

    ⛔ **العطبُ الذي وُجدت له:** `error_triage.parse_item` يقرأ صيغةَ الطويل وحدَها
    (`long_<رواية>_<سورة>_<آية>x<عدد>`)، **وخطّةُ الآية المفردة معرّفاتُها من شكلٍ آخر**
    (`hafs_minshawi_015076`) ⇒ كلُّ بندٍ قصيرٍ كان يُعَدّ **مجهولاً** فلا يُقاس على المادّة
    القصيرة شيء — وهي **مادّةُ الحلقة الحيّة** التي يتوقّف عليها سؤالُ `guardScope`.
    ⭐ **والمرجعُ حاضرٌ في الخطّة نفسِها** (`refText` · `riwaya`) ⇒ يُقرأ منها لا من فرضيّة.
    ⛔ **والأولويّةُ للمصحف**: ما قرأه `item_words` لا تنسخه الخطّةُ (فالمصحفُ أصلٌ والخطّةُ نقل).
    """
    rw, fo, no, ac = base or _default_judges()

    def ref(iid):
        got = rw(iid)
        if got and got[1]:
            return got
        alt = plan_ref.get(iid)
        return alt if alt and alt[0] and alt[1] else (None, None)

    return ref, fo, no, ac


def bag_stats(rows_arm, ref_words=None, forms=None, norm=None, accepts=None):
    """🔁 **كم من كلمات المرجع عادت · وكم قِيل بلا مرجع** — كِيساً لا خطَّ محاذاة.

    ⭐ **لِمَ وُجد** (‏حدُّ D-519 بنصّه): عدُّ الكلمات وحدَه **ليس صواباً** — كلمةٌ خطأٌ تُعَدّ
    كلمةً، فذراعٌ ترفع العددَ قد تكون استعادت وقد تكون هَلوَست. ⇒ يُقاس **عددان لا واحد**:
      · **الاستعادة** = كلماتُ المرجع التي وُجد لها مقابلٌ مقبول ÷ كلماتِ المرجع.
      · **الزائد** = المسموعُ الذي لم يقابل كلمةَ مرجعٍ ÷ المسموعِ كلِّه.
    فالمرشَّحُ النافعُ **ترتفع استعادتُه ولا يرتفع زائدُه**؛ ومن ارتفع الاثنان فيه فقد
    قايض فقداً بهَلوَسة، **وهي ثمنٌ لا مكسب**.

    ⛔⛔ **وحدُّ هذه المسطرة يُقال قبل أن يُبنى عليها** — فهي **ليست** حاكمَ التسميع:
      ① **كِيسٌ لا ترتيب**: كلمةٌ سُمعت في موضعٍ غيرِ موضعها تُحسب استعادةً ⇒ الرقمُ
         **سقفٌ** للصواب لا الصوابُ نفسُه. وحكمُ الصواب لـ`scorer.py` على خطِّ المحاذاة.
      ② **الالتقاطُ جَشِعٌ** بترتيب المسموع (أوّلُ مرجعٍ غيرِ مستهلَكٍ يقبلُه)، وكلماتُ المرجع
         تُستهلَك مرّةً واحدة ⇒ **حلقةُ تكرارٍ لا تُقرأ استعادةً** (وهي الفخُّ الأوّلُ هنا).
      ③ **ما تعذّر مرجعُه يُعَدّ مجهولاً ويُعلَن، ولا يُبَنّ في الطرفَين** (درسُ `floor_shape`):
         بندٌ بلا مرجعٍ لا يُنقص الاستعادةَ ولا يُضخّم الزائد.
      ④ **والقبولُ قبولُ الحاكم لا التطابقُ حرفاً** (‏صُحّح قبل النشر · D-523): `scorer._matches`
         يقبل **مسافةَ تحريرٍ ≤ خُمسِ الطول** ومعها رخصةُ القصيرة ⇒ مَن قاس بالعضويّة وحدَها
         **نقَص عدَّه عن حاكمه**. ويُطبَع العددان: `hit` بقبول الحاكم و`exact` مطابقاً حرفاً،
         **والتطابقُ يُلتقَط أوّلاً** كي لا يستهلكَ جارٌ فضفاضٌ صورةً بعينها.
      ⑤ **و`heard` هنا يُعَدّ بعد التشذيب** ⇒ قد يقلّ بواحدٍ أو اثنَين عن صفّ «كلماتٌ مسموعةٌ
         كلّيّاً» (‏وهو عدٌّ خامٌ بالمسافات): رمزٌ يُشذَّب إلى فراغٍ ليس كلمةً هنا. **عدّان
         تعريفاهما مختلفان، فلا يُطرح أحدهما من الآخر.**
    """
    if ref_words is None:
        ref_words, forms, norm, accepts = _default_judges()
    if accepts is None:
        accepts = lambda fs, tok, riw: tok in fs     # ⛔ صارمةٌ: للضوابط المُحقَنة وحدَها
    ref_n = heard_n = hit = exact = dropped = 0
    unknown = []
    for iid in sorted(rows_arm):
        riw, words = ref_words(iid)
        if not words:
            unknown.append(iid)
            continue
        pool = [list(forms(w, riw)) for w in words]
        used = [False] * len(pool)
        ref_n += len(pool)
        raw = (rows_arm[iid].get("text") or "").split()
        toks = [t for t in (norm(x, riw) for x in raw) if t]
        # 📣 **وما أسقطه التشذيبُ يُعلَن لا يُسكت عنه** (‏D-523): `scorer.norm` يُفرّغ ما ليس
        #    عربيّاً ⇒ **هَلوَسةٌ لاتينيّةٌ تختفي من الطرفَين** («thank you for watching» ⇒ صفر).
        #    فلو كان العددُ كبيراً لكان الحكمُ «لا يسمع» وصفاً خاطئاً للعطب: هو يتكلّم بغير
        #    لغته. ⇒ يُعَدّ ويُطبَع، **وهو نفسُه الذي يفسّر فرقَ المقامَين في الجدول**.
        dropped += len(raw) - len(toks)
        heard_n += len(toks)
        for t in toks:
            # ⭐ **والتطابقُ حرفاً يُقدَّم على القبول الفضفاض**: لو جاء المسموعُ صورةَ كلمةٍ
            #    بعينها فلا يُستهلَك بها جارٌ يقبله الحاكمُ بمسافةِ حرفٍ ⇒ العدُّ **لا يُبدَّد**.
            k = next((i for i, fs in enumerate(pool) if not used[i] and t in fs), None)
            if k is not None:
                exact += 1
            else:
                k = next((i for i, fs in enumerate(pool) if not used[i] and accepts(fs, t, riw)), None)
            if k is not None:
                used[k] = True
                hit += 1
    return {"ref": ref_n, "heard": heard_n, "hit": hit, "exact": exact,
            "excess": heard_n - hit, "dropped": dropped, "unknown": unknown}


# 🧩 أقصرُ ذيلٍ يُفرَد مقطعاً — وما دونه يُضَمّ إلى ما قبله (ثانيتان: شوطٌ على أقلَّ منهما
#    ليس قياساً، وwhisper قد يسكت عنه فيُقرأ صفراً).
MIN_TAIL_MS = 2000

# 🛡️ **سماحُ حارس الذيل — من المحرك حرفاً** (`LongAudioTranscriber.TAIL_SLACK_MS = 500`).
#    ⛔ ولا يُغيَّر هنا وحدَه: مرآةٌ تفترق عن أصلها تقيس غيرَ ما يُشحن.
TAIL_SLACK_MS = 500


_TS = re.compile(r"^\[(\d+):(\d+):(\d+)\.(\d+)")


def seg_start_ms(line):
    """طابعُ بداية المقطوعة بالملّي من سطرِ `whisper-cli` — أو `None` إن لم يُقرأ.

    ⛔ **و`None` ليست صفراً**: مقطوعةٌ بلا طابعٍ **لا تُشذَّب** (‏الشكُّ لا يُسقط كلاماً).
    """
    m = _TS.match(line)
    if not m:
        return None
    h, mi, sec, frac = m.groups()
    return ((int(h) * 60 + int(mi)) * 60 + int(sec)) * 1000 + int(frac.ljust(3, "0")[:3])


def tail_trim(segs, limit_ms, slack_ms=TAIL_SLACK_MS):
    """🛡️ **مرآةُ `LongAudioTranscriber.tailGuard` حرفاً** (‏D-532).

    القاعدةُ في المحرك: تُشذَّب المقطوعاتُ **من الذيل** ما دام طابعُ بدايتها
    `>= voicedEndMs + slackMs`، **ويُتوقَّف عند أوّل واحدةٍ دونَه** — فليست تصفيةً عامّةً
    تُسقط كلَّ ما تجاوز الحدَّ حيث وقع. ⇒ ومقطوعةٌ متجاوزةٌ **يليها** ما هو دون الحدّ
    **تبقى**، وهذا سلوكُ المحرك بعينه لا تبسيطٌ له (وضابطٌ سالبٌ يثبّته).
    ⛔ **وما لا طابعَ له لا يُشذَّب** (`None`)، و`limit_ms <= 0` ⇒ لا تشذيب.
    """
    if limit_ms <= 0:
        return segs
    end = len(segs)
    while end > 0:
        st = segs[end - 1][0]
        if st is not None and st >= limit_ms + slack_ms:
            end -= 1
        else:
            break
    return segs[:end]


def chunk_spans(dur_sec, chunk_sec):
    """🧩 **سلَّمُ الإزاحات** — (إزاحةٌ بالملّي · مدّةٌ بالملّي) تغطّي المدّةَ كلَّها بلا تداخل.

    ⛔ **ولا مقطعَ فارغٌ في الذيل**: بقيّةٌ أقصرُ من عشرِ ملّيّاتٍ **تُضَمّ** إلى ما قبلها
    بدل أن تُفكَّ وحدَها (‏شوطٌ على 3م.ث ليس قياساً، والأداةُ قد تسكت عنه فيُقرأ صفراً).
    """
    if chunk_sec <= 0:
        raise SystemExit("⛔ طولُ المقطع ثوانٍ موجبةٌ لا %r" % chunk_sec)
    total = int(round(dur_sec * 1000))
    step = int(chunk_sec * 1000)
    out = []
    off = 0
    while off < total:
        left = total - off
        # ⛔ **ويُنظَر إلى ما سيبقى، لا إلى ما بقي:** لو كان الذيلُ بعد هذا المقطع أقصرَ من
        #    [MIN_TAIL_MS] ضُمّ إليه الآن. (وأوّلُ صياغةٍ كتبتُها نظرت إلى `left` فأفردت
        #    ذيلاً 1.6ث على 21.6 — وأسقطها ضابطُها قبل أن تُدفع.)
        if left <= step + MIN_TAIL_MS:
            out.append((off, left))
            break
        out.append((off, step))
        off += step
    return out or [(0, total)]


def run_one(cli, model, wav, arm, threads, lang, dur_sec=None):
    """يعيد (ثوانيَ الاستدلال بلا التحميل، عددَ المقاطع، النصَّ) — أو يرفع إن سكتت الأداة.

    🧩 وذراعُ تقطيعٍ (`ARM_CHUNK`) تُنادي الأداةَ **مرّةً لكلّ مقطع** بـ`-ot`/`-d`،
    وتجمع الأزمنةَ والنصوص. ⛔ **وزمنُ التحميل مطروحٌ في كلّ نداء** (‏كما هو أصلاً) ⇒
    **لا يُحتسب تحميلُ النموذج مرّاتٍ**، وهو الصوابُ: التطبيقُ يُحمّل مرّةً ويفكّ قِطَعاً.
    """
    chunk = ARM_CHUNK.get(arm)
    if chunk:
        if not dur_sec:
            raise SystemExit("⛔ ذراعُ تقطيعٍ بلا مدّةٍ للملفّ — ولا تُخمَّن المدّة")
        sec = 0.0
        segs = 0
        parts = []
        guard = arm in ARM_TAILGUARD
        for off_ms, len_ms in chunk_spans(dur_sec, chunk):
            s1, n1, t1, sg = _run_cli(cli, model, wav,
                                      ARMS[arm] + ["-ot", str(off_ms), "-d", str(len_ms)],
                                      threads, lang)
            sec += s1
            if guard:
                # 🛡️⛔ **والطوابعُ مطلقةٌ في الملفّ لا نسبيّةٌ للمقطع — قُرئ من المصدر لا ظُنّ**
                #    (`whisper.cpp@c4ac001`): `seek_start = params.offset_ms/10` (‏سطر 6964)
                #    و`t0 = seek + 2*(…)` (‏سطر 7731) ⇒ **الطابعُ يحمل الإزاحةَ**.
                #    ⇒ الحدُّ **`off_ms + len_ms`** لا `len_ms`. ⭐ **وأوّلُ صياغةٍ كتبتُها
                #    استعملت `len_ms`** — وكانت ستُشذّب كلَّ مقطعٍ بعد الأوّل تشذيباً شبهَ تامٍّ
                #    وتُخرج «حارساً ينفع» كذباً؛ **والمصدرُ أسقطها قبل أن تُنفَق عليها دقيقة**.
                sg = tail_trim(sg, off_ms + len_ms)
                t1 = " ".join(t for _, t in sg)
            segs += len(sg) if guard else n1
            if t1.strip():
                parts.append(t1.strip())
        return sec, segs, " ".join(parts)
    sec, n, text, _ = _run_cli(cli, model, wav, ARMS[arm], threads, lang)
    return sec, n, text


def _run_cli(cli, model, wav, flags, threads, lang):
    cmd = [cli, "-m", model, "-t", str(threads), "-l", lang, "-ojf"] + flags + [wav]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (p.stdout or "") + (p.stderr or "")
    if "usage:" in out and "error:" in out:
        raise SystemExit(f"⛔ الأداةُ ردّت الاستعمالَ لا نتيجةً (رايةٌ غيرُ مدعومة): {out[:200]}")
    load = tot = None
    for ln in out.splitlines():
        if " load time" in ln:
            m = _NUM.search(ln); load = float(m.group(1)) if m else None
        elif " total time" in ln:
            m = _NUM.search(ln); tot = float(m.group(1)) if m else None
    if load is None or tot is None:
        # ⛔ **ورسالةُ العطب لا تنكسر عند الحاجة إليها** (‏أُصلح 2026-09-15): كانت تُقحم
        #    `arm` وهو **غيرُ معروفٍ هنا** بعد تفكيك الدالّة ⇒ `NameError` يحجب السببَ
        #    الحقيقيَّ في اللحظة التي يُقرأ فيها. **ومسارُ خطإٍ مكسورٌ أسوأُ من لا رسالة.**
        raise SystemExit("⛔ لا زمنَ في مخرَج الأداة لـ%s (رايات %s) ⇒ لا يُحتسب صفراً:\n%s"
                         % (os.path.basename(wav), " ".join(flags), out[-400:]))
    lines = [ln for ln in out.splitlines() if ln.startswith("[")]
    segs = [(seg_start_ms(ln), re.sub(r"^\[[^\]]*\]\s*", "", ln).strip()) for ln in lines]
    text = " ".join(t for _, t in segs)
    return (tot - load) / 1000.0, len(segs), text, segs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cli", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--src", required=True, help="مجلدُ ملفّات wav")
    ap.add_argument("--plan", default="", help="‏json فيه items بمفاتيح id و durationSec (اختياريّ — وإلّا فمن الملفّ)")
    ap.add_argument("--threads", type=int, default=2, help="⚠️ سياسةُ التطبيق: عدُّ الأنوية التي تردّدها فوق الأدنى")
    ap.add_argument("--lang", default="en", help="‏D-308/D-313: المشحونُ يُخدم بـen صريحاً")
    ap.add_argument("--limit", type=int, default=0)
    # 🎛️ **والذراعان تُسمّيان** (‏أُضيف 2026-09-15 · D-515): الافتراضُ **هو المشحونُ سلفاً**
    #    (`greedy,guard`) فلا يتبدّل رقمٌ منشور، ومن أراد ذراعاً أخرى سمّاها في الطلب.
    ap.add_argument("--arms", default="greedy,guard",
                    help="ذراعان بالاسم من ARMS مفصولتان بفاصلة (الافتراض: greedy,guard)")
    ap.add_argument("--md", default="")
    ap.add_argument("--json", default="")
    a = ap.parse_args()

    # ⏱️ **المدّةُ من الملفّ إن لم تكن في الخطّة** (2026-09-13): `sample.json` — وهي خطّةُ الآية
    # المفردة — **لا تحمل `durationSec` أصلاً** (‏202 بندٍ · صفرُ مدّة)، فكان الشوطُ يموت بـ«لا ملفَّ
    # له مدّة» وكأنّ المجموعةَ غائبة، والمجموعةُ حاضرةٌ والمدّةُ في الملفّ نفسِه. ⇒ الخطّةُ صارت
    # **تحسيناً لا شرطاً**: ما لم تُسمِّ مدّتَه تُقرأ من ترويسة الـwav.
    arms = [x.strip() for x in a.arms.split(",") if x.strip()]
    if len(arms) != 2:
        raise SystemExit(f"⛔ ذراعان بالاسم لا {len(arms)}: {a.arms}")
    if arms[0] == arms[1]:
        raise SystemExit("⛔ ذراعان متطابقتان سؤالٌ لا جواب (D-385)")
    for x in arms:
        if x not in ARMS:
            raise SystemExit(f"⛔ ذراعٌ لا تُعرف: {x} — والمعروفُ {' · '.join(ARMS)}")
    A, B = arms

    dur = {}
    plan_ref = {}
    if a.plan:
        plan = json.load(open(a.plan, encoding="utf-8"))
        items = plan["items"] if isinstance(plan, dict) else plan
        dur = {it["id"]: it.get("durationSec") for it in items if it.get("durationSec")}
        # 📖 **والمرجعُ من الخطّة للبنود التي لا يقرأ `parse_item` معرّفَها** (‏الآيةُ المفردة)
        plan_ref = {it["id"]: (it.get("riwaya"), (it.get("refText") or "").split())
                    for it in items if it.get("refText") and it.get("riwaya")}
        if plan_ref:
            print(f"📖 {len(plan_ref)} بنداً مرجعُه في الخطّة (‏سَنَدٌ للقصير)", flush=True)
    files = sorted(f for f in os.listdir(a.src) if f.endswith(".wav"))
    if a.limit:
        files = files[: a.limit]
    if not files:
        raise SystemExit(f"⛔ لا ملفَّ wav في {a.src} — لا يُقرأ الصفرُ نتيجةً")
    miss = 0
    for f in files:
        if not dur.get(f[:-4]):
            # 📦 **وحملُ `soundfile` هنا لا في الرأس** (‏2026-09-15): كان استيراداً علويّاً
            #    ⇒ **`--selftest` نفسُه لا يعمل** إلا في بيئةٍ فيها عدّةُ الصوت، وضابطٌ لا
            #    يُشغَّل في الصندوق حارسٌ نصفُ حاضر. والقراءةُ لا تحدث إلا هنا أصلاً.
            import soundfile as sf
            info = sf.info(os.path.join(a.src, f))
            dur[f[:-4]] = info.frames / float(info.samplerate)
            miss += 1
    if miss:
        print(f"⏱️ {miss} بنداً مدّتُها من الملفّ لا من الخطّة", flush=True)
    print(f"⏱️ {len(files)} بنداً · خيوط {a.threads} · لغة {a.lang}", flush=True)

    rows = {}
    for k, f in enumerate(files, 1):
        i = f[:-4]
        for arm in (A, B):   # متداخلتان لكلّ بندٍ كي تتقاسما حالةَ الحرارة
            s, n, txt = run_one(a.cli, a.model, os.path.join(a.src, f), arm, a.threads, a.lang,
                                dur_sec=dur[i])
            rows.setdefault(arm, {})[i] = {"sec": s, "rtf": s / dur[i], "segs": n, "text": txt}
        if k % 5 == 0 or k == len(files):
            print(f"   … {k}/{len(files)}", flush=True)

    def q(v, p):
        v = sorted(v); x = (len(v) - 1) * p; lo = int(x)
        return v[lo] if lo == x else v[lo] + (v[lo + 1] - v[lo]) * (x - lo)

    L = [f"### ⏱️ زمنُ الفكّ على `{os.uname().machine if hasattr(os, 'uname') else '?'}` · {len(files)} بنداً · {a.threads} خيطاً\n",
         f"| المقياس | {ARM_LABEL.get(A, A)} | {ARM_LABEL.get(B, B)} |", "|---|---:|---:|"]
    for lab, fn in (("RTF وسيطاً", lambda v: q(v, .5)), ("RTF p90", lambda v: q(v, .9)),
                    ("RTF أقصى", max), ("زمنٌ كلّيٌّ ÷ صوتٌ كلّيّ", None)):
        if fn is None:
            tb = sum(r["sec"] for r in rows[A].values()) / sum(dur[i] for i in rows[A])
            tg = sum(r["sec"] for r in rows[B].values()) / sum(dur[i] for i in rows[B])
            L.append(f"| {lab} | {tb:.3f} | {tg:.3f} |")
            continue
        L.append(f"| {lab} | {fn([r['rtf'] for r in rows[A].values()]):.3f} | "
                 f"{fn([r['rtf'] for r in rows[B].values()]):.3f} |")
    for t in (1.0,):
        cb = sum(1 for r in rows[A].values() if r["rtf"] > t)
        cg = sum(1 for r in rows[B].values() if r["rtf"] > t)
        L.append(f"| **بنودٌ يتجاوز فيها الزمنَ الحقيقيّ (‏RTF>{t:g})** | **{cb}/{len(files)}** | **{cg}/{len(files)}** |")
    # 🔇 **وصفُّ الإسكات — وهو المقصودُ من ذراع `hearall`** (‏D-513): بندٌ خرج تفريغُه **فارغاً**
    #    هو «لم أسمع شيئاً» بعينها. ويُقرأ **مع عدد الكلمات**: فارغٌ يهبط وكلماتٌ تُزاد = سمعٌ
    #    عاد؛ وفارغٌ يهبط وكلماتٌ تنفجر = هَلوَسةٌ على صمت، **والثانيةُ ثمنٌ لا مكسب**.
    ea, wa = silence_stats(rows[A])
    eb, wb = silence_stats(rows[B])
    L.append(f"| 🔇 **بنودٌ تفريغُها فارغ** | **{ea}/{len(files)}** | **{eb}/{len(files)}** |")
    L.append(f"| 📝 كلماتٌ مسموعةٌ كلّيّاً | {wa} | {wb} |")
    # 🔁 **والعددُ وحدَه لا يُقرأ حكماً** (‏حدُّ D-519): تُقاس **الاستعادةُ والزائدُ** معاً.
    # ⛔ وتعذُّرُ الحاكم لا يُقرأ صفراً ولا يُسقط الشوط — يُكتب بنصِّ خطئه في الجدول نفسِه.
    bags = {}
    try:
        J = judges_with_plan(plan_ref) if plan_ref else (None, None, None, None)
        ba, bb = bag_stats(rows[A], *J), bag_stats(rows[B], *J)
        bags = {A: ba, B: bb}
        for lab, key, tot in (("🔁 **استعادةٌ بقبول الحاكم**", "hit", "ref"),
                              ("🔁 منها مطابقٌ حرفاً", "exact", "ref"),
                              ("👻 زائدٌ لا يقابل مرجعاً", "excess", "heard")):
            def pct(d):
                return f"{d[key]}/{d[tot]} = **{100.0 * d[key] / d[tot]:.1f}٪**" if d[tot] else "—"
            L.append(f"| {lab} | {pct(ba)} | {pct(bb)} |")
        if ba["dropped"] or bb["dropped"]:
            L.append(f"| 🗑️ رمزٌ أسقطه التشذيب (‏ليس عربيّاً) | {ba['dropped']} | {bb['dropped']} |")
        if ba["unknown"]:
            L.append(f"| ⚠️ بنودٌ بلا مرجعٍ (مجهولةٌ لا مبنَّنة) | {len(ba['unknown'])} | {len(bb['unknown'])} |")
    except Exception as e:
        L.append(f"| ⛔ مسطرةُ الاستعادة تعذّرت | `{type(e).__name__}: {e}` | — |")
    rat =[rows[B][i]["sec"] / rows[A][i]["sec"] for i in rows[A]]
    L.append(f"\n**نسبةُ {ARM_LABEL.get(B, B)} إلى {ARM_LABEL.get(A, A)}:** وسيطاً ×{st.median(rat):.2f} · المدى ×{min(rat):.2f}–×{max(rat):.2f} "
             f"· الحرسُ أسرعُ في {sum(1 for x in rat if x < 1)}/{len(rat)} بنداً")
    # 🔍 وأثرُ الانهيار يُسمّى: بنودٌ نسبتُها دون 1 هي التي انهار فيها greedy
    bad = sorted(((rows[A][i]["rtf"], i) for i in rows[A]), reverse=True)[:5]
    L.append(f"\n**أسوأُ خمسةٍ في {ARM_LABEL.get(A, A)}:** " + " · ".join(f"`{i}` RTF {r:.2f}" for r, i in bad))
    # 🧠 **وذروةُ الذاكرة تُقاس مع الزمن لا بعده** (‏أُضيفت 2026-09-14 لثمن D-432): رفعُ عدد
    # الخيوط يشتري زمناً **بذاكرةٍ** (‏كلُّ خيطٍ في ggml مخزنُه)، فلا يُقرأ الكسبُ بلا ثمنِه.
    # ⛔ **وحدُّ ما يقيسه `ru_maxrss` لـ`RUSAGE_CHILDREN`:** ذروةُ **أكبرِ ابنٍ انتهى** — وكلُّ
    # ابنٍ هنا تفريغةٌ واحدة ⇒ فهو **ذروةُ تفريغةٍ واحدةٍ في هذه الذراع** لا مجموعَ البنود.
    # وعلى لينكس بالكيبيبايت (‏وهي بيئةُ الأشواط كلِّها). وغيابُ `resource` لا يُسقط القياسَ.
    peak_kb = None
    try:
        import resource
        peak_kb = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    except Exception:
        pass
    if peak_kb:
        L.append(f"\n**ذروةُ ذاكرةِ تفريغةٍ واحدةٍ (‏أكبرُ ابن):** {peak_kb / 1024.0:.1f} م.ب "
                 f"بـ{a.threads} خيطاً")
    md = "\n".join(L)
    print("\n" + md)
    if a.md:
        open(a.md, "w", encoding="utf-8").write(md + "\n")
    if a.json:
        json.dump({"threads": a.threads, "lang": a.lang, "arms": [A, B], "peak_rss_kb": peak_kb,
                   "silence": {A: silence_stats(rows[A]), B: silence_stats(rows[B])},
                   "bag": bags, "rows": rows},
                  open(a.json, "w", encoding="utf-8"), ensure_ascii=False)


def _selftest():
    fails = []

    def ok(c, m):
        if not c:
            fails.append(m)

    # ① ذراعُ D-513 هي المشحونةُ + رفعُ الإسكات وحدَه
    ok(ARMS["hearall"][:4] == ARMS["greedy"], "‏hearall تبدأ بذراع المشحون حرفاً")
    ok(ARMS["hearall"][4:] == ["-nth", "1.01"], "‏hearall تضيف `-nth 1.01` ولا شيءَ غيرَه")
    ok("-bs" in ARMS["hearall"] and ARMS["hearall"][ARMS["hearall"].index("-bs") + 1] == "1",
       "‏hearall تبقى greedy لا حزمة")
    # ⛔⛔ **والحارسُ يُشدَّد لا يُخفَّف:** الخطرُ في **إرخاء** عتبةِ الثقة (قبولُ فكٍّ رديء)،
    #    فيبقى ممنوعاً بالرقم؛ و**تشديدُها** في ذراع تثبُّتٍ لا يَشحن شيئاً — بل يُسكت أكثر.
    for _n, _v in ARMS.items():
        if "-lpt" in _v:
            _lpt = float(_v[_v.index("-lpt") + 1])
            ok(_lpt > -1.0, f"⛔ ذراعُ {_n} تُرخي عتبةَ الثقة ({_lpt} دون −1.0) — ممنوع")
            ok(_n == "silenceall", f"⛔ ذراعٌ غيرُ التثبُّت تمسّ عتبةَ الثقة: {_n}")
    ok("-lpt" not in ARMS["hearall"] and "-lpt" not in ARMS["greedy"],
       "⛔ ولا المشحونُ ولا مرشَّحُ D-513 يمسّانها")
    ok(ARMS["silenceall"][ARMS["silenceall"].index("-nth") + 1] == "0.0",
       "ذراعُ التثبُّت تُشعل البوّابةَ دائماً")
    ok(float(ARMS["hearall"][-1]) > 1.0, "‏العتبةُ احتمالٌ لا يُبلَغ (> 1.0)")
    ok(set(ARM_LABEL) >= set(ARMS), "لكلّ ذراعٍ عنوانٌ في الجدول")
    # ⑤ **ومرآةُ المشحون تختلف عن `guard` بـ`-bo` وحدَه** (‏D-522) — فلو تساوَتا لضاع السؤال.
    ok(ARMS["shipguard"][:4] == ARMS["guard"], "‏shipguard تبدأ بذراع الحرس حرفاً")
    ok(ARMS["shipguard"][4:] == ["-bo", "1"], "‏shipguard تضيف `-bo 1` ولا شيءَ غيرَه")
    ok("-bo" not in ARMS["guard"], "⛔ و`guard` تُترك على افتراض الأداة (5) فالفرقُ مقيسٌ لا مبنيّ")
    ok("-nth" not in ARMS["shipguard"] and "-lpt" not in ARMS["shipguard"],
       "⛔ مرآةُ المشحون لا تمسّ عتبةَ إسكاتٍ ولا ثقة")

    # ② عدُّ الإسكات
    R = {"a": {"text": ""}, "b": {"text": "   "}, "c": {"text": "ولا الضالين"}}
    e, w = silence_stats(R)
    ok(e == 2, f"الفارغُ اثنان (والفراغُ بمسافاتٍ فارغٌ) — جاء {e}")
    ok(w == 2, f"الكلماتُ اثنتان — جاءت {w}")
    ok(silence_stats({}) == (0, 0), "لا بنودَ ⇒ صفران بلا انفجار")
    ok(silence_stats({"a": {}}) == (1, 0), "بندٌ بلا مفتاح `text` يُعَدّ فارغاً لا يُسقط الأداة")

    # ③ **مسطرةُ الاستعادة والزائد** — بحاكمٍ مُحقَنٍ كي تُقاس في صندوقٍ بلا مصحف.
    #    (والحقنُ هو نفسُه ما يجعل الضابطَ يُشغَّل دائماً لا في بيئةِ البيانات وحدَها.)
    REF = {"i1": ("hafs", ["الحمد", "لله", "رب"]), "i2": ("hafs", ["مالك", "يوم"])}
    fake_ref = lambda iid: REF.get(iid, (None, None))
    # صورتان مقبولتان لكلمةٍ واحدة — كي يُقاس أنّ المسطرةَ تسأل الحاكمَ لا تُقارن حرفاً
    fake_forms = lambda w, riw: ["رب", "ربي"] if w == "رب" else [w]
    fake_norm = lambda w, riw: w.strip("،.")

    def bag(texts):
        return bag_stats({k: {"text": v} for k, v in texts.items()}, fake_ref, fake_forms, fake_norm)

    b = bag({"i1": "الحمد لله رب"})
    ok((b["ref"], b["hit"], b["excess"]) == (3, 3, 0), f"تفريغٌ مطابقٌ ⇒ استعادةٌ تامّةٌ بلا زائد — جاء {b}")
    b = bag({"i1": "الحمد لله ربي"})
    ok(b["hit"] == 3, f"صورةٌ ثانيةٌ مقبولةٌ تُحسب استعادةً (الحاكمُ لا الحرف) — جاء {b}")
    b = bag({"i1": "الحمد رب"})
    ok((b["hit"], b["ref"], b["excess"]) == (2, 3, 0), f"كلمةٌ ساقطةٌ تُنقص الاستعادةَ ولا تصير زائداً — جاء {b}")
    b = bag({"i1": "الحمد لله رب العالمين"})
    ok((b["hit"], b["heard"], b["excess"]) == (3, 4, 1), f"مسموعٌ بلا مرجعٍ يُعَدّ زائداً — جاء {b}")
    # 🗑️ وما يُفرّغه التشذيبُ يُعَدّ ويُعلَن — لا يختفي من الطرفَين صامتاً
    b = bag_stats({"i1": {"text": "الحمد لله رب"}}, fake_ref, fake_forms, lambda w, r: "" if w == "لله" else w)
    ok((b["dropped"], b["heard"], b["hit"]) == (1, 2, 2),
       f"⛔ المُفرَّغُ يُعَدّ مُسقَطاً ويخرج من المقام — جاء {b}")
    ok(bag({"i1": "الحمد لله رب"})["dropped"] == 0, "ولا يُعَدّ مُسقَطاً ما لم يُفرَّغ")
    # ⛔⛔ **الفخُّ الأوّل:** حلقةُ تكرارٍ ترفع العددَ — ولا يجوز أن ترفع الاستعادة.
    b = bag({"i1": "الحمد الحمد الحمد لله رب"})
    ok(b["hit"] == 3 and b["excess"] == 2,
       f"⛔ حلقةُ تكرارٍ: المرجعُ يُستهلَك مرّةً والمكرّرُ زائدٌ — جاء {b}")
    # ⛔ وما لا مرجعَ له يُعلَن ولا يُبَنّ في الطرفَين (درسُ `floor_shape`)
    b = bag({"iX": "كلامٌ كثيرٌ جدّاً"})
    ok(b["unknown"] == ["iX"] and (b["ref"], b["heard"], b["hit"]) == (0, 0, 0),
       f"⛔ بندٌ بلا مرجعٍ مجهولٌ لا مبنَّن — جاء {b}")
    b = bag({"i1": "", "i2": "مالك يوم"})
    ok((b["ref"], b["hit"], b["heard"]) == (5, 2, 2), f"فارغٌ لا يُسقط ولا يُحتسب زائداً — جاء {b}")
    ok(bag({})["ref"] == 0 and bag({})["unknown"] == [], "لا بنودَ ⇒ أصفارٌ بلا انفجار")
    for t in ("الحمد لله رب", "الحمد الحمد", "", "كلمةٌ غريبة"):
        b = bag({"i1": t})
        ok(b["excess"] >= 0 and b["hit"] <= b["ref"] and b["hit"] <= b["heard"],
           f"⛔ حدودُ المسطرة تُنتهك على «{t}»: {b}")
        ok(b["exact"] <= b["hit"], f"⛔ المطابقُ حرفاً لا يزيد على المقبول: {b}")

    # ④ **وقبولُ الحاكم يُقاس بحاكمٍ مُحقَنٍ يحاكي مسافةَ حرف** (‏D-523): فالعضويّةُ وحدَها
    #    كانت **تنقص عن الحاكم**، والبندُ كلُّه قام على هذا التصحيح.
    def ed1(fs, tok, riw):
        for f in fs:
            if abs(len(f) - len(tok)) <= 1 and sum(1 for a, b in zip(f, tok) if a != b) <= 1:
                return True
        return False

    def bagj(texts, ref=None):
        return bag_stats({k: {"text": v} for k, v in texts.items()},
                         ref or fake_ref, fake_forms, fake_norm, ed1)

    REF2 = {"i1": ("hafs", ["الرحمن", "مالك"])}
    b = bagj({"i1": "الرحمان مالك"}, lambda i: REF2.get(i, (None, None)))
    ok(b["hit"] == 2 and b["exact"] == 1,
       f"⛔ صورةٌ بمسافة حرفٍ يقبلها الحاكمُ وتُعَدّ خارجَ المطابق حرفاً — جاء {b}")
    b = bagj({"i1": "الرحمان"}, lambda i: REF2.get(i, (None, None)))
    ok(b["excess"] == 0, f"⛔ ما قبله الحاكمُ ليس زائداً — جاء {b}")
    # ⛔ والتطابقُ يُلتقَط أوّلاً: «قل» لا تستهلك «قال» فيبقى المطابقُ حرفاً صادقاً
    REF3 = {"i1": ("hafs", ["قل", "قال"])}
    b = bagj({"i1": "قال قل"}, lambda i: REF3.get(i, (None, None)))
    ok(b["hit"] == 2 and b["exact"] == 2,
       f"⛔ التطابقُ حرفاً يُلتقَط أوّلاً فلا يُبدَّد عدٌّ — جاء {b}")
    # ⛔ وحاكمٌ فضفاضٌ لا يخلق استعادةً من لا شيء
    b = bagj({"i1": ""}, lambda i: REF3.get(i, (None, None)))
    ok((b["hit"], b["exact"], b["excess"]) == (0, 0, 0), f"⛔ فارغٌ بحاكمٍ فضفاضٍ صفرٌ — جاء {b}")

    # ⑤ **والسقوطُ إلى مرجع الخطّة** (‏D-523): معرّفٌ لا يُقرأ ⇒ يُؤخذ من الخطّة لا يُعَدّ مجهولاً
    base = (lambda iid: (None, None), fake_forms, fake_norm, None)
    PR = {"hafs_minshawi_015076": ("hafs", ["الحمد", "لله"])}
    rf, fo, no, ac = judges_with_plan(PR, base)
    b = bag_stats({"hafs_minshawi_015076": {"text": "الحمد لله"}}, rf, fo, no, ac)
    ok((b["ref"], b["hit"], b["unknown"]) == (2, 2, []),
       f"⛔ مرجعُ الخطّة يُقرأ للقصير فلا يُعَدّ مجهولاً — جاء {b}")
    b = bag_stats({"لا_في_الخطّة": {"text": "شيء"}}, rf, fo, no, ac)
    ok(b["unknown"] == ["لا_في_الخطّة"], f"⛔ وما ليس في الخطّة يبقى مجهولاً مُعلَناً — جاء {b}")
    # ⛔ وأولويّةُ المصحف على الخطّة (المصحفُ أصلٌ والخطّةُ نقل)
    rf2, _, _, _ = judges_with_plan({"i9": ("hafs", ["منقولٌ"])},
                                    (lambda iid: ("hafs", ["أصلٌ"]), fake_forms, fake_norm, None))
    ok(rf2("i9") == ("hafs", ["أصلٌ"]), "⛔ ما قرأه المصحفُ لا تنسخه الخطّة")

    # ⑥ **سلَّمُ الإزاحات للتقطيع** (‏D-530) — يُقاس في الصندوق بلا `whisper-cli`.
    ok(chunk_spans(30.0, 10) == [(0, 10000), (10000, 10000), (20000, 10000)],
       f"ثلاثونَ ثانيةً بقِطَعِ 10 ⇒ ثلاثةٌ متساوية — جاء {chunk_spans(30.0, 10)}")
    sp = chunk_spans(21.6, 10)
    ok(sp == [(0, 10000), (10000, 11600)],
       f"⛔ الذيلُ القصيرُ يُضَمّ لا يُفرَد — جاء {sp}")
    for d, c in ((21.6, 10), (30.0, 10), (5.0, 10), (0.4, 6), (37.0, 6)):
        sp = chunk_spans(d, c)
        tot = int(round(d * 1000))
        ok(sp[0][0] == 0, f"⛔ يبدأ من الصفر: {sp}")
        ok(sum(x[1] for x in sp) == tot, f"⛔ التغطيةُ ناقصةٌ أو زائدةٌ على {d}ث/{c}: {sp}")
        for k in range(1, len(sp)):
            ok(sp[k][0] == sp[k - 1][0] + sp[k - 1][1], f"⛔ فجوةٌ أو تداخلٌ في {sp}")
        ok(all(x[1] > 0 for x in sp), f"⛔ مقطعٌ فارغٌ في {sp}")
    ok(chunk_spans(5.0, 10) == [(0, 5000)], "أقصرُ من المقطع ⇒ نداءٌ واحدٌ كما هو")
    # ⛔ وذراعا التقطيع **رايات المشحون حرفاً** — فالفرقُ المقيسُ هو التقطيعُ وحدَه
    for _n in ARM_CHUNK:
        ok(_n in ARMS, f"⛔ ذراعُ تقطيعٍ بلا رايات: {_n}")
        ok(ARMS[_n] == ARMS["greedy"], f"⛔ {_n} يجب أن تكون رايات المشحون حرفاً")
        ok(_n in ARM_LABEL, f"⛔ ذراعُ تقطيعٍ بلا عنوان: {_n}")
        ok(ARM_CHUNK[_n] > 0, f"⛔ طولُ مقطعٍ غيرُ موجب: {_n}")

    # ⑦ **محلِّلُ الطابع ومرآةُ حارس الذيل** (‏D-532) — تُقاس في الصندوق بلا أداة.
    ok(seg_start_ms("[00:00:01.500 --> 00:00:03.000]   نص") == 1500,
       f"طابعٌ بسيطٌ — جاء {seg_start_ms('[00:00:01.500 --> 00:00:03.000]   نص')}")
    ok(seg_start_ms("[00:01:02.250 --> 00:01:03.000]  x") == 62250, "دقائقُ وثوانٍ")
    ok(seg_start_ms("[01:00:00.000 --> 01:00:01.000]  x") == 3600000, "ساعةٌ كاملة")
    ok(seg_start_ms("لا طابعَ هنا") is None, "⛔ ما لا طابعَ له يعود None لا صفراً")
    S = [(0, "أ"), (5000, "ب"), (11000, "ج"), (12000, "د")]
    ok(tail_trim(S, 10000) == S[:2],
       f"⛔ ما بدأ بعد 10000+500 يُشذَّب من الذيل — جاء {tail_trim(S, 10000)}")
    ok(tail_trim(S, 12000) == S, "وما دون الحدّ يبقى كلُّه")
    ok(tail_trim([], 10000) == [], "فارغٌ ⇒ فارغٌ بلا انفجار")
    ok(tail_trim(S, 0) == S, "حدٌّ غيرُ موجبٍ ⇒ لا تشذيب")
    # ⛔⛔ **الضابطُ السالبُ الأهمّ**: القاعدةُ **ذيلٌ** لا تصفيةٌ عامّة — متجاوزةٌ يليها
    #     ما هو دون الحدّ **تبقى**، وهو سلوكُ المحرك بعينه.
    M = [(0, "أ"), (20000, "ب"), (3000, "ج")]
    ok(tail_trim(M, 10000) == M,
       f"⛔ تصفيةٌ عامّةٌ بدل تشذيبِ ذيلٍ — جاء {tail_trim(M, 10000)}")
    ok(tail_trim([(None, "أ"), (99000, "ب")], 10000) == [(None, "أ")],
       "والمجهولُ الطابعِ لا يُشذَّب وما بعده يُشذَّب")
    ok(TAIL_SLACK_MS == 500, "سماحُ الحارس 500 كما في المحرك")
    # ⛔⛔ **ودلالةُ الحدّ مطلقةٌ** (مصدرُ whisper: `seek_start = offset_ms/10` · `t0 = seek + …`)
    #     ⇒ مقطعٌ ثانٍ [10000..20000] مقطوعاتُه تبدأ عند 10500 و21000: الأولى **تبقى**
    #     والثانيةُ تُشذَّب. ولو كان الحدُّ `len_ms` وحدَه لشُذّبت الاثنتان ⇒ حارسٌ يكذب نفعاً.
    SEC = [(10500, "أ"), (21000, "ب")]
    ok(tail_trim(SEC, 10000 + 10000) == SEC[:1],
       f"⛔ الحدُّ إزاحةٌ + طولٌ — جاء {tail_trim(SEC, 20000)}")
    ok(tail_trim(SEC, 10000) == [],
       "والحدُّ الخاطئُ (طولٌ وحدَه) يمحو المقطعَ — وهذا ما يحرسه الضابطُ أعلاه")
    for _n in ARM_TAILGUARD:
        ok(_n in ARM_CHUNK and _n in ARMS and _n in ARM_LABEL, f"⛔ ذراعُ حارسٍ ناقصةُ التسجيل: {_n}")
        ok(ARMS[_n] == ARMS["greedy"], f"⛔ {_n} رايات المشحون حرفاً")
    ok(ARM_CHUNK["chunk10g"] == ARM_CHUNK["chunk10"], "⛔ الحارسُ لا يغيّر طولَ المقطع")

    print("🧪 ضوابطُ `cli_time`: %d إخفاقاً" % len(fails))
    for m in fails:
        print("  ⛔", m)
    return 1 if fails else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    sys.exit(main())
