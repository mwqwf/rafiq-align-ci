# -*- coding: utf-8 -*-
"""مولّد التوقيتات الكلمية الحقيقية (بديل القسمة التقديرية في word_split).

**الوصفة** (مقيسة في `../REPORT.md` §٧): whisper بـ`-ml 1 -sow -oj -ojf -nfa -dtw tiny`
والزمن من **`t_dtw`** لا `offsets`. ثم محاذاة NW بين كلمات النافذة وكلمات الآية بنص
الرواية نفسها، فتُسند لكل كلمة مرجعية زمنها الحقيقي.

**ثلاثة حُرّاس** (كلها مبادئ من ليلة الصقل، لا عتبات مضبوطة على هذه المهمة):
1. **التشبّع الطرفي:** تُسقط كل كلمة يقع طابعها في آخر `SAT_MS` من النافذة.
2. **`acc >= MIN_ACC` للآية كلها** وإلا **لا تُكتب `words[]` أصلاً** — «التخمين لا
   يُكتب فوق قياس»: آية بلا توقيت كلمي أصدق من آية بتوقيت مخترع.
3. **الاستقراء محدود:** الكلمة غير المطابقة تأخذ زمناً مستقرأً بين جارتيها بوزن
   الحروف، وتُوسم بثقة أدنى صراحةً (`interpolated`)؛ وإن تجاوز المستقرأ
   `MAX_INTERP_RATIO` من كلمات الآية سقطت الآية كلها.

⛔ القصاصات محلية مؤقتة تُحذف فور القياس (D-024: نفهرس الصوت ولا نملكه).
"""
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_V2 = os.path.dirname(_HERE)
sys.path.insert(0, _V2)
sys.path.insert(0, os.path.join(os.path.dirname(_V2), "alignment"))

from align import nw_align  # noqa: E402
from common import norm  # noqa: E402

import refine  # noqa: E402  (نعيد استعمال clip_words بوصفة DTW نفسها)

MIN_ACC = 0.75           # عتبة قبول الآية (نفس مبدأ حارس الترقية)
# ⛔ العتبة النسبية أداة قياس خاطئة للمقام الصغير: على آية من كلمتين لا تمرّ إلا
# بتفريغ كامل الدقة (‏0 خطأ)، وعلى آية من عشرين تتسامح في خمسة. والآيات القصار
# أكثر ما يُظلَّل ويُحفظ — فالعتبة تحرم أنفع المواضع. البديل **مبدئي لا تخفيفي**:
# نقبل حين يكون البرهان **مباشراً وكاملاً** — كل كلمة أُسندت إلى مقطعها بالترتيب
# (استقراء = صفر) — وهو أقوى من نسبة 0.8 على آية فيها أربع كلمات مستقرأة بلا إسناد.
FULL_EVIDENCE_MIN_EXACT = 0.5   # ومع ذلك: نصف الكلمات على الأقل مطابق حرفياً
MAX_INTERP_RATIO = 0.34  # فوقها الآية مستقرأة أكثر مما هي مقيسة ⇒ تُرفض
MIN_WORD_MS = 60         # أدنى مدة كلمة معقولة
# ⛔ حد whisper الصلب 30ث. الآيات الطوال تتجاوزه: **845 آية من 4018 (21%) أطول من
# 30ث** وأطولها 2:282 بـ236ث — وجزء عمّ لم يكن فيه منها شيء تقريباً فلم يظهر العطب
# إلا على البقرة، حيث انهار whisper على 2:29 (‏30ث بالضبط) بكود 3221226505.
# العلاج: تقطيع النافذة الطويلة إلى مقاطع ≤ CHUNK_MS بتراكب، ثم ضمّ الكلمات.
CHUNK_MS = 24_000
CHUNK_OVERLAP_MS = 2_000
DEDUPE_MS = 400          # كلمتان متطابقتان خلاله = تكرار تراكب لا نطقان

# ⛔ اكتشاف مقيس (اختبار الدورة الكاملة): طوابع `t_dtw` تؤشّر **نهاية** الكلمة لا
# بدايتها. البرهان سمعي وقاطع: مقطع «مثقال» بأزمنة `t_dtw` الخام يُسمع «قال ذر» —
# أي أنه يبدأ داخل الكلمة ويمتد إلى التالية؛ و«الصمد» يُسمع «مد»، و«أحد» يُسمع «عد».
# والقياس ضد QUL يوافق: انحياز تأخير ثابت ‎+560م.ث، منه ~160 صمت ابتدائي والباقي
# هذا العرَض نفسه. فالمعالجة الصحيحة **بنيوية لا ثابت مضبوط**: حدود الكلمات هي
# علامات `t_dtw` نفسها، فتصير الكلمة j هي المدى [نهاية j-1، نهاية j].
DTW_MARKS_WORD_END = True

_LONG = re.compile("[اويآٱ]")


def _weight(w_raw):
    """وزن زمني تقريبي للاستقراء وحده (منقول عن word_split الإنتاجي)."""
    bare = norm(w_raw).replace(" ", "")
    return max(len(bare) + 0.7 * len(_LONG.findall(bare)) + 0.5 * w_raw.count("ّ"), 1.0)


def ayah_word_times(wav, start_ms, end_ms, ayah_text, tag, cache_dir=None, log=None,
                    onset_ms=None, dtw_marks_end=DTW_MARKS_WORD_END):
    """يعيد (words, meta) أو (None, meta) إن سقطت الآية بأحد الحُرّاس.

    words: [{"subIndex", "startMs", "endMs", "conf", "interpolated"}] بأزمنة **مطلقة**.
    """
    raw_words = ayah_text.split()
    ref = [norm(w) for w in raw_words]
    meta = {"n": len(ref), "matched": 0, "interp": 0, "acc": 0.0, "reason": ""}
    if not ref:
        meta["reason"] = "no-ref"
        return None, meta

    cd = cache_dir or os.path.join(_HERE, "work", "clips")
    # ⛔ مفتاح الكاش يجب أن يحمل **النافذة** لا اسم الآية وحده: الفهرس قد يُعاد
    #    توليده فتتغير حدود الآية بينما يبقى اسمها — فيعيد الكاش تفريغ نافذة قديمة
    #    بصمت. (اكتُشف حين تبيّن أن 435 من 456 آية انزاحت حدودها بعد دمج الصقل.)
    tag = "%s_%d_%d" % (tag, start_ms, end_ms)
    if end_ms - start_ms <= CHUNK_MS:
        hyp = refine.clip_words(wav, start_ms, end_ms, tag, cache_dir=cd)
    else:
        hyp, t0, i = [], start_ms, 0
        while t0 < end_ms:
            t1 = min(end_ms, t0 + CHUNK_MS)
            hyp += refine.clip_words(wav, t0, t1, "%s_c%d" % (tag, i), cache_dir=cd)
            if t1 >= end_ms:
                break
            t0 = t1 - CHUNK_OVERLAP_MS
            i += 1
        hyp.sort(key=lambda h: h["s"])
        dedup = []                       # أسقط تكرار منطقة التراكب
        for h in hyp:
            if dedup and h["w"] == dedup[-1]["w"] and h["s"] - dedup[-1]["s"] < DEDUPE_MS:
                continue
            dedup.append(h)
        hyp = dedup
    if len(hyp) < 1:
        meta["reason"] = "no-words"
        return None, meta

    pairs = nw_align([h["w"] for h in hyp], ref)
    slots = {}
    exact = 0
    for hi, rj in pairs:
        if hyp[hi]["w"] == ref[rj]:
            exact += 1
        s, e = hyp[hi]["s"], hyp[hi]["e"]
        if rj in slots:
            slots[rj] = (min(slots[rj][0], s), max(slots[rj][1], e))
        else:
            slots[rj] = (s, e)
    meta["matched"] = len(slots)
    meta["acc"] = round(exact / max(len(pairs), 1), 3)
    meta["exact"] = exact
    full_evidence = (len(slots) == len(ref)
                     and exact >= FULL_EVIDENCE_MIN_EXACT * len(ref))
    meta["fullEvidence"] = bool(full_evidence)
    if meta["acc"] < MIN_ACC and not full_evidence:
        meta["reason"] = "low-acc"
        return None, meta

    missing = [j for j in range(len(ref)) if j not in slots]
    meta["interp"] = len(missing)
    # علامات الوقف المستقلة (ۖ ۗ …) رموز خام لا نطق لها، فتطبيعها يعطي نصاً فارغاً
    # ولن يطابقها المفرِّغ أبداً. تأخذ مقطعاً زمنياً (كما في QUL) لكنها **لا تُحتسب
    # في نسبة الاستقراء** وإلا أسقطت آيات حفص السليمة بلا ذنب.
    speech = [j for j in range(len(ref)) if ref[j]]
    interp_speech = [j for j in missing if ref[j]]
    meta["interpSpeech"] = len(interp_speech)
    if len(interp_speech) > MAX_INTERP_RATIO * max(len(speech), 1):
        meta["reason"] = "too-interpolated"
        return None, meta

    # استقراء الفجوات بوزن الحروف بين أقرب مسندين
    for j in missing:
        lo_j = max([k for k in slots if k < j], default=None)
        hi_j = min([k for k in slots if k > j], default=None)
        a = slots[lo_j][1] if lo_j is not None else start_ms
        b = slots[hi_j][0] if hi_j is not None else end_ms
        gap_idx = [k for k in range(
            (lo_j + 1) if lo_j is not None else 0,
            hi_j if hi_j is not None else len(ref)) if k not in slots]
        tot_w = sum(_weight(raw_words[k]) for k in gap_idx) or 1.0
        off = a
        for k in gap_idx:
            d = (b - a) * _weight(raw_words[k]) / tot_w
            slots[k] = (off, off + d)
            off += d

    if dtw_marks_end:
        # علامة `t_dtw` = نهاية الكلمة ⇒ الكلمة j هي [نهاية j-1، نهاية j]،
        # وبداية الأولى من أول كلام حقيقي (VAD) لا من طابع النموذج.
        ends = [slots[j][1] for j in range(len(ref))]
        first = onset_ms if onset_ms is not None else max(start_ms, slots[0][0])
        shifted = {}
        for j in range(len(ref)):
            shifted[j] = (first if j == 0 else ends[j - 1], ends[j])
        slots = shifted

    # بناء الحدود ثم **تطبيع صارم**: نقاط قطع رتيبة داخل [start_ms, end_ms].
    # ⛔ الدرس: فرض MIN_WORD_MS كان يدفع نهاية الكلمة خارج مدى الآية، ثم يلصق
    #    التالية على تلك النهاية، فتخرج الأخيرة **مقلوبة** (نهاية < بداية).
    #    اصطاده حارس النشر في 19 آية. العلاج بنيوي: نبني n+1 نقطة قطع ونفرضها
    #    غير متناقصة ومحصورة، فيستحيل الانقلاب والتداخل رياضياً لا احتياطاً.
    # ⚠️ نقطة البدء = بدء الكلام المقيس (VAD) لا حدّ الآية — عليها قِيس وسيط
    #    180م.ث، وإرجاعها إلى حدّ الآية يُدخل الصمت الابتدائي في الكلمة الأولى.
    cuts = [max(start_ms, min(int(slots[0][0]), end_ms))]
    for j in range(1, len(ref)):
        cuts.append(int(slots[j][0]))
    cuts.append(end_ms)
    for j in range(1, len(cuts)):                      # رتابة أمامية + حصر
        cuts[j] = max(cuts[j - 1], min(int(cuts[j]), end_ms))
    words = [{"subIndex": j, "startMs": cuts[j], "endMs": cuts[j + 1],
              "interpolated": j in missing} for j in range(len(ref))]
    meta["zeroLen"] = sum(1 for w in words if w["endMs"] <= w["startMs"])
    if log:
        log(f"  {tag}: {meta['matched']}/{meta['n']} مسندة · استقراء {meta['interp']} · acc={meta['acc']}")
    return words, meta
