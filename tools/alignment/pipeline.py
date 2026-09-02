# -*- coding: utf-8 -*-
"""تشغيل خط المحاذاة على سورة من ملف سورة كامل.

python pipeline.py --wav path/to/surah.wav --surah 1 --riwaya hafs [--json out.json]
أو --url لتنزيل ملف السورة أولاً (لا يُعاد توزيعه — للفهرسة فقط).
"""
import argparse
import json
import os
import sys
import urllib.request

# دمج الجيل الثاني (2026-09-01، مذكرة rafiq-v2 التساعية): مشروط بALIGN_REFINE=1
# كي لا يختلط محركان داخل فهرس واحد — يُفعَّل لدفعة كاملة أو لا يُفعَّل.
REFINE = os.environ.get("ALIGN_REFINE") == "1"
if REFINE:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "alignment_v2"))

from align import derive_boundaries
from common import WORK, ffprobe_duration_ms, load_index, load_text, norm, surah_slice, to_wav16k
from transcribe import transcribe
from vad import silences
from validate import band, check_surah


def _repair_prefix_absorption(entries, wav, ref_ayahs, log=print):
    """إصلاح جراحي (2026-09-01): بسملة/استعاذة ابتُلعت في الآية الأولى.

    بصمة العطب: startMs للآية 1 < 3000م.ث في سورة ذات تمهيد. العلاج: VAD دقيق
    (90م.ث/0.06) داخل مطلع الملف؛ آخر صمت قوي (≥600م.ث) نهايته في [3ث،20ث]
    هو فاصل التمهيد. حارس نصي: إن طابق تفريغ [0،القطع] كلمات الآية 1 الأولى
    مطابقة صريحة أُجهض القطع (لا تمهيد في التسجيل).
    """
    from vad import silences as _sil
    from transcribe import transcribe_range
    from common import norm as _norm
    e0 = entries[0]
    if e0["startMs"] is None or e0["startMs"] >= 3000:
        return False
    fine = [x for x in _sil(wav, min_silence_ms=90, rel_threshold=0.06)
            if x[1] <= min(e0["endMs"], 25000)]
    strong = [x for x in fine if (x[1] - x[0]) >= 600 and 3000 <= x[1] <= 20000]
    if not strong:
        log("  ⚠️ بصمة ابتلاع تمهيد بلا فاصل صمت قوي — تُترك للمراجعة")
        return False
    first_words = set(_norm(ref_ayahs[0]).split()[:4])
    # آخر صمت قوي قد يقع داخل الآية 1 نفسها (سور المائدة/الأنفال/الحج) —
    # نتراجع عبر المرشحين من الأحدث حتى يجيز الحارس النصي القطع.
    for cand_s, cand_e in reversed(strong):
        cut = cand_e
        probe = transcribe_range(wav, 0, cut, f"prefixprobe{cut}")
        exact_hits = sum(1 for w in probe if w in first_words)
        if exact_hits >= 2:
            log(f"  ↩️ [0,{cut}] يشمل مطلع الآية 1 ({exact_hits}) — أتراجع لمرشح أقدم")
            continue
        old = e0["startMs"]
        e0["startMs"] = cut
        e0["snapped"] = True
        log(f"  🔧 عُزل التمهيد: الآية 1 من {old} إلى {cut}م.ث (تفريغ التمهيد: {' '.join(probe) or '—'})")
        return True
    log("  ⚠️ كل مرشحي الصمت يشملون مطلع الآية 1 — لا تمهيد في التسجيل، تُرك كما هو")
    return False


def run_surah(audio_path, surah_no, riwaya, log=print):
    index = load_index()
    text = load_text(riwaya)
    a, b, s = surah_slice(index, surah_no)
    ref_ayahs = text[a:b]
    wav = to_wav16k(audio_path)
    total_ms = ffprobe_duration_ms(audio_path)
    log(f"سورة {s['name']} ({surah_no}) — {s['ayahs']} آية، {total_ms//1000}ث، رواية {riwaya}")
    sil = silences(wav)
    log(f"VAD: {len(sil)} فترة صمت")
    segments = transcribe(wav, total_ms, sil, log=log)
    log(f"تفريغ: {len(segments)} مقطعاً، {sum(len(s['words']) for s in segments)} كلمة")
    entries = derive_boundaries(segments, ref_ayahs,
                                with_basmala_prefix=("istiadha_only" if surah_no in (1, 9) else True))
    if entries:  # الفاتحة أيضاً: استعاذتها تُعزل عن آية البسملة (درس قزابري v2)
        _repair_prefix_absorption(entries, wav, ref_ayahs, log=log)
    for e in entries:  # لصق الحدود قد يمد النهاية الأخيرة بضع م.ث بعد نهاية الملف
        if e["endMs"] is not None and e["endMs"] > total_ms:
            e["endMs"] = total_ms
    if REFINE:  # الترتيب حرج (مذكرة الدمج بند 1): الصقل قبل check_surah
        from refine import refine_surah
        starts_before = [e["startMs"] for e in entries]
        rstats = refine_surah({"segments": segments, "entries": entries,
                               "refAyahs": ref_ayahs, "wav": wav,
                               "totalMs": total_ms, "surah": surah_no}, log=lambda *a: None)
        # إعادة لصق السلسلة (v2.1): الحد المصقول يجر نهاية سابقه الملصوقة معه،
        # والمصقول على صمت حقيقي يُعامل مسنوداً (عقد startApprox)
        for k in range(1, len(entries)):
            e, p = entries[k], entries[k - 1]
            if e.get("refined") and e["startMs"] != starts_before[k]:
                if p["endMs"] is not None and p["endMs"] == starts_before[k]:
                    p["endMs"] = e["startMs"]
                e["snapped"] = True
        # إنقاذ آية-1 المبتلعة سلسلياً: مدتها المجهرية بعد القطع تتسع بعد اللصق
        e0 = entries[0] if entries else None
        if e0 and e0["startMs"] is not None and e0["conf"] < 0.45:
            dur = (e0["endMs"] or 0) - e0["startMs"]
            ch = len(norm(ref_ayahs[0]).replace(" ", ""))
            if dur >= max(1200, ch * 45):
                e0["conf"] = 0.5  # MED صادقة: تشغيل فقط حتى تحقق أدق
                log(f"  🩹 آية-1 استعادت مدى معقولاً ({dur}م.ث) — رفعت لMED")
        log(f"  صقل ج2: {rstats['refineStats'] if isinstance(rstats, dict) and 'refineStats' in rstats else rstats}")
    char_counts = [len(norm(t).replace(" ", "")) for t in ref_ayahs]
    issues = check_surah(entries, char_counts, total_ms)
    bands = {}
    for e in entries:
        bands[band(e["conf"]) if e["startMs"] is not None else "MISSING"] = \
            bands.get(band(e["conf"]) if e["startMs"] is not None else "MISSING", 0) + 1
    log(f"نطاقات الثقة: {bands}")
    for i in issues:
        log(f"  ⚠️ {i}")
    return {"surah": surah_no, "riwaya": riwaya, "totalMs": total_ms,
            "entries": entries, "issues": issues, "bands": bands}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav")
    ap.add_argument("--url")
    ap.add_argument("--surah", type=int, required=True)
    ap.add_argument("--riwaya", default="hafs", choices=["hafs", "warsh", "qalun"])
    ap.add_argument("--json")
    args = ap.parse_args()
    audio = args.wav
    if args.url:
        os.makedirs(WORK, exist_ok=True)
        audio = os.path.join(WORK, f"s{args.surah:03d}_{os.path.basename(args.url)}")
        if not os.path.exists(audio):
            urllib.request.urlretrieve(args.url, audio)
    result = run_surah(audio, args.surah, args.riwaya)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=1)
        print(f"كُتب: {args.json}")


if __name__ == "__main__":
    main()
