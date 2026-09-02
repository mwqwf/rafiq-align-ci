# -*- coding: utf-8 -*-
"""حقيقة أرضية «فترة الصمت» + صوت مضموم — نسخة v2 تكتب في alignment_v2/work حصراً.

منقول منهجياً عن tools/alignment/calibrate.py (لا يُعدَّل الإنتاجي) مع تغيير المسار.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "alignment"))
from common import FFMPEG, ffprobe_duration_ms, fetch_retry, to_wav16k  # noqa: E402
from vad import silences  # noqa: E402

W2 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "work")
HAFS_AYAH_BASE = "https://everyayah.com/data/Husary_128kbps/"
# مصادر آية-بآية للمعايرة (كلها حفص) — المفتاح يفصل مجلدات العمل والكاش
SOURCES = {
    "husary_hafs": "https://everyayah.com/data/Husary_128kbps/",
    "minshawy_hafs": "https://everyayah.com/data/Minshawy_Murattal_128kbps/",
    # ⚠️ `segments_husary.jz` (أصل QUL) مؤقّت على الحصري **المعلم** لا المرتل —
    # نسبة مدى الكلام بين التسجيلين 1.25× (مقيسة). فهذا هو المصدر الصحيح لأي
    # معايرة كلمية ضد QUL.
    "husary_muallim": "https://everyayah.com/data/Husary_Muallim_128kbps/",
}


def _fetch(url, dest):
    if not os.path.exists(dest) or os.path.getsize(dest) < 1000:
        fetch_retry(url, dest)
    return dest


def ayah_dir(surah_no, key="husary_hafs"):
    d = os.path.join(W2, f"gt_{key}_{surah_no:03d}")
    os.makedirs(d, exist_ok=True)
    return d


def download_ayahs(surah_no, ayah_count, base=HAFS_AYAH_BASE, key="husary_hafs", log=print):
    d = ayah_dir(surah_no, key)
    for a in range(1, ayah_count + 1):
        _fetch(f"{base}{surah_no:03d}{a:03d}.mp3", os.path.join(d, f"{a:03d}.mp3"))
        if a % 25 == 0:
            log(f"    نُزّل {a}/{ayah_count}")
    return d


def ground_truth(surah_no, ayah_count, base=HAFS_AYAH_BASE, key="husary_hafs"):
    """لكل آية: الفترة الصامتة المقبولة [نهاية كلام السابقة، بداية كلام هذه]."""
    d = download_ayahs(surah_no, ayah_count, base, key, log=lambda *_: None)
    bounds, t, prev_speech_end = [], 0, 0
    for a in range(1, ayah_count + 1):
        p = os.path.join(d, f"{a:03d}.mp3")
        dur = ffprobe_duration_ms(p)
        sil = silences(to_wav16k(p), min_silence_ms=120)
        onset = sil[0][1] if sil and sil[0][0] <= 40 else 0
        offset = sil[-1][0] if sil and sil[-1][1] >= dur - 250 else dur
        bounds.append({"ayah": a, "startMs": t, "okFrom": prev_speech_end,
                       "okTo": t + onset, "speechStart": t + onset})
        prev_speech_end = t + offset
        t += dur
    return bounds


def concat_surah(surah_no, ayah_count, key="husary_hafs"):
    d = ayah_dir(surah_no, key)
    out = os.path.join(W2, f"concat_{key}_s{surah_no:03d}.wav")
    if not os.path.exists(out):
        wavs = [to_wav16k(os.path.join(d, f"{a:03d}.mp3")) for a in range(1, ayah_count + 1)]
        lst = os.path.join(d, "concat.txt")
        with open(lst, "w", encoding="utf-8") as f:
            for w in wavs:
                f.write("file '" + w.replace("\\", "/") + "'\n")
        subprocess.run([FFMPEG, "-y", "-v", "error", "-f", "concat", "-safe", "0",
                        "-i", lst, "-ar", "16000", "-ac", "1", out], check=True)
    return out


def boundary_error(start_ms, g):
    """خطأ الحد بمقياس calibrate.py: 0 داخل فترة الصمت المقبولة."""
    if start_ms is None:
        return None
    if g["okFrom"] <= start_ms <= g["okTo"]:
        return 0
    return start_ms - g["okFrom"] if start_ms < g["okFrom"] else start_ms - g["okTo"]


# ---------------------------------------------------------------------------
# الضمّ المُحكم (tight concat) — إعادة إنتاج ظاهرة MED بحقيقة أرضية مضبوطة
# ---------------------------------------------------------------------------
# اكتشاف مقيس: الضمّ العادي لملفات الآيات **لا يعيد إنتاج MED إطلاقاً**
# (مريم الحصري/حفص مضمومة: 97 HIGH وصفر MED)، لأن كل ملف آية يحمل صمتاً في
# طرفيه فيفصل VAD الآيات دائماً. أما التسجيل المتصل الحقيقي (قالون) ففيه
# 34.2% MED إجمالاً و74% في مريم — لأن القارئ يصل الآيات بنَفَس واحد.
#
# الحل: نقصّ صمت الطرفين من كل ملف آية ونضمّها بفجوة `gap_ms` أصغر من عتبة
# VAD (180م.ث) ⇒ يُجبَر VAD على دمج الآيات في مقطع واحد ⇒ **الظاهرة نفسها**،
# وحدودها معلومة بالمللي حرفياً لأننا نحن من ألّف الملف. اختبار إجهاد أقسى من
# الواقع (100% من الحدود داخل مقاطع، لا 34%).


def speech_extent(mp3_path, min_silence_ms=120):
    """[بداية الكلام، نهايته] بالمللي داخل ملف آية."""
    dur = ffprobe_duration_ms(mp3_path)
    sil = silences(to_wav16k(mp3_path), min_silence_ms=min_silence_ms)
    start = sil[0][1] if sil and sil[0][0] <= 40 else 0
    end = sil[-1][0] if sil and sil[-1][1] >= dur - 250 else dur
    return max(0, start), min(dur, end)


def tight_concat(surah_no, ayah_count, gap_ms=80, key="husary_hafs", base=HAFS_AYAH_BASE):
    """يعيد (مسار wav، حدود). كل حد: فجوة صمت معلومة بين كلام آيتين متتاليتين."""
    d = download_ayahs(surah_no, ayah_count, base, key, log=lambda *_: None)
    out = os.path.join(W2, f"tight{gap_ms}_{key}_s{surah_no:03d}.wav")
    meta = out + ".bounds.json"
    if os.path.exists(out) and os.path.exists(meta):
        import json
        with open(meta, encoding="utf-8") as f:
            return out, json.load(f)
    parts, bounds, t, prev_end = [], [], 0, 0
    gap_dir = os.path.join(W2, "tightparts", f"{key}_s{surah_no:03d}_{gap_ms}")
    os.makedirs(gap_dir, exist_ok=True)
    silence_wav = os.path.join(gap_dir, "gap.wav")
    if gap_ms > 0 and not os.path.exists(silence_wav):
        subprocess.run([FFMPEG, "-y", "-v", "error", "-f", "lavfi",
                        "-i", "anullsrc=r=16000:cl=mono", "-t", f"{gap_ms/1000:.3f}",
                        silence_wav], check=True)
    for a in range(1, ayah_count + 1):
        src = os.path.join(d, f"{a:03d}.mp3")
        s0, e0 = speech_extent(src)
        piece = os.path.join(gap_dir, f"{a:03d}.wav")
        if not os.path.exists(piece):
            subprocess.run([FFMPEG, "-y", "-v", "error", "-i", src,
                            "-ss", f"{s0/1000:.3f}", "-to", f"{e0/1000:.3f}",
                            "-ar", "16000", "-ac", "1", piece], check=True, timeout=120)
        if a > 1 and gap_ms > 0:
            parts.append(silence_wav)
            t += gap_ms
        bounds.append({"ayah": a, "okFrom": prev_end, "okTo": t, "speechStart": t})
        dur = ffprobe_duration_ms(piece)
        parts.append(piece)
        t += dur
        prev_end = t
    lst = os.path.join(gap_dir, "list.txt")
    with open(lst, "w", encoding="utf-8") as f:
        for p in parts:
            f.write("file '" + p.replace("\\", "/") + "'\n")
    subprocess.run([FFMPEG, "-y", "-v", "error", "-f", "concat", "-safe", "0",
                    "-i", lst, "-ar", "16000", "-ac", "1", out], check=True)
    import json
    with open(meta, "w", encoding="utf-8") as f:
        json.dump(bounds, f, ensure_ascii=False)
    return out, bounds
