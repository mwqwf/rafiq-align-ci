# -*- coding: utf-8 -*-
"""🔊 **مرآةُ `AudioLevelV2.audibleSnrDb` على مجموعات القياس** — لمعايرة عتبتَي D-329 برقمٍ لا بحدس.

جلسةُ التطبيق شحنت بوّابةَ «الغرفةِ الصاخبة» (‏D-329): دون **8 د.ب لا حكمَ** بل طلبُ إعادة، ودون
**15** يُعرض الحكمُ موسوماً «تقريبيّ». والعتبتان **معايرةٌ أوّليةٌ على إشاراتٍ اصطناعية** لا على
مجموعاتنا، وطلبت توزيعَ القيم على بنودنا. ⭐ **ولا يُنتظر لذلك بناءُ APK**: الدالّةُ في
`engine/recitation/` (نطاقُنا) فتُقرأ وتُطبَّق على الصوت نفسِه هنا، فتُغلق المعايرةُ اليومَ.

المرآةُ حرفاً بحرف من `AudioLevelV2.kt`:
    FRAME = 320 (‏20 م.ث) · frameRms = جذرُ متوسّطِ المربّعات لكلّ إطار
    percentile = خطّيٌّ كـ`numpy.percentile` · db(v) = 20·log10(max(v, 1e-9))
    noiseFloor = المئينُ 10 من طاقة الإطارات
    snrDb = db(p95) − db(p10) − 3
    audibleSnrDb = snrDb إن كان db(noiseFloor) > −45 dBFS، وإلا None (غرفةٌ هادئةٌ لا تُتَّهم)

    python tools/tasmi_bench/snr_probe.py --sets g1 g2:noise-fan-5 g4 g4n g4n10 g4n20

⚠️ **حدٌّ يُقال:** البوّابةُ في التطبيق تُقاس على التسجيل كما يأتي من الميكروفون. ومجموعاتُنا ملفّاتٌ
مُسوّاةُ الجهارة، و`snrDb` **فرقُ ديسيبلاتٍ فلا يتأثّر بالكسب**، لكن **حارسَ الأرضية (‏−45 dBFS)
يتأثّر** ⇒ يُطبع عددُ البنود التي يحجبها الحارسُ كي لا يُقرأ «هادئٌ» ما هو «خفيضٌ».
"""
import argparse
import os
import sys

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

FRAME = 320
FLOOR_DBFS = -45.0
BLOCK_DB = 8.0
NOISY_DB = 15.0


def frame_rms(x):
    n = len(x) // FRAME
    if n == 0:
        return np.array([float(np.sqrt(np.mean(x.astype(np.float64) ** 2)))])
    y = x[: n * FRAME].astype(np.float64).reshape(n, FRAME)
    return np.sqrt((y * y).mean(axis=1))


def db(v):
    return 20.0 * np.log10(max(float(v), 1e-9))


def snr_of(x):
    """(‏snrDb, أرضيةٌ dBFS, أمسموعةٌ الأرضية) — مرآةُ `audibleSnrDb`."""
    e = frame_rms(x)
    if e.size == 0:
        return None, -999.0, False
    p95, p10 = np.percentile(e, 95), np.percentile(e, 10)
    floor_db = db(p10)
    s = db(p95) - db(p10) - 3.0
    return s, floor_db, floor_db > FLOOR_DBFS


def dir_of(set_name, work):
    if set_name.startswith("g4"):
        return os.path.join(work, set_name)
    if set_name == "g1":
        return os.path.join(work, "wav")
    kind, name = set_name.split(":", 1)
    return os.path.join(work, {"g3": "g3", "g3r": "g3r"}.get(kind, "g2"), name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sets", nargs="+", required=True)
    ap.add_argument("--work", default=os.path.join(HERE, "work"))
    ap.add_argument("--md", default="")
    a = ap.parse_args()

    L = ["| المجموعة | ن | snrDb وسيطاً | المئين 10 | المئين 90 | أدنى | **< 8 (يُحجب)** | **< 15 (تقريبيّ)** | أرضيةٌ غيرُ مسموعة |",
         "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for s in a.sets:
        d = dir_of(s, a.work)
        if not os.path.isdir(d):
            L.append(f"| {s} | ⛔ لا مجلد `{d}` | | | | | | | |")
            continue
        vals, mute = [], 0
        for f in sorted(os.listdir(d)):
            if not f.endswith(".wav"):
                continue
            x, _ = sf.read(os.path.join(d, f), dtype="float32")
            v, _fl, audible = snr_of(x)
            if not audible:
                mute += 1
            else:
                vals.append(v)
            del x
        if not vals:
            L.append(f"| {s} | 0 مسموع · {mute} أرضيتُها خفيضة | | | | | | | {mute} |")
            continue
        v = np.array(vals)
        L.append(f"| `{s}` | {len(v)} | **{np.median(v):.1f}** | {np.percentile(v,10):.1f} | "
                 f"{np.percentile(v,90):.1f} | {v.min():.1f} | "
                 f"**{int((v < BLOCK_DB).sum())} ({(v < BLOCK_DB).mean()*100:.0f}٪)** | "
                 f"**{int((v < NOISY_DB).sum())} ({(v < NOISY_DB).mean()*100:.0f}٪)** | {mute} |")
    md = "\n".join(L)
    print(md)
    if a.md:
        open(a.md, "w", encoding="utf-8").write(md + "\n")


if __name__ == "__main__":
    sys.exit(main())
