#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`stage_transform.parent_coded_approved` — إعفاءُ العتبة الموروث من صفّ موافقة الأصل (2026-11-10).

لا يُعفى إلا ما اجتمع فيه: صفُّ مفتاحِ الأصل يسمّيه · محجوبٌ في الأصل برمزٍ غير البتر · محجوبٌ في المرشّح بالرمز نفسه."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import promote  # noqa: E402
from stage_transform import parent_coded_approved as f  # noqa: E402

PSHA = "143e13dd" + "0" * 56
KEY = "timings-staging/qalun/akri_qalun.143e13dd.jz"


def tr(surahs, code="TIMING_UNDER_REPAIR"):
    return {"op": "drop_surah:" + ",".join(map(str, surahs)), "reasonCode": code,
            "reasonUser": "قيد الإصلاح", "dropSurah": list(surahs)}


P_IDX = {"riwaya": "qalun", "reciterId": "akri_qalun", "transform": tr([10, 37])}


class ParentApproval(unittest.TestCase):
    def test_inherited_same_code_excused(self):
        idx = {"transform": tr([10, 37])}
        self.assertEqual(f(P_IDX, idx, "timings/qalun/akri_qalun.jz", PSHA, {KEY: frozenset({10, 37})}),
                         frozenset({10, 37}))

    def test_no_parent_row_nothing(self):
        idx = {"transform": tr([10, 37])}
        self.assertEqual(f(P_IDX, idx, "timings/qalun/akri_qalun.jz", PSHA, {}), frozenset())

    def test_other_key_row_ignored(self):
        idx = {"transform": tr([10, 37])}
        other = "timings-staging/qalun/akri_qalun.deadbeef.jz"
        self.assertEqual(f(P_IDX, idx, "timings/qalun/akri_qalun.jz", PSHA, {other: frozenset({10, 37})}),
                         frozenset())

    def test_new_hide_not_excused(self):
        idx = {"transform": tr([10, 37, 55])}
        got = f(P_IDX, idx, "timings/qalun/akri_qalun.jz", PSHA, {KEY: frozenset({10, 37, 55})})
        self.assertEqual(got, frozenset({10, 37}))

    def test_changed_code_not_excused(self):
        idx = {"transform": tr([10, 37], code="OTHER")}
        self.assertEqual(f(P_IDX, idx, "timings/qalun/akri_qalun.jz", PSHA, {KEY: frozenset({10, 37})}),
                         frozenset())

    def test_source_truncated_never_via_row(self):
        p = dict(P_IDX, transform=tr([10], code="SOURCE_TRUNCATED"))
        idx = {"transform": tr([10], code="SOURCE_TRUNCATED")}
        self.assertEqual(f(p, idx, "timings/qalun/akri_qalun.jz", PSHA, {KEY: frozenset({10})}), frozenset())

    def test_surah_restored_in_candidate_not_excused(self):
        idx = {"transform": tr([37])}
        self.assertEqual(f(P_IDX, idx, "timings/qalun/akri_qalun.jz", PSHA, {KEY: frozenset({10, 37})}),
                         frozenset({37}))

    def test_staging_parent_uses_its_own_key(self):
        idx = {"transform": tr([10, 37])}
        self.assertEqual(f(P_IDX, idx, KEY, "ffffffff" + "0" * 56, {KEY: frozenset({10})}), frozenset({10}))

    def test_gate_uses_only_inherited(self):
        """التكامل: حجبٌ جديد بلا صفٍّ لمفتاح المرشّح يبقى محسوباً على العتبة."""
        entries = [{"ayahId": f"{s}:1"} for s in range(1, 115) if s not in (10, 37, 55)]
        idx = {"refineVersion": 1, "ayahCount": 6236, "entries": entries,
               "missing": {"count": 6236 - len(entries)}, "transform": tr([10, 37, 55])}
        appr = f(P_IDX, idx, "timings/qalun/akri_qalun.jz", PSHA, {KEY: frozenset({10, 37, 55})})
        self.assertNotIn(55, appr)
        self.assertIsNotNone(promote.index_gate(idx, coded_approved=appr, inherited_rows=[]))


if __name__ == "__main__":
    unittest.main()
