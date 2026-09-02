# -*- coding: utf-8 -*-
"""تفريغ VAD-first (المخطط 4.3): التقطيع عند الصمت ثم تفريغ كل مقطع وحده.

النموذج q8 مُثبت الجودة على المقاطع القصيرة (BENCHMARKS)، وطوابعه الرمزية على
النوافذ الطويلة غير موثوقة — لذا المقطع الصوتي هو وحدة التفريغ، وحدوده من VAD.
المخرج: قائمة مقاطع [{"s","e","words":[نصوص مطبَّعة]}].
"""
import json
import os
import subprocess

from common import MODEL_Q8, WHISPER_CLI, norm

MAX_SEG_MS = 28_000  # حد whisper 30ث
MIN_SEG_MS = 400


def speech_segments(total_ms, sil):
    """مقاطع الكلام بين فترات الصمت؛ يقسم الطويل ويهمل الفتات."""
    segs, t = [], 0
    for s, e in sil:
        if s - t >= MIN_SEG_MS:
            segs.append((t, s))
        t = e
    if total_ms - t >= MIN_SEG_MS:
        segs.append((t, total_ms))
    out = []
    for s, e in segs:
        while e - s > MAX_SEG_MS:
            out.append((s, s + MAX_SEG_MS))
            s += MAX_SEG_MS
        out.append((s, e))
    return out


def transcribe_range(wav, start_ms, dur_ms, tag):
    """يقصّ المدى إلى wav مؤقت (whisper-cli يتجاهل -d عملياً) ثم يفرّغه.
    القصّ للمعالجة المحلية فقط — لا يُخزَّن ولا يُوزَّع (D-024)."""
    from common import FFMPEG
    out_base = wav + f".{tag}"
    clip = out_base + ".clip.wav"
    # مهلات صارمة + إعادة واحدة: علّقت الدفعة الأولى على ابن ميت بلا مهلة (درس 08-31)
    for attempt in (1, 2):
        try:
            subprocess.run([FFMPEG, "-y", "-v", "error", "-i", wav,
                            "-ss", f"{start_ms/1000:.3f}", "-t", f"{dur_ms/1000:.3f}",
                            "-ar", "16000", "-ac", "1", clip],
                           check=True, timeout=60, stdin=subprocess.DEVNULL)
            subprocess.run(
                [WHISPER_CLI, "-m", MODEL_Q8, "-f", clip, "-l", "ar",
                 "-oj", "-of", out_base, "--no-prints",
                 "-bo", "1", "-bs", "1", "-nf", "-ac", "512"],  # تسريع مقيس 1.92× بجودة مطابقة (نطابق نصاً معروفاً)
                capture_output=True, check=True, timeout=240, stdin=subprocess.DEVNULL,
            )
            # مخرج فارغ/معطوب = فشل يعاد (رصد 09-01: JSON فارغ من whisper ميت)
            with open(out_base + ".json", encoding="utf-8", errors="replace") as _f:
                json.load(_f)
            break
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError,
                json.JSONDecodeError, FileNotFoundError):
            if attempt == 2:
                raise
    if os.path.exists(clip):
        os.remove(clip)
    with open(out_base + ".json", encoding="utf-8", errors="replace") as f:
        data = json.load(f)
    os.remove(out_base + ".json")
    text = " ".join(seg["text"] for seg in data.get("transcription", []))
    return norm(text).split()


def transcribe(wav, total_ms, sil, log=print):
    segs = speech_segments(total_ms, sil)
    out = []
    for i, (s, e) in enumerate(segs):
        words = transcribe_range(wav, s, e - s, f"seg{i}")
        out.append({"s": s, "e": e, "words": words})
        log(f"  مقطع {i+1}/{len(segs)} [{s/1000:.1f}-{e/1000:.1f}ث]: {' '.join(words)}")
        if (i + 1) % 20 == 0:
            print(f"    …تقدم: {i+1}/{len(segs)} مقطعاً", flush=True)
    return out
