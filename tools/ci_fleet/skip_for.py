#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تخطّي البسملة لسورةٍ بعينها من مُدخل `skip_ms` في `realign_surah.yml` (2026-09-30).

    python tools/ci_fleet/skip_for.py "<skip_ms>" <سورة>   ⇒ يطبع م.ث

‏`skip_ms` إمّا عددٌ واحد (‏السلوكُ القديم: القيمةُ نفسُها لكلّ سورة) أو **خريطةٌ لكلّ سورة**
‏`95:8030,97:6903` — فتُصلَح مطالعُ متعدّدةٌ لقارئٍ في تشغيلةٍ واحدة بدل جولاتٍ متتالية
(‏qeryo_qalun: أربعُ جولاتٍ ≈ ثلاثُ ساعات لأنّ القيمةَ كانت واحدة).
⛔ سورةٌ مطلوبةٌ ليست في الخريطة **تُردّ** — لا تُفترض لها قيمة (‏التخطّي مقيسٌ لكلّ سورة لا مخمَّن).
"""
import re
import sys


def skip_for(spec: str, surah: int) -> int:
    spec = (spec or "0").strip()
    if re.fullmatch(r"\d+", spec):
        return int(spec)
    if not re.fullmatch(r"\d+:\d+(,\d+:\d+)*", spec):
        raise ValueError(f"صيغةُ skip_ms غيرُ مفهومة: {spec!r} — عددٌ أو «سورة:م.ث,…»")
    m = {}
    for part in spec.split(","):
        s, ms = part.split(":")
        if int(s) in m:
            raise ValueError(f"السورة {s} مكرّرةٌ في الخريطة")
        m[int(s)] = int(ms)
    if surah not in m:
        raise ValueError(f"السورة {surah} ليست في خريطة التخطّي {spec!r} — لا تُخمَّن قيمتُها")
    return m[surah]


if __name__ == "__main__":
    try:
        print(skip_for(sys.argv[1], int(sys.argv[2])))
    except ValueError as ex:
        sys.exit(f"⛔ {ex}")
