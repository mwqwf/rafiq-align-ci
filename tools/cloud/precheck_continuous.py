#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""فحصٌ مسبق: أموصولُ الأنفاس هذا القارئ؟ رمز 1 = موصول (يُؤجَّل)، 0 = عادي.

    python tools/cloud/precheck_continuous.py --reciter a_majed --riwaya hafs --base '…'

⛔ لماذا **قبل** الفهرسة لا بعدها: `a_majed` استغرق ساعتين وبلغ 114/114 ثم رفضه
حارس التغطية (غياب 256 آية، 4.1%). والسبب أن VAD لا يجد صمتاً في تلاوته
الموصولة، فتُقطَّع مقاطعه عند السقف الصلب `MAX_SEG_MS=28_000` — قطعاً اعتباطياً
في وسط الكلام لا عند حدٍّ طبيعي: **96% من مقاطعه فوق 20ث ووسطيها 27.1ث**
(مقابل 12.8ث لمرتّلٍ عادي). ومن ثَمّ MED 89% والآيات القصيرة تُبتلع.
⇒ ساعتان تُحرقان على قارئٍ يسقط حتماً. وسورةٌ واحدة تُنزَّل تكشفه في دقيقة.

⚠️ وهو **تأجيلٌ لا حكمٌ بالرداءة**: العلّة في تقطيعنا لا في تلاوته، وعلاجها
(قطعٌ بالطاقة أو بحدود الآي المتوقّعة) عملٌ قادم.
"""
import argparse
import os
import subprocess
import sys
import tempfile
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "alignment"))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

LONG_MS = int(os.environ.get("PRECHECK_LONG_MS", "20000"))
MAX_FRAC = float(os.environ.get("PRECHECK_MAX_LONG_FRAC", "0.70"))
# ⚠️ السورة المُسبار ليست اختياراً حراً: سور قصار الآي (36 و18 و12) تُقطَّع عند
# السقف عند **كل** قارئ تقريباً — قِستُها فصنّفت مرتّلاً مفصولاً معروفاً (‏darweez)
# «موصولاً» بـ99%، أي مقياسٌ يرفض الجميع. سورة النساء (4) طوال الآي فتفرّق:
#   a_majed 99% موصول · darweez 38% عادي · huthaify_qalun 0% عادي (وفهرسه مقبول)
# ⛔ لا تُبدَّل إلى سورةٍ قصيرة الآي مهما أغرى توفيرُ التنزيل.
PROBE_SURAH = int(os.environ.get("PRECHECK_SURAH", "4"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reciter", required=True)
    ap.add_argument("--riwaya", required=True)
    ap.add_argument("--base", required=True)
    a = ap.parse_args()
    url = a.base.format(surah=PROBE_SURAH)
    tmp = tempfile.mkdtemp()
    mp3 = os.path.join(tmp, f"{PROBE_SURAH:03d}.mp3")
    try:
        with urllib.request.urlopen(url, timeout=120) as r, open(mp3, "wb") as f:
            while True:
                c = r.read(1 << 20)
                if not c:
                    break
                f.write(c)
        import transcribe as T                       # noqa: PLC0415
        from pipeline import ffprobe_duration_ms, to_wav16k   # noqa: PLC0415
        from vad import silences                     # noqa: PLC0415
        wav = to_wav16k(mp3)
        segs = T.speech_segments(ffprobe_duration_ms(mp3), silences(wav))
        d = [(e - s) for s, e in segs]
        if not d:
            print("  ⚠️ لا مقاطع — لا حكم، يمضي عادياً", flush=True)
            return 0
        long_n = sum(1 for x in d if x > LONG_MS)
        frac = long_n / len(d)
        avg = sum(d) / len(d) / 1000
        verdict = "موصول" if frac > MAX_FRAC else "عادي"
        print(f"  {a.reciter}: مقاطع={len(d)} · وسطي={avg:.1f}ث · "
              f">20ث={long_n} ({frac*100:.0f}%) ⇒ {verdict}", flush=True)
        return 1 if frac > MAX_FRAC else 0
    except Exception as ex:                          # الفحص يسقط ⇒ لا يمنع
        print(f"  ⚠️ تعذّر الفحص المسبق ({ex}) — يمضي عادياً", flush=True)
        return 0
    finally:
        for p in (mp3, mp3 + ".16k.wav"):
            try:
                os.remove(p)
            except OSError:
                pass
        try:
            os.rmdir(tmp)
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
