# -*- coding: utf-8 -*-
"""إعادة قياس كاملة للسور الثلاث بالحارس الثالث — سورة بسورة مع تنظيف فوري.

قيد القرص: لا يتجاوز الترانزيت اللحظي ~100م.ب — تُنزَّل سورة واحدة وتُقاس ثم
تُحذف صوتياتها قبل التالية. لا استدعاء whisper واحد: كاش التفريغ (`baseline_*.json`)
وكاش النوافذ (`clips/*.words.json`) سليمان، والصوت مطلوب فقط لحساب الصمت الدقيق.
"""
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "alignment"))

from calibrate_v2 import evaluate  # noqa: E402
from gt import W2  # noqa: E402


def free_mb():
    return shutil.disk_usage(W2).free // (1 << 20)


def cleanup(surah_no, key="husary_hafs"):
    for p in (os.path.join(W2, f"tight80_{key}_s{surah_no:03d}.wav"),
              os.path.join(W2, f"tight80_{key}_s{surah_no:03d}.wav.16k.wav")):
        if os.path.exists(p):
            os.remove(p)
    for d in (os.path.join(W2, f"gt_{key}_{surah_no:03d}"),
              os.path.join(W2, "tightparts")):
        if os.path.isdir(d):
            shutil.rmtree(d, ignore_errors=True)


def main():
    for sn in (19, 20, 23):
        print(f"\n########## سورة {sn} — الحر قبل: {free_mb()}م.ب ##########", flush=True)
        try:
            evaluate(sn, gap_ms=80, key="husary_hafs")
        finally:
            cleanup(sn)
            print(f"نُظّفت سورة {sn} — الحر بعد: {free_mb()}م.ب", flush=True)


if __name__ == "__main__":
    main()
