#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نوافذُ شاهد Whisper لقاعدة المِرساة الضعيفة في بوّابة السماع (‏2026-11-10) — قارئٌ محض.

    python tools/index_qa/heard_weak_windows.py <heard_sNNN.json> <cand_N.json>

`heard_sNNN.json` مخرَجُ `ctc_heard_map --probe` للسورة · `cand_N.json` {"ends": {آية: [بدء، نهاية]}, "pubEnds": {…}|null}
من خطّة `heard_gate.yml`. يطبع نوافذَ `whisper_witness --ayahs` للآيات الممسوسة التي مرساتُها دون 0.5، أو لا شيء.
⛔ لا يحكم: الحكمُ يُعاد في `heard_gate.judge` من الخريطة والشاهد."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import heard_gate as H  # noqa: E402


def main(argv) -> int:
    hm = H.compact_map(json.load(open(argv[0], encoding="utf-8")))
    cand = json.load(open(argv[1], encoding="utf-8"))
    ends = {int(a): v for a, v in cand["ends"].items()}
    plan = H.weak_plan(ends, cand.get("pubEnds"), hm)
    if plan:
        print(H.witness_windows({a: (v[0], v[1]) for a, v in ends.items()}, plan))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
