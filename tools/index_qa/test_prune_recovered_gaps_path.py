#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مسارُ ctc_splice بوضع window (‏التشغيلة 44688704348): المرشّحُ يصل إلى stage_transform بإعلان الأب الستّ ومعه مدخلا 5:20 و5:36.
الحذفُ يجب أن يسبق index_gate لا أن يلحقه، وإلا ردّ الحارسُ المرشّحَ قبل بلوغ الحذف."""
import copy
import inspect
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import promote                                                        # noqa: E402
import stage_transform as st                                          # noqa: E402

GAPS = [12, 20, 36, 48, 72, 117]


def patched_candidate():
    """ما يحمله patched.jz: ترويسةُ الأب كاملةً + مداخلُ الأب + 5:20 و5:36 المضافتان."""
    ents = [{"ayahId": f"5:{a}", "startMs": a, "endMs": a + 1}
            for a in range(1, 121) if a not in GAPS or a in (20, 36)]
    ev = {f"5:{a}": {"method": "ctc_window", "detail": f"قياس {a}"} for a in GAPS}
    return {"refineVersion": "x", "entries": ents, "missing": {"count": 4, "ids": []},
            "transform": {"op": "ctc_gapsplit:5|declare_gap:5", "gapAyahs": 6,
                          "truncatedGaps": {"5": {"absent": list(GAPS), "reason": "source_truncated", "evidence": ev}},
                          "declarations": {"5": {"op": "declare_gap", "reasonCode": "SOURCE_TRUNCATED"}}}}


class PathOrder(unittest.TestCase):
    def test_candidate_as_it_arrives_is_refused_by_guard(self):
        self.assertIn("5:20", promote.gap_declared_present_error(patched_candidate()))

    def test_pruning_the_loaded_candidate_gives_four_ayahs(self):
        idx = patched_candidate()
        ev0 = copy.deepcopy(idx["transform"]["truncatedGaps"]["5"]["evidence"])
        st.prune_recovered_gaps(idx)
        rec = idx["transform"]["truncatedGaps"]["5"]
        self.assertEqual(rec["absent"], [12, 48, 72, 117])
        self.assertEqual({k: rec["evidence"][k] for k in rec["evidence"]},
                         {f"5:{a}": ev0[f"5:{a}"] for a in (12, 48, 72, 117)})
        self.assertIsNone(promote.gap_declared_present_error(idx))
        self.assertNotIn("حاضرةً", promote.index_gate(idx) or "")

    def test_main_prunes_loaded_idx_before_index_gate(self):
        src = inspect.getsource(st.main)
        i_prune = src.index("prune_recovered_gaps(idx)")
        i_gate = src.index("promote.index_gate(idx")
        self.assertLess(i_prune, i_gate)
        self.assertIsNone(re.search(r"index_gate\(idx[^\n]*\n[^\n]*\n[^\n]*prune_recovered_gaps\(idx\)", src))


if __name__ == "__main__":
    unittest.main()
