#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`stage_transform.realigned_coverage_error` — الغيابُ الموروث (ctc_gapsplit · 2026-09-30)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stage_transform import AYAH_COUNTS, realigned_coverage_error as f  # noqa: E402
from stage_transform import entry_change_counts

S = 55
FULL = {f"{S}:{a}" for a in range(1, AYAH_COUNTS[S - 1] + 1)}


class InheritedGaps(unittest.TestCase):
    def test_inserted_ayah_does_not_count_unchanged_following_entries_as_moved(self):
        old = [{"ayahId": "3:2", "startMs": 10, "endMs": 20},
               {"ayahId": "3:3", "startMs": 20, "endMs": 30}]
        new = [{"ayahId": "3:1", "startMs": 0, "endMs": 10}] + old
        self.assertEqual(entry_change_counts(old, new), (0, 1, 0))
        moved = [dict(e) for e in new]
        moved[1]["startMs"] = 11
        self.assertEqual(entry_change_counts(old, moved), (1, 1, 0))
    def test_complete_always_ok(self):
        self.assertIsNone(f(FULL - {f"{S}:5"}, FULL, [S]))

    def test_partial_refused_without_flag(self):
        old = FULL - {f"{S}:5", f"{S}:20"}
        self.assertIn("لا يُرفع ناقص", f(old, FULL - {f"{S}:20"}, [S]))

    def test_partial_gain_ok_with_flag(self):
        old = FULL - {f"{S}:5", f"{S}:20"}
        self.assertIsNone(f(old, FULL - {f"{S}:20"}, [S], allow_inherited=True))

    def test_new_loss_refused_with_flag(self):
        old = FULL - {f"{S}:5", f"{S}:20"}
        new = FULL - {f"{S}:20", f"{S}:7"}          # 5 استُرجعت و7 غابت
        self.assertIn("غابت آياتٌ كانت في الأب", f(old, new, [S], allow_inherited=True))

    def test_no_gain_refused_with_flag(self):
        old = FULL - {f"{S}:5"}
        self.assertIn("لم تزد", f(old, old, [S], allow_inherited=True))


if __name__ == "__main__":
    unittest.main()
