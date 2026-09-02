# -*- coding: utf-8 -*-
"""VAD طاقي بسيط على wav 16k mono — يكفي لإسقاط حدود الآي على الصمت (المخطط 4.3 خطوة 3).

لا يحتاج إلا numpy + stdlib. المخرج: قائمة فترات صمت [startMs, endMs].
"""
import wave

import numpy as np

FRAME_MS = 20


def read_wav(path):
    with wave.open(path, "rb") as w:
        assert w.getframerate() == 16000 and w.getnchannels() == 1, "wav يجب أن يكون 16k mono"
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return data.astype(np.float32) / 32768.0


def silences(wav_path, min_silence_ms=180, rel_threshold=0.04):
    """فترات صمت: طاقة الإطار دون عتبة نسبية من وسيط طاقة الكلام، بطول أدنى."""
    x = read_wav(wav_path)
    n = 16000 * FRAME_MS // 1000
    frames = x[: len(x) // n * n].reshape(-1, n)
    rms = np.sqrt((frames**2).mean(axis=1))
    speech_level = np.percentile(rms[rms > 1e-4], 70) if (rms > 1e-4).any() else 0.01
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
