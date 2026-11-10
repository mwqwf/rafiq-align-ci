#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⛔ (‏#105 · قرار القائد 2026-11-10) الخريطةُ الجزئيّة (‏`ctc_heard_map --start-ms` ⇒ `windowStartMs`) لم تسمع ما قبل
بدئها: لا تدخل حكماً أبداً (‏heard_gate · الجرد · gap-split)، ولا يُستعمل منها في pin_heard إلا ما بعد بدئها بـ1000م.ث.

    python -m unittest tools/index_qa/test_partial_heard_map.py
"""
from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import heard_gate as H                                           # noqa: E402
import pin_heard as P                                            # noqa: E402

TD = HERE / "testdata" / "opener_letters" / "kurdi40"
FULL = json.loads((TD / "heard_s040.json").read_text(encoding="utf-8"))
ENTS = json.loads((TD / "entries.json").read_text(encoding="utf-8"))


def _partial(ws):
    m = copy.deepcopy(FULL)
    m["windowStartMs"] = ws
    return m


def _idx():
    return {"riwaya": "hafs", "reciterId": "kurdi", "entries": copy.deepcopy(ENTS["entries"]),
            "audioSha256": [ENTS["audioSha256"]]}


class GateNeverJudgesPartial(unittest.TestCase):
    def test_compact_map_refuses(self):
        H.compact_map(FULL)
        with self.assertRaises(ValueError) as cm:
            H.compact_map(_partial(5000))
        self.assertIn("جزئيّة", str(cm.exception))

    def test_zero_is_not_partial(self):
        self.assertIsNone(H.partial_map_error(dict(FULL, windowStartMs=0)))
        self.assertEqual(H.compact_map(dict(FULL, windowStartMs=0)), H.compact_map(FULL))

    def test_disputed_and_dual_paths_go_through_compact_map(self):
        with self.assertRaises(SystemExit):
            P.disputed_claims(_idx(), 40, _partial(5000), {2: 1}, "", wits={})

    def test_census_repeats_refuses(self):
        import entry_window_census as C
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "heard_s040.json"), "w", encoding="utf-8") as f:
            json.dump(_partial(5000), f, ensure_ascii=False)
        rc = C.cmd_repeats(SimpleNamespace(surahs="40", maps=d, riwaya="hafs", out=""))
        self.assertEqual(rc, 2)


class PinUsesOnlyAfterWindow(unittest.TestCase):
    def test_full_map_unchanged(self):
        m, lo = P.usable_map(FULL)
        self.assertIs(m, FULL)
        self.assertIsNone(lo)

    def test_anchors_before_start_plus_1000_are_dropped(self):
        m, lo = P.usable_map(_partial(5800))           # الحدّ 6800: مِرساةُ 40:2 (‏6684) تُسقط
        self.assertEqual(lo, 6800)
        self.assertNotIn("windowStartMs", m)
        self.assertEqual([x[0] for x in P.measured_starts(m, 2)], [7645])
        self.assertTrue(all(x[0] >= 6800 for a in m["heardMap"] for x in P.measured_starts(m, int(a))))

    def test_pin_before_window_refused(self):
        with self.assertRaises(SystemExit) as cm:
            P.pin(_idx(), 40, _partial(5800), {2: 6684})
        self.assertIn("خريطةٌ جزئيّة", str(cm.exception))

    def test_pin_after_window_uses_the_kept_anchor(self):
        # 40:3 مِرساتُها 14729 بعد الحدّ 6800 فتبقى مقيسة
        self.assertEqual(P.measured_starts(P.usable_map(_partial(5800))[0], 3)[0][0],
                         P.measured_starts(FULL, 3)[0][0])
        m, _lo = P.usable_map(_partial(5600))          # الحدّ 6600: مِرساةُ 40:2 (‏6684) تبقى
        self.assertEqual(P.measured_starts(m, 2)[0][0], 6684)


if __name__ == "__main__":
    unittest.main()
