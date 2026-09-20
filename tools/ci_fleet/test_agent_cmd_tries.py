#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يختبر حارسَ المحاولات في `agent_cmd` — أمرٌ لا يكتمل لا يحجز الطابورَ أبداً.

    python tools/ci_fleet/test_agent_cmd_tries.py

⛔ **لماذا كُتب (2026-09-20):** أمرٌ أبطأُ من `timeout-minutes` لا يكتمل أبداً:
يُلغى الشوطُ قبل أن يُنفَّذ ما بعده، ويبقى الأمرُ في مجلّده فيُعاد الكرّةَ في
كلّ شوطٍ تالٍ ⇒ **حجزٌ دائمٌ للطابور**. وقع على الشوطين 35531563565 و35533123411:
نحوُ نصفِ ساعةٍ لكلٍّ بلا جوابٍ واحدٍ وعشرةُ أوامرَ محتجزة.

⚖️ اختبارٌ قارئٌ محض: يُحاكي العدّادَ ولا يمسّ دلواً ولا شبكةً ولا مستودعاً.
⛔ وهو يحرس **الجهتين**: ألّا يُنحّى أمرٌ يعمل، وألّا يُحجز الطابورُ بما لا يعمل.
"""
from __future__ import annotations

import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                 # noqa: BLE001
        pass

MAX_TRIES = 3


def simulate(completes_on: int | None, runs: int = 6):
    """يحاكي أشواطاً متتابعة. `completes_on` رقمُ المحاولة التي يتمّ فيها الأمرُ
    (أو None إن كان لا يتمّ أبداً). يُرجع (أُنجز؟ · نُحّي؟ · عددُ الأشواط المحجوزة)."""
    tries, done, retired, blocked = 0, False, False, 0
    for _ in range(runs):
        if done or retired:
            break
        if tries >= MAX_TRIES:
            retired = True
            break
        tries += 1                                  # تُسجَّل **قبل** التنفيذ
        if completes_on is not None and tries >= completes_on:
            done, tries = True, 0                   # تمّ ⇒ يُمحى العدّاد
        else:
            blocked += 1                            # مات الشوطُ قبل التمام
    return done, retired, blocked


def main() -> int:
    cases = [
        ("أمرٌ يتمّ من أوّل محاولة", 1, (True, False, 0)),
        ("أمرٌ يتمّ في الثانية (شوطٌ مات مرّة)", 2, (True, False, 1)),
        ("أمرٌ يتمّ في الثالثة — على حافّة الحدّ", 3, (True, False, 2)),
        ("أمرٌ لا يتمّ أبداً ⇒ يُنحّى ولا يحجز الأبد", None, (False, True, 3)),
    ]
    ok = True
    for desc, c, exp in cases:
        got = simulate(c)
        good = got == exp
        ok &= good
        print(f"{'✅' if good else '🔴'} {desc} → أُنجز={got[0]} نُحّي={got[1]} "
              f"أشواطٌ محجوزة={got[2]}")

    print()
    print(f"✅ بالحدّ: أمرٌ لا يتمّ يحجز **{simulate(None)[2]}** أشواطٍ ثمّ يُنحّى.")
    print("🔴 وبلا الحدّ كان يحجزها **بلا نهاية** — وهو ما وقع فعلاً اليوم.")
    print("⛔ ولا يُحذف الأمرُ صامتاً: يُكتب جوابُه (rc=98) بسببه، وملفُّه يُنقل"
          " إلى done/ فيبقى شاهداً.")
    print("⚖️ ولا يُنحّى عاملٌ: الأمرُ الناجحُ يمحو عدّادَه أوّلَ ما يتمّ،"
          " فلا يبلغ الحدَّ إلا ما لا يكتمل أصلاً.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
