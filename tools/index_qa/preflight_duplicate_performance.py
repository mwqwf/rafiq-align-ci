#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""كشف تكرار الأداء في ملف سورة قبل المحاذاة — تقريري لا يقصّ ولا يرقّي.

    python tools/index_qa/preflight_duplicate_performance.py \
        --url URL --surah 14 --expected-sec 1393 --timing-start-ms 2548840 --file-sec 3942.8

    # أو بقياس فعلي على الصوت (ffprobe / ffmpeg 400 هرتز):
    python tools/index_qa/preflight_duplicate_performance.py \
        --url URL --surah 4 --expected-sec 4785.6 --ffprobe --envelope

طرق الكشف (من الأرخص إلى الأثقل):

1) نسبة مدّة الملف إلى مدى التوقيت الرسمي أو إلى مرجع معلَن (`--expected-sec`).
   ≥2.5 ⇒ repeated_performance؛ 1.6–2.5 ⇒ suspect؛ أقل ⇒ ok من هذه الطريق.
2) إن وُجد `--timing-start-ms` وكانت الآية 1 بعد 40٪ من الملف ⇒ leading_extra_material
   (نمط الدوسري: التوقيت على الأداء الأخير).
3) اختياري: غلاف طاقة عبر ffmpeg ببثّ 400 هرتز (`--envelope`) — ملف واحد، nice خارجاً.
   يبحث عن إزاحة ذات ارتباط مرتفع تشير إلى إعادة أداء. لا يُشغَّل افتراضياً.

لا يكتب في الدلو. القصّ المقترح يُعرض في الحقل `suggested_trim` ليمرّ بالسماع لاحقاً.
"""
from __future__ import annotations

import argparse
import array
import json
import math
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

STRONG = 2.5
WARN = 1.6
START_FRAC = 0.40
ENVELOPE_SR = 400


def classify_ratio(file_sec: float, expected_sec: float | None) -> dict:
    if not file_sec or not expected_sec or expected_sec <= 0:
        return {"verdict": "unknown", "ratio": None}
    ratio = file_sec / expected_sec
    if ratio >= STRONG:
        v = "repeated_performance"
    elif ratio >= WARN:
        v = "suspect_repeat_or_very_slow"
    else:
        v = "ok_by_duration"
    return {"verdict": v, "ratio": round(ratio, 3)}


def classify_start(file_sec: float, timing_start_ms: int | None) -> dict:
    if not file_sec or timing_start_ms is None:
        return {}
    frac = (timing_start_ms / 1000) / file_sec
    out = {"start_frac": round(frac, 3), "timing_start_ms": timing_start_ms}
    if frac >= START_FRAC:
        out["leading_extra_material"] = True
        # القصّ المقترح: من بدء التوقيت إلى نهاية الملف (الأداء المؤقَّت رسمياً)
        out["suggested_trim"] = {
            "start_ms": int(timing_start_ms),
            "end_ms": int(round(file_sec * 1000)),
            "reason": "آية 1 في التوقيت الرسمي بعد بداية الملف — أداء سابق غير مؤقَّت",
        }
    return out


def envelope_peaks(energy: list[float], min_lag_s: int = 120, corr_min: float = 0.75) -> dict:
    """ارتباط ذاتي بسيط على غلاف طاقة ثانية-بثانية. energy[i] ≥ 0."""
    if len(energy) < min_lag_s * 2:
        return {"error": "envelope_too_short"}
    mean = sum(energy) / len(energy)
    var = sum((x - mean) ** 2 for x in energy) / len(energy)
    if var <= 1e-12:
        return {"error": "flat_envelope"}
    best = {"lag_s": None, "corr": 0.0}
    max_lag = min(len(energy) - min_lag_s, len(energy) // 2)
    for lag in range(min_lag_s, max_lag + 1):
        n = len(energy) - lag
        num = sum((energy[i] - mean) * (energy[i + lag] - mean) for i in range(n))
        corr = num / (n * var)
        if corr > best["corr"]:
            best = {"lag_s": lag, "corr": round(float(corr), 3)}
    best["repeated_like"] = bool(best["lag_s"] and best["corr"] >= corr_min)
    return best


def synthesize_repeated_envelope(perf_s: int = 200, reps: int = 3, hop: int = 1) -> list[float]:
    """غلاف اصطناعي غير دوري داخل الأداء، يتكرر reps مرات — لاختبار الوحدة."""
    pat = []
    for i in range(perf_s):
        x = i / max(1, perf_s - 1)
        v = 0.15 + 0.7 * x * x
        if 30 <= i < 38:
            v = 1.6
        if 90 <= i < 94:
            v = 1.2
        if i > perf_s - 25:
            v = 0.04
        pat.append(v)
    out: list[float] = []
    for _ in range(reps):
        out.extend(pat)
    return out


def probe_duration_sec(url: str, timeout: int = 60) -> float:
    """قراءة مدّة الصوت الفعلية بـffprobe دون الاعتماد على ترويسة CBR أو التخمين."""
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", url,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=True)
    return float(r.stdout.strip())


def extract_rms_envelope(url: str, sr: int = ENVELOPE_SR, timeout: int = 180) -> list[float]:
    """بثّ PCM أحادي 400 هرتز عبر ffmpeg وحساب طاقة RMS لكل ثانية."""
    cmd = [
        "ffmpeg", "-v", "error", "-i", url,
        "-ac", "1", "-ar", str(sr), "-f", "s16le", "-",
    ]
    r = subprocess.run(cmd, capture_output=True, timeout=timeout, check=True)
    samples = array.array("h")
    samples.frombytes(r.stdout[: len(r.stdout) - (len(r.stdout) % 2)])
    out: list[float] = []
    for off in range(0, len(samples) - sr + 1, sr):
        chunk = samples[off : off + sr]
        out.append(math.sqrt(sum(x * x for x in chunk) / sr) / 32768.0)
    return out


def report(file_sec, expected_sec=None, timing_start_ms=None, envelope=None) -> dict:
    out = {"file_sec": file_sec, "expected_sec": expected_sec}
    out.update(classify_ratio(file_sec or 0, expected_sec))
    out.update(classify_start(file_sec or 0, timing_start_ms))
    if envelope is not None:
        out["envelope"] = envelope_peaks(list(envelope))
        if out["envelope"].get("repeated_like") and out["verdict"] == "ok_by_duration":
            out["verdict"] = "repeated_performance"
            lag = out["envelope"]["lag_s"]
            out["suggested_trim"] = {
                "start_ms": 0,
                "end_ms": int(lag * 1000),
                "reason": f"غلاف الطاقة يتكرر بإزاحة {lag}ث — يُقترَح الأداء الأول",
            }
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="", help="رابط الصوت أو مساره (يُستخدم مع --ffprobe أو --envelope)")
    ap.add_argument("--file-sec", type=float, default=None)
    ap.add_argument("--ffprobe", action="store_true", help="قياس المدّة الفعلية بـffprobe من --url")
    ap.add_argument("--envelope", action="store_true", help="بناء غلاف الطاقة 400 هرتز عبر ffmpeg من --url")
    ap.add_argument("--expected-sec", type=float, default=None)
    ap.add_argument("--timing-start-ms", type=int, default=None)
    ap.add_argument("--surah", type=int, default=None)
    ap.add_argument("--reciter", default="")
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)
    file_sec = args.file_sec
    if args.ffprobe:
        if not args.url:
            ap.error("--ffprobe يتطلّب --url")
        file_sec = probe_duration_sec(args.url)
    env = None
    if args.envelope:
        if not args.url:
            ap.error("--envelope يتطلّب --url")
        env = extract_rms_envelope(args.url)
        if file_sec is None:
            file_sec = float(len(env))
    if file_sec is None:
        ap.error("--file-sec أو --ffprobe أو --envelope مطلوب")
    rec = report(file_sec, args.expected_sec, args.timing_start_ms, envelope=env)
    if env is not None:
        rec["envelope_seconds"] = len(env)
    rec["reciter"] = args.reciter
    rec["surah"] = args.surah
    rec["url"] = args.url
    print(json.dumps(rec, ensure_ascii=False, indent=2))
    if args.out:
        Path(args.out).write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
