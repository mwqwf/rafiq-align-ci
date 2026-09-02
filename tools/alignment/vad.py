# -*- coding: utf-8 -*-
"""VAD طاقي بسيط على wav 16k mono — يكفي لإسقاط حدود الآي على الصمت (المخطط 4.3 خطوة 3).

لا يحتاج إلا numpy + stdlib. المخرج: قائمة فترات صمت [startMs, endMs].
"""
import wave

import numpy as np

FRAME_MS = 20

# يدخل مفتاح كاش CI وترويسة الفهرس: تقطيعٌ مختلف = فهرسٌ مختلف ولو تطابق كل
# ما عداه، فلا يُقارَن فهرسان بُنيا بنسختين مختلفتين من العتبة.
VAD_VERSION = "adaptive-1"


def read_wav(path):
    with wave.open(path, "rb") as w:
        assert w.getframerate() == 16000 and w.getnchannels() == 1, "wav يجب أن يكون 16k mono"
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return data.astype(np.float32) / 32768.0


def silences(wav_path, min_silence_ms=180, rel_threshold=0.04, adaptive=True):
    """فترات صمت: طاقة الإطار دون عتبة نسبية من وسيط طاقة الكلام، بطول أدنى.

    ⛔ درس 2026-09-02 (قياس github-8e): العتبة الثابتة 0.04 تفترض تسجيلاً نظيفاً.
    وأرضية ضجيج `a_majed` **20.4% من مستوى كلامه** (مقابل 1.7% عند الحصري)، أي
    **أعلى من العتبة نفسها** ⇒ لا يرى المحرك سكتةً واحدة (4 سكتات في 762ث مقابل
    221 في 1427ث) ⇒ يقطع عند سقف 28ث اعتباطاً ⇒ MED غالب والآي القصار تُبتلع.
    وكنّا نظنّه «قارئاً موصول الأنفاس» — والعلّة في مقياسنا لا في تلاوته.

    فالعتبة تتكيّف مع أرضية التسجيل: `max(0.04, 1.4 × أرضية/مستوى)`. تعطي ~0.29
    لـ`a_majed`، و**0.04 بلا تغيير** للتسجيلات النظيفة — فالسلوك المنشور محفوظ
    حرفياً لمن لا يحتاج التكيّف. قياس مضبوط على يس (الفرق العتبة وحدها):
    HIGH ‏9 ⇐ **78** من 83، وMED ‏74 ⇐ 5.
    """
    x = read_wav(wav_path)
    n = 16000 * FRAME_MS // 1000
    frames = x[: len(x) // n * n].reshape(-1, n)
    rms = np.sqrt((frames**2).mean(axis=1))
    speech_level = np.percentile(rms[rms > 1e-4], 70) if (rms > 1e-4).any() else 0.01
    if adaptive:
        floor = float(np.percentile(rms, 5)) if len(rms) else 0.0
        # 1.4× : تعلو الأرضية قليلاً لا كثيراً ⇒ 0.29 لـa_majed و0.024 للحصري
        #        (فتُقصَر إلى 0.04 = بلا تغيير).
        # سقف 0.35 : يمنع الانفلات — تسجيلٌ أرضيته 60% من كلامه ستجعل الصيغة
        #        **تعدّ الكلام صمتاً**. وفوق السقف العلّة في التسجيل لا في المعامل.
        # adaptive=False : يعيد السلوك المنشور بحرفه لمن أراد.
        rel_threshold = min(0.35, max(rel_threshold,
                                      1.4 * floor / max(float(speech_level), 1e-9)))
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
