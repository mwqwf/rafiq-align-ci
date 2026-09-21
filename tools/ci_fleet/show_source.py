#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يطبع **مصدرَ القارئ المسجَّل في الكتالوج** — قراءةٌ محضةٌ تمنع التخمين.

    python tools/ci_fleet/show_source.py sousi/soufi_sousi douri/deban_douri

⛔ **العطبُ الذي وُلد منه (مقيسٌ 2026-09-21):** خمّنتُ قالبَ رابطٍ لـ`soufi_sousi`
من نمط قارئٍ آخر، فأُنفقت **محاذاةُ CTC كاملةً بأربعة أجزاءٍ وسقطت الأربعةُ**
(‏404 على كلّ سورة، وقد تحقّقتُ منه بعدها بنفسي). ⇒ ساعةٌ ونصفٌ من العمل ضاعت
لأنّ المصدرَ خُمّن ولم يُقرأ.
⛔ **وأخطرُ من الهدر:** قالبٌ خاطئٌ يصيب سوراً موجودةً عند قارئٍ آخر **يُنتج
فهرساً يحاذي صوتَ غيره** — وذاك تحريفٌ لا نقص. فالمصدرُ يُقرأ من الكتالوج دائماً.

⚖️ قراءةٌ محضة: تستعمل `catalog_bases()` نفسَها التي تستعملها حلقةُ الاسترجاع،
ولا تكتب في الدلو بايتاً ولا تمسّ حارساً.
"""
from __future__ import annotations
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
import restore_loop as rl                                            # noqa: E402


def main() -> int:
    args = sys.argv[1:]
    bases = rl.catalog_bases()
    if not args:
        print(f"الكتالوجُ فيه {len(bases)} مدخلاً. مرّر <رواية>/<قارئ> لطباعة مصدره.")
        return 0
    rc = 0
    for a in args:
        riwaya, _, rid = a.partition("/")
        base = rl.source_base(bases, riwaya, rid, 1)
        if base:
            print(f"✅ {a}\t{base}{{s:03d}}.mp3")
        else:
            print(f"⛔ {a}\tلا مصدرَ في الكتالوج — ولا يُخمَّن")
            rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
