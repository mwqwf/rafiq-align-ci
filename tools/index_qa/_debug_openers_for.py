#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تشخيصٌ لمرّةٍ واحدة: `startMs`/`endMs` لآية 1 من سورٍ بعينها في فهرسٍ ما —
لحساب `skip_ms` صحيحٍ لإعادة محاذاة مطلعٍ ابتلع بسملتَه (بدلاً من تخمين رقم).

    python tools/index_qa/_debug_openers_for.py <مفتاحٌ في timings أو timings-staging> <سورة1,سورة2,...>

قراءةٌ فحسب — لا يكتب شيئاً.
"""
from __future__ import annotations

import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                 # noqa: BLE001
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run as _run  # noqa: E402


def main():
    if len(sys.argv) < 3:
        sys.exit("الاستعمال: _debug_openers_for.py <مفتاح> <سور مفصولة بفواصل>")
    key = sys.argv[1]
    surahs = [int(x) for x in sys.argv[2].split(",")]
    idx, sha = _run.fetch_index(key)
    print(f"— {key}  (بصمة {sha[:16]}…)")
    by_ayah = {}
    for e in idx.get("entries", []):
        s, a = (int(x) for x in e["ayahId"].split(":"))
        if s in surahs and a == 1:
            by_ayah[s] = e
    for s in surahs:
        e = by_ayah.get(s)
        if e is None:
            print(f"    سورة {s}:1  ⛔ لا مدخل")
            continue
        print(f"    سورة {s}:1  startMs={e.get('startMs')}  endMs={e.get('endMs')}"
              f"  المدّة={e.get('endMs', 0) - e.get('startMs', 0)}م.ث")


if __name__ == "__main__":
    main()
