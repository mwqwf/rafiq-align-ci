# -*- coding: utf-8 -*-
"""حقيقة أرضية ذاتية: **اختبار الدورة الكاملة** على الصوت الذي نشحن توقيتاته.

لماذا: `segments_husary.jz` مؤقّت على تسجيل حصري **أسرع بـ1.25×** من ملفات
`everyayah/Husary_128kbps` (مقيس: نسبة مدى الكلام ثابتة 1.25–1.31)، فهو مرجع
غير صالح لصوتنا (درس العدة §4). والمعايرة على مرجع خاطئ تزرع الخطأ بدل كشفه.

البديل لا يحتاج مرجعاً خارجياً ولا يفترض تسجيلاً: **نقصّ مدى الكلمة ونفرّغه وحده**.
إن نطق المقطع تلك الكلمة فالتوقيت يحيط بها؛ وإن نطق جارتها فالحد منزاح **باتجاه
معلوم**. وهو يقيس ما يهم المستخدم بالضبط: هل تشغيل الكلمة يُسمع تلك الكلمة؟

python roundtrip.py --surah 99 --surah 112 --sample 40
"""
import argparse
import json
import os
import random
import shutil
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_V2 = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)
sys.path.insert(0, _V2)
sys.path.insert(0, os.path.join(os.path.dirname(_V2), "alignment"))

from common import (FFMPEG, MODEL_Q8, QURAN_ASSETS, WHISPER_CLI,  # noqa: E402
                    ffprobe_duration_ms, load_index, load_text, norm, read_jz,
                    surah_slice, to_wav16k)
from vad import silences  # noqa: E402

from generate import ayah_word_times  # noqa: E402
from gt import SOURCES, download_ayahs  # noqa: E402

WORK = os.path.join(_HERE, "work")
PAD_MS = 60          # هامش ضئيل: لا نريد أن نمنح التوقيت أكثر مما ادّعى


def transcribe_clip(wav, s_ms, e_ms, tag):
    """يفرّغ مدى الكلمة وحده ⇒ نص مطبَّع (⛔ القصاصة تُحذف فوراً — D-024)."""
    os.makedirs(os.path.join(WORK, "rt"), exist_ok=True)
    base = os.path.join(WORK, "rt", tag)
    clip = base + ".wav"
    s = max(0, s_ms - PAD_MS)
    dur = (e_ms + PAD_MS) - s
    subprocess.run([FFMPEG, "-y", "-v", "error", "-i", wav, "-ss", f"{s/1000:.3f}",
                    "-t", f"{dur/1000:.3f}", "-ar", "16000", "-ac", "1", clip],
                   check=True, timeout=120, stdin=subprocess.DEVNULL)
    try:
        r = subprocess.run([WHISPER_CLI, "-m", MODEL_Q8, "-f", clip, "-l", "ar",
                            "-oj", "-of", base, "--no-prints"],
                           capture_output=True, text=True, timeout=600,
                           stdin=subprocess.DEVNULL)
        if r.returncode != 0 or not os.path.exists(base + ".json"):
            return None
        with open(base + ".json", encoding="utf-8") as f:
            data = json.load(f)
        return norm(" ".join(x["text"] for x in data.get("transcription", [])))
    finally:
        for p in (clip, base + ".json"):
            if os.path.exists(p):
                os.remove(p)


def verdict(heard, target, prev_w, next_w):
    """حكم موضوعي على مقطع الكلمة."""
    toks = heard.split() if heard else []
    if not toks:
        return "SILENT"
    if target in toks:
        if len(toks) == 1:
            return "EXACT"
        if prev_w and prev_w in toks:
            return "BLEED_PREV"      # الحد مبكر: التقط ذيل السابقة
        if next_w and next_w in toks:
            return "BLEED_NEXT"      # الحد متأخر/ممتد
        return "CONTAINS"
    if prev_w and prev_w in toks:
        return "WRONG_PREV"          # منزاح إلى السابقة كلياً
    if next_w and next_w in toks:
        return "WRONG_NEXT"
    return "MISMATCH"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--surah", type=int, action="append", required=True)
    ap.add_argument("--sample", type=int, default=40)
    ap.add_argument("--reciter", default="husary_muallim")
    ap.add_argument("--source", choices=["mine", "qul"], default="mine",
                    help="qul = **شاهد ضابط**: يقيس سقف الأداة نفسها على حدود QUL "
                         "الحقيقية؛ نتيجتنا تُقارن بهذا السقف لا بـ100%")
    args = ap.parse_args()
    base, key = SOURCES[args.reciter], args.reciter
    os.makedirs(WORK, exist_ok=True)
    index = load_index()
    text = load_text("hafs")
    qul = read_jz(os.path.join(QURAN_ASSETS, "segments_husary.jz"))
    rng = random.Random(1234)          # ثابت: النتيجة قابلة لإعادة الإنتاج
    cands = []
    for sn in args.surah:
        a, _b, s = surah_slice(index, sn)
        d = download_ayahs(sn, s["ayahs"], base, key, log=lambda *_: None)
        for an in range(1, s["ayahs"] + 1):
            mp3 = os.path.join(d, f"{an:03d}.mp3")
            wav = to_wav16k(mp3)
            dur = ffprobe_duration_ms(mp3)
            raw = text[a + an - 1].split()
            if args.source == "qul":
                g = qul.get(str(a + an - 1))
                if not g:
                    continue
                words = [{"startMs": x[0], "endMs": x[1], "interpolated": False}
                         for x in g]
            else:
                sl = silences(wav, min_silence_ms=100)
                onset = sl[0][1] if sl and sl[0][0] <= 40 else 0
                words, meta = ayah_word_times(wav, 0, dur, text[a + an - 1],
                                              f"{key}_s{sn:03d}_a{an:03d}",
                                              onset_ms=onset)
                if not words:
                    continue
            for i, w in enumerate(words[:len(raw)]):
                cands.append((sn, an, i, w, wav,
                              norm(raw[i]),
                              norm(raw[i - 1]) if i > 0 else None,
                              norm(raw[i + 1]) if i + 1 < len(raw) else None))
    rng.shuffle(cands)
    cands = cands[: args.sample]
    print(f"عينة {len(cands)} كلمة من {len(args.surah)} سورة\n", flush=True)

    counts, rows = {}, []
    for sn, an, i, w, wav, tgt, prv, nxt in cands:
        heard = transcribe_clip(wav, w["startMs"], w["endMs"], f"{sn}_{an}_{i}")
        v = verdict(heard, tgt, prv, nxt)
        counts[v] = counts.get(v, 0) + 1
        rows.append({"ayah": f"{sn}:{an}", "w": i + 1, "verdict": v,
                     "target": tgt, "heard": heard,
                     "ms": [w["startMs"], w["endMs"]],
                     "interp": w["interpolated"]})
        print(f"  {sn}:{an} ك{i+1} [{w['startMs']}-{w['endMs']}] {v}"
              f" · هدف «{tgt}» · سُمع «{heard}»", flush=True)

    n = len(rows)
    good = counts.get("EXACT", 0) + counts.get("CONTAINS", 0)
    print(f"\n=== نتيجة الدورة الكاملة على {n} كلمة ===")
    for k in sorted(counts, key=lambda x: -counts[x]):
        print(f"  {k}: {counts[k]} ({counts[k]/n*100:.1f}%)")
    print(f"\n✅ الكلمة مسموعة داخل مقطعها: {good}/{n} = {good/n*100:.1f}%")
    print(f"⚠️ تسرّب من الجارة: {counts.get('BLEED_PREV',0)+counts.get('BLEED_NEXT',0)}")
    print(f"⛔ منزاح كلياً: {counts.get('WRONG_PREV',0)+counts.get('WRONG_NEXT',0)+counts.get('MISMATCH',0)}")
    out = os.path.join(WORK, f"roundtrip_{args.source}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"counts": counts, "rows": rows}, f, ensure_ascii=False, indent=1)
    print(f"التفاصيل: {out}")
    shutil.rmtree(os.path.join(WORK, "rt"), ignore_errors=True)


if __name__ == "__main__":
    main()
