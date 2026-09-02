# -*- coding: utf-8 -*-
"""تفريغ مقاطع VAD بمرونة تحت ضغط الذاكرة (نسخة v2 — لا تلمس الإنتاجي).

نفس منهج transcribe.py (VAD-first) + ثلاث إضافات فرضها واقع الجهاز الليلة:
  1. **تسلسل صارم** لعمليات whisper (أمر المشرفة: عملية واحدة في أي لحظة).
  2. تراجع أُسّي وإعادة محاولة عند انهيار whisper بضغط الذاكرة (3221225477/10).
  3. كاش لكل مقطع ⇒ الانهيار لا يُفقد ما سبق.
"""
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "alignment"))
from common import FFMPEG, MODEL_Q8, WHISPER_CLI, norm  # noqa: E402
from transcribe import speech_segments  # noqa: E402

from gt import W2  # noqa: E402


def _run_whisper(clip, base, extra=()):
    for attempt in range(5):
        r = subprocess.run([WHISPER_CLI, "-m", MODEL_Q8, "-f", clip, "-l", "ar", "-oj",
                            "-of", base, "--no-prints", *extra],
                           capture_output=True, text=True, timeout=600, stdin=subprocess.DEVNULL)
        if r.returncode == 0 and os.path.exists(base + ".json"):
            return
        time.sleep(20 * (attempt + 1))  # ضغط ذاكرة: انتظر وأعد (لا تُوازِ أبداً)
    raise RuntimeError(f"whisper فشل خمس مرات على {clip}: {r.returncode} {r.stderr[-300:]}")


def transcribe_range(wav, start_ms, dur_ms, tag, cache_dir, extra=()):
    cache = os.path.join(cache_dir, tag + ".json")
    if os.path.exists(cache):
        with open(cache, encoding="utf-8") as f:
            return json.load(f)
    base = os.path.join(cache_dir, tag)
    clip = base + ".clip.wav"
    subprocess.run([FFMPEG, "-y", "-v", "error", "-i", wav, "-ss", f"{start_ms/1000:.3f}",
                    "-t", f"{dur_ms/1000:.3f}", "-ar", "16000", "-ac", "1", clip],
                   check=True, timeout=120, stdin=subprocess.DEVNULL)
    try:
        _run_whisper(clip, base + ".raw", extra)
        with open(base + ".raw.json", encoding="utf-8") as f:
            data = json.load(f)
    finally:
        for p in (clip, base + ".raw.json"):
            if os.path.exists(p):
                os.remove(p)
    words = norm(" ".join(s["text"] for s in data.get("transcription", []))).split()
    with open(cache, "w", encoding="utf-8") as f:
        json.dump(words, f, ensure_ascii=False)
    return words


def transcribe(wav, total_ms, sil, tag_prefix, log=print):
    cache_dir = os.path.join(W2, "segs", tag_prefix)
    os.makedirs(cache_dir, exist_ok=True)
    segs = speech_segments(total_ms, sil)
    out = []
    for i, (s, e) in enumerate(segs):
        words = transcribe_range(wav, s, e - s, f"seg{i:04d}", cache_dir)
        out.append({"s": s, "e": e, "words": words})
        if (i + 1) % 20 == 0:
            log(f"    تقدم التفريغ: {i+1}/{len(segs)}")
    return out
