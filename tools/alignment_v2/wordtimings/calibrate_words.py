# -*- coding: utf-8 -*-
"""معايرة إلزامية للتوقيتات الكلمية ضد حقيقة QUL الأرضية (§4.4: وسيط ≤250م.ث).

الحقيقة الأرضية `segments_husary.jz` معرّفة **داخل ملف الآية** (الحصري/حفص من
everyayah): لكل آية قائمة [بداية، نهاية] لكل كلمة. فنشغّل المولّد على **ملف الآية
نفسه** ⇒ أزمنتنا وأزمنة QUL في المرجع الزمني ذاته والمقارنة مباشرة بلا وسيط.

python calibrate_words.py --surah 99 --surah 100 --surah 112
"""
import argparse
import json
import os
import shutil
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_V2 = os.path.dirname(_HERE)
sys.path.insert(0, _V2)
sys.path.insert(0, os.path.join(os.path.dirname(_V2), "alignment"))

from common import QURAN_ASSETS, ffprobe_duration_ms, load_index, load_text, read_jz, surah_slice, to_wav16k  # noqa: E402
from vad import silences  # noqa: E402

from generate import ayah_word_times  # noqa: E402
from gt import SOURCES, download_ayahs  # noqa: E402

WORK = os.path.join(_HERE, "work")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--surah", type=int, action="append", required=True)
    ap.add_argument("--reciter", default="husary_muallim",
                    help="المصدر المطابق لـQUL هو الحصري المعلم لا المرتل")
    args = ap.parse_args()
    base, key = SOURCES[args.reciter], args.reciter
    os.makedirs(WORK, exist_ok=True)
    qul = read_jz(os.path.join(QURAN_ASSETS, "segments_husary.jz"))
    index = load_index()
    text = load_text("hafs")

    errs_start, errs_end, rows = [], [], []
    dropped = []
    for sn in args.surah:
        a, b, s = surah_slice(index, sn)
        d = download_ayahs(sn, s["ayahs"], base, key, log=lambda *_: None)
        print(f"\n=== سورة {sn} ({s['name']}) — {s['ayahs']} آية ===", flush=True)
        for an in range(1, s["ayahs"] + 1):
            gidx = a + an - 1
            gt = qul.get(str(gidx))
            if not gt:
                continue
            mp3 = os.path.join(d, f"{an:03d}.mp3")
            wav = to_wav16k(mp3)
            dur = ffprobe_duration_ms(mp3)
            sil = silences(wav, min_silence_ms=100)
            onset = sil[0][1] if sil and sil[0][0] <= 40 else 0
            words, meta = ayah_word_times(wav, 0, dur, text[gidx],
                                          f"{key}_s{sn:03d}_a{an:03d}", onset_ms=onset)
            if words is None:
                dropped.append((sn, an, meta["reason"], meta["acc"]))
                print(f"  {sn}:{an} ⚠️ سقطت ({meta['reason']}, acc={meta['acc']})", flush=True)
                continue
            n = min(len(words), len(gt))
            for i in range(n):
                es = words[i]["startMs"] - gt[i][0]
                ee = words[i]["endMs"] - gt[i][1]
                errs_start.append(es)
                errs_end.append(ee)
                rows.append({"ayah": f"{sn}:{an}", "w": i + 1, "errStart": es,
                             "errEnd": ee, "interp": words[i]["interpolated"]})
            print(f"  {sn}:{an} ✓ {n} كلمة · acc={meta['acc']} · استقراء {meta['interp']}",
                  flush=True)
            os.remove(wav) if os.path.exists(wav) else None

    def stat(v, name):
        if not v:
            print(f"{name}: لا بيانات")
            return
        av = sorted(abs(x) for x in v)
        med = av[len(av) // 2]
        p90 = av[int(len(av) * 0.9)] if len(av) > 1 else av[0]
        within = sum(1 for x in av if x <= 250)
        print(f"{name}: وسيط |الخطأ| = {med}م.ث · p90 = {p90}م.ث · "
              f"ضمن ±250م.ث: {within}/{len(av)} = {within/len(av)*100:.1f}%")

    print(f"\n=== المعايرة على {len(rows)} كلمة ===")
    stat(errs_start, "بداية الكلمة")
    stat(errs_end, "نهاية الكلمة")
    direct = [r["errStart"] for r in rows if not r["interp"]]
    interp = [r["errStart"] for r in rows if r["interp"]]
    stat(direct, "  منها المسندة مباشرة")
    stat(interp, "  منها المستقرأة")
    print(f"آيات ساقطة (بلا words[]): {len(dropped)} {dropped[:8]}")
    out = os.path.join(WORK, f"calib_words_{key}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"rows": rows, "dropped": dropped}, f, ensure_ascii=False)
    print(f"التفاصيل: {out}")
    for sn in args.surah:                       # تنظيف فوري (D-024 + قيد القرص)
        shutil.rmtree(os.path.join(os.path.dirname(_HERE), "work",
                                   f"gt_{key}_{sn:03d}"), ignore_errors=True)
    print("نُظّفت قصاصات الآيات.")


if __name__ == "__main__":
    main()
