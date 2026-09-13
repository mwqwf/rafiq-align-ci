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
BLOCK_DB = 14.0
NOISY_DB = 18.0


def frame_rms(x):
    n = len(x) // FRAME
    if n == 0:
        return np.array([float(np.sqrt(np.mean(x.astype(np.float64) ** 2)))])
    y = x[: n * FRAME].astype(np.float64).reshape(n, FRAME)
    return np.sqrt((y * y).mean(axis=1))


def db(v):
    return 20.0 * np.log10(max(float(v), 1e-9))


def quiet_floor(e, win=50):
    """🔇 أرضيةٌ بإحصاء الأدنى — مرآةُ `AudioLevelV2.quietFloor` (‏D-344).

    ⛔ المقامُ كان المئينَ العاشرَ من **كلّ** الإطارات، وهو مدىً ديناميٌّ يتأثّر بكثافة الكلام:
    تلاوةٌ نظيفةٌ متّصلةٌ تُقرأ «صاخبة» (‏14.9 د.ب وسيطاً على `g4dense`) فتُحجب وهي صحيحة.
    وبأدنى كلِّ نافذةٍ ثانيةً ثمّ مئينِها 25: **25.8** وأدناها 22.3 ⇒ 8.3 د.ب هامشاً فوق الحجب.
    """
    if e.size < win:
        return float(e.min())
    step = max(1, win // 2)
    mins = [float(e[i:i + win].min()) for i in range(0, e.size - win + 1, step)]
    return float(np.percentile(mins, 25))


def snr_of(x):
    """(‏snrDb, أرضيةٌ dBFS, أمسموعةٌ الأرضية) — مرآةُ `audibleSnrDb`."""
    e = frame_rms(x)
    if e.size == 0:
        return None, -999.0, False
    fl = quiet_floor(e)
    floor_db = db(fl)
    s = db(np.percentile(e, 95)) - floor_db - 3.0
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
    # 📈 **بندٌ بندٌ لا متوسّطَ مجموعة:** العتبةُ تُقرأ من منحنى «‏snrDb ⇒ دقّة» على البنود كلِّها
    # مجموعةً واحدةً (‏180 نقطةً بين 9 و25 د.ب)، لا من ثلاثة متوسّطاتٍ — والمتوسّطُ يخفي التشتّت
    # الذي عليه يُبنى الحجب: ما يهمّ هو **أيُّ بندٍ يُحجب** لا أيُّ مجموعةٍ وسيطُها دون العتبة.
    ap.add_argument("--json", default="", help="قيمُ كلِّ بندٍ (‏id ⇒ snrDb · أرضية · أمسموعة)")
    a = ap.parse_args()

    per = {}
    # ⛔ العنوانُ يُشتقّ من الثابتَين لا يُكتب رقماً: كُتبت «< 8» و«< 15» بعد تغييرهما إلى 14/18
    # فصار الجدولُ **لافتةً كاذبةً على حسابٍ صحيح** — وهو أخطرُ من خطأ حسابٍ لأنّه لا يُشكّ فيه.
    L = [f"| المجموعة | ن | snrDb وسيطاً | المئين 10 | المئين 90 | أدنى | **< {BLOCK_DB:g} (يُحجب)** | **< {NOISY_DB:g} (تقريبيّ)** | أرضيةٌ غيرُ مسموعة |",
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
            per[s + "/" + f[:-4]] = {"set": s, "id": f[:-4], "snrDb": None if v is None else round(float(v), 2),
                           "floorDbfs": round(float(_fl), 2), "audible": bool(audible)}
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
    if a.json:
        import json as _j
        _j.dump(per, open(a.json, "w", encoding="utf-8"), ensure_ascii=False)
        print(str(len(per)) + " بندٍ ⇒ " + a.json)


if __name__ == "__main__":
    sys.exit(main())
