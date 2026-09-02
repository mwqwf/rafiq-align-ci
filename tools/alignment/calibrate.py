# -*- coding: utf-8 -*-
"""معايرة D-025: الحصري/حفص — ملف السورة مقابل الحقيقة الأرضية من ملفات الآيات.

الحقيقة الأرضية: مدد ملفات الآيات (everyayah قصّت من نفس التلاوة) ⇒ حدود تراكمية.
DoD: ≥95% من الحدود ضمن ±300م.ث · 100% عدّ الآي · ≥90% استدعاء للأخطاء >500م.ث في MED/LOW.

python calibrate.py --surah 1
"""
import argparse
import json
import os
import urllib.request

from common import WORK, ffprobe_duration_ms, load_index, surah_slice
from pipeline import run_surah
from validate import band

SOURCES = {
    "husary_hafs": ("hafs", "https://everyayah.com/data/Husary_128kbps/"),
    "dosary_warsh": ("warsh", "https://everyayah.com/data/warsh/warsh_ibrahim_aldosary_128kbps/"),
}
AYAH_BASE = SOURCES["husary_hafs"][1]
SURAH_BASE = "https://download.quranicaudio.com/quran/mahmood_khaleel_al-husaree/"


def fetch(url, dest):
    if not os.path.exists(dest) or os.path.getsize(dest) < 1000:
        urllib.request.urlretrieve(url, dest)
    return dest


def ground_truth(surah_no, ayah_count, base=AYAH_BASE, key=""):
    """حقيقة أرضية بفترة سماح: لكل حد آية، الفترة الصامتة المقبولة
    [نهاية كلام السابقة، بداية كلام هذه الآية] — أي حد داخلها صائب سمعياً."""
    from common import to_wav16k
    from vad import silences
    d = os.path.join(WORK, f"gt_{key}{surah_no:03d}")
    os.makedirs(d, exist_ok=True)
    bounds, t = [], 0
    prev_speech_end = 0
    for a in range(1, ayah_count + 1):
        p = fetch(f"{base}{surah_no:03d}{a:03d}.mp3", os.path.join(d, f"{a:03d}.mp3"))
        dur = ffprobe_duration_ms(p)
        sil = silences(to_wav16k(p), min_silence_ms=120)
        onset = sil[0][1] if sil and sil[0][0] <= 40 else 0
        offset = sil[-1][0] if sil and sil[-1][1] >= dur - 250 else dur
        bounds.append({"ayah": a, "startMs": t,
                       "okFrom": prev_speech_end, "okTo": t + onset,
                       "speechStart": t + onset})
        prev_speech_end = t + offset
        t += dur
    return bounds


def compare(entries, gt):
    """خطأ الحد = بعده عن فترة الصمت المقبولة (0 إن وقع داخلها)."""
    errs = []
    for e in entries:
        g = gt[e["ayahIdx"]]
        if e["startMs"] is None:
            errs.append({"ayah": g["ayah"], "err": None, "band": "MISSING"})
            continue
        s = e["startMs"]
        if g["okFrom"] <= s <= g["okTo"]:
            err = 0
        elif s < g["okFrom"]:
            err = s - g["okFrom"]
        else:
            err = s - g["okTo"]
        errs.append({"ayah": g["ayah"], "err": err, "band": band(e["conf"])})
    return errs


def concat_surah(surah_no, ayah_count, key=""):
    """ضمّ ملفات الآيات إلى wav واحد ⇒ حقيقة أرضية مضبوطة (نفس التسجيل حتماً)."""
    import subprocess

    from common import FFMPEG, to_wav16k
    d = os.path.join(WORK, f"gt_{key}{surah_no:03d}")
    out = os.path.join(WORK, f"concat_{key}s{surah_no:03d}.wav")
    if not os.path.exists(out):
        wavs = [to_wav16k(os.path.join(d, f"{a:03d}.mp3")) for a in range(1, ayah_count + 1)]
        lst = os.path.join(d, "concat.txt")
        with open(lst, "w") as f:
            for w in wavs:
                f.write(f"file '{w}'\n")
        subprocess.run([FFMPEG, "-y", "-v", "error", "-f", "concat", "-safe", "0",
                        "-i", lst, "-ar", "16000", "-ac", "1", out], check=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--surah", type=int, required=True)
    ap.add_argument("--source", choices=["concat", "surahfile"], default="concat",
                    help="concat: حقيقة أرضية مضبوطة من ضم ملفات الآيات نفسها")
    ap.add_argument("--reciter", choices=list(SOURCES), default="husary_hafs")
    args = ap.parse_args()
    index = load_index()
    _, _, s = surah_slice(index, args.surah)
    os.makedirs(WORK, exist_ok=True)
    riwaya, ayah_base = SOURCES[args.reciter]
    key = args.reciter + "_"
    gt_pre = ground_truth(args.surah, s["ayahs"], ayah_base, key)  # ينزّل ملفات الآيات أولاً
    if args.source == "concat":
        surah_audio = concat_surah(args.surah, s["ayahs"], key)
    else:
        surah_audio = fetch(f"{SURAH_BASE}{args.surah:03d}.mp3",
                            os.path.join(WORK, f"husary_s{args.surah:03d}.mp3"))
    result = run_surah(surah_audio, args.surah, riwaya)
    gt = ground_truth(args.surah, s["ayahs"], ayah_base, key)
    errs = compare(result["entries"], gt)
    valid = [e for e in errs if e["err"] is not None]
    within = sum(1 for e in valid if abs(e["err"]) <= 300)
    big = [e for e in valid if abs(e["err"]) > 500]
    flagged = sum(1 for e in big if e["band"] in ("MED", "LOW"))
    print("\n=== نتيجة المعايرة ===")
    print(f"حدود ضمن ±300م.ث: {within}/{len(errs)} = {within/len(errs)*100:.1f}% (الهدف ≥95%)")
    print(f"أخطاء >500م.ث: {len(big)} — موسومة MED/LOW: {flagged} "
          f"({flagged/len(big)*100:.0f}% استدعاء)" if big else "لا أخطاء >500م.ث")
    for e in errs:
        mark = "✅" if e["err"] is not None and abs(e["err"]) <= 300 else "❌"
        print(f"  {mark} آية {e['ayah']}: خطأ {e['err']}م.ث [{e['band']}]")
    out = os.path.join(WORK, f"calibration_{args.reciter}_s{args.surah:03d}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"surah": args.surah, "errors": errs, "result": result}, f, ensure_ascii=False, indent=1)
    print(f"التفاصيل: {out}")


if __name__ == "__main__":
    main()
