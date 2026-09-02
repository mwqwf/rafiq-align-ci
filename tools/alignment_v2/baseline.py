# -*- coding: utf-8 -*-
"""خط أساس v2: يشغّل خط المحاذاة الإنتاجي على سورة ويحتفظ **بالمقاطع** (يحتاجها الصقل).

لا يعدّل شيئاً في tools/alignment — يستورد منه فقط.
python baseline.py --surah 19
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "alignment"))
from align import derive_boundaries  # noqa: E402
from common import ffprobe_duration_ms, load_index, load_text, norm, surah_slice, to_wav16k  # noqa: E402
import transcribe_v2  # noqa: E402
from vad import silences  # noqa: E402
from validate import band, check_surah  # noqa: E402

from gt import SOURCES, W2, concat_surah, download_ayahs, ground_truth, tight_concat  # noqa: E402


def build(surah_no, riwaya="hafs", key="husary_hafs", gap_ms=None, log=print):
    base = SOURCES[key]
    """يعيد dict فيه segments وentries وtotalMs — ويخزّنه كي لا يُعاد التفريغ."""
    os.makedirs(W2, exist_ok=True)
    suffix = f"tight{gap_ms}_" if gap_ms is not None else ""
    cache = os.path.join(W2, f"baseline_{suffix}{key}_s{surah_no:03d}.json")
    index = load_index()
    a, b, s = surah_slice(index, surah_no)
    ref_ayahs = load_text(riwaya)[a:b]
    if os.path.exists(cache):
        with open(cache, encoding="utf-8") as f:
            d = json.load(f)
        # الكاش يحمل نتائج التفريغ لكن الصوت قد يكون حُذف (طوارئ القرص). الصقل
        # يحتاجه لحساب الصمت الدقيق وحده ⇒ أعِد بناءه بلا إعادة تفريغ.
        if not os.path.exists(d.get("wav", "")):
            log("الكاش موجود والصوت مفقود — يُعاد بناء الصوت بلا إعادة تفريغ…")
            download_ayahs(surah_no, s["ayahs"], base, key, log=log)
            if gap_ms is not None:
                audio, _ = tight_concat(surah_no, s["ayahs"], gap_ms, key, base)
            else:
                audio = concat_surah(surah_no, s["ayahs"], key)
            d["audio"], d["wav"] = audio, to_wav16k(audio)
        d["refAyahs"] = ref_ayahs
        return d
    log(f"تنزيل وضمّ ملفات آيات {s['name']} ({s['ayahs']} آية)…")
    download_ayahs(surah_no, s["ayahs"], base, key, log=log)
    if gap_ms is not None:
        audio, gt_bounds = tight_concat(surah_no, s["ayahs"], gap_ms, key, base)
    else:
        audio, gt_bounds = concat_surah(surah_no, s["ayahs"], key), None
    wav = to_wav16k(audio)
    total_ms = ffprobe_duration_ms(audio)
    sil = silences(wav)
    log(f"VAD: {len(sil)} فترة صمت، المدة {total_ms//1000}ث")
    segments = transcribe_v2.transcribe(wav, total_ms, sil, f"{suffix}{key}_s{surah_no:03d}", log=log)
    log(f"تفريغ: {len(segments)} مقطعاً")
    entries = derive_boundaries(segments, ref_ayahs)
    for e in entries:
        if e["endMs"] is not None and e["endMs"] > total_ms:
            e["endMs"] = total_ms
    issues = check_surah(entries, [len(norm(t).replace(" ", "")) for t in ref_ayahs], total_ms)
    d = {"surah": surah_no, "riwaya": riwaya, "key": key, "wav": wav, "audio": audio,
         "gapMs": gap_ms, "gtBounds": gt_bounds,
         "totalMs": total_ms, "segments": segments, "entries": entries, "issues": issues}
    with open(cache, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    d["refAyahs"] = ref_ayahs
    return d


def report(d, log=print):
    counts = {}
    for e in d["entries"]:
        bn = band(e["conf"]) if e["startMs"] is not None else "MISSING"
        counts[bn] = counts.get(bn, 0) + 1
    log(f"نطاقات خط الأساس: {counts}")
    return counts


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--surah", type=int, required=True)
    args = ap.parse_args()
    d = build(args.surah)
    report(d)
    gt = ground_truth(args.surah, len(d["entries"]))
    from gt import boundary_error
    errs = [boundary_error(e["startMs"], g) for e, g in zip(d["entries"], gt)]
    ok = sum(1 for x in errs if x is not None and abs(x) <= 300)
    print(f"ضمن ±300م.ث: {ok}/{len(errs)} = {ok/len(errs)*100:.1f}%")
