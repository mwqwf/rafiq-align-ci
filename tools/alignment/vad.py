# -*- coding: utf-8 -*-
"""VAD طاقي بسيط على wav 16k mono — يكفي لإسقاط حدود الآي على الصمت (المخطط 4.3 خطوة 3).

لا يحتاج إلا numpy + stdlib. المخرج: قائمة فترات صمت [startMs, endMs].
"""
import wave

import numpy as np

FRAME_MS = 20

# يدخل مفتاح كاش CI وترويسة الفهرس: تقطيعٌ مختلف = فهرسٌ مختلف ولو تطابق كل
# ما عداه، فلا يُقارَن فهرسان بُنيا بنسختين مختلفتين من العتبة.
VAD_VERSION = "adaptive-2"

# العتبة المستعملة فعلاً في آخر نداء — تُكتب في الترويسة كي لا يُقال «متكيّفة»
# بلا رقم. ⚠️ وهي **لكل سورة** لا لكل قارئ (المقياس يتغيّر ×34 بين السور)،
# فالمكتوب في الترويسة وسيطُها لا قيمةٌ واحدة حاكمة.
LAST_REL = None


def read_wav(path):
    with wave.open(path, "rb") as w:
        assert w.getframerate() == 16000 and w.getnchannels() == 1, "wav يجب أن يكون 16k mono"
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return data.astype(np.float32) / 32768.0


def _silences_at(rms, rel_threshold, speech_level, min_silence_ms):
    quiet = rms < max(rel_threshold * speech_level, 1e-4)
    out, start = [], None
    for i, q in enumerate(quiet):
        if q and start is None:
            start = i
        elif not q and start is not None:
            if (i - start) * FRAME_MS >= min_silence_ms:
                out.append((start * FRAME_MS, i * FRAME_MS))
            start = None
    if start is not None and (len(quiet) - start) * FRAME_MS >= min_silence_ms:
        out.append((start * FRAME_MS, len(quiet) * FRAME_MS))
    return out


# ⛔ درسٌ مقيس مرتين 2026-09-02:
# ① العتبة الثابتة 0.04 تعجز عن التلاوة **قليلة السكتات**: `a_majed` ‏0.16
#   سكتة/دقيقة مقابل 5.6 عند الحصري، فيقطع المحرك عند سقف 28ث اعتباطاً،
#   فتغلب MED (‏89%) وتُبتلع الآي القصار.
# ② ورفعُ العتبة على من **لا** يحتاجها سمٌّ (قياس github-8e على الحصري/النبأ):
#   ‏HIGH ‏88% ⇐ 40%، و**47.5% من الحدود تزيح** بعضها 7.5ث.
#
# فالشرط **وظيفيّ لا إحصائي**: لا تُرفع العتبة إلا إذا أخفقت الافتراضية في
# إيجاد مواضع قطعٍ أصلاً، وتُرفع **بالتدريج** وتقف عند الكفاية. والمقياس
# الإحصائي الأول (أرضية/مستوى) سقط لأنه ينقلب ×34 بين سور القارئ الواحد،
# فكانت سورةٌ من قارئٍ نظيف قد تعبره فتُفسد. أمّا كثافة السكتات فتقيس ما
# نريده مباشرةً، والفصل فيها ×35 فلا تقع سورةٌ سليمة قرب الحدّ.
MIN_DENS = 1.5      # دون هذا: لم يجد مواضع قطع ⇒ يُرفع
GOOD_DENS = 3.0     # عند هذا: كفى ⇒ يُوقف الرفع
LADDER = (0.10, 0.15, 0.25)

LAST_REL = None


def silences(wav_path, min_silence_ms=180, rel_threshold=0.04, adaptive=True):
    """فترات صمت: طاقة الإطار دون عتبة نسبية من وسيط طاقة الكلام، بطول أدنى.

    `adaptive=False` يعيد السلوك المنشور بحرفه (عتبةٌ ثابتة بلا سُلّم).
    """
    global LAST_REL
    x = read_wav(wav_path)
    n = 16000 * FRAME_MS // 1000
    frames = x[: len(x) // n * n].reshape(-1, n)
    rms = np.sqrt((frames**2).mean(axis=1))
    speech_level = np.percentile(rms[rms > 1e-4], 70) if (rms > 1e-4).any() else 0.01
    minutes = max(len(rms) * FRAME_MS / 60000.0, 1e-6)

    out = _silences_at(rms, rel_threshold, speech_level, min_silence_ms)
    LAST_REL = float(rel_threshold)
    if not adaptive or len(out) / minutes >= MIN_DENS:
        return out                      # الافتراضية كافية ⇒ لا تُمَس
    for rel in LADDER:
        if rel <= rel_threshold:
            continue
        cand = _silences_at(rms, rel, speech_level, min_silence_ms)
        out, LAST_REL = cand, float(rel)
        if len(cand) / minutes >= GOOD_DENS:
            break                       # كفى ⇒ لا تُرفع أكثر (الزيادة تضرّ)
    return out


def snap_to_silence(t_ms, sil, tolerance_ms=700):
    """أقرب مركز صمت ضمن نافذة التسامح، وإلا t نفسها. يعيد (زمن، هل انطبق على صمت)."""
    best, best_d = None, tolerance_ms + 1
    for s, e in sil:
        c = (s + e) // 2
        if s - tolerance_ms <= t_ms <= e + tolerance_ms:
            d = 0 if s <= t_ms <= e else min(abs(t_ms - s), abs(t_ms - e))
            if d < best_d:
                best, best_d = c if not (s <= t_ms <= e) else max(s + 40, min(t_ms, e - 40)), d
    return (best, True) if best is not None else (t_ms, False)
