#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""توريثُ الحجب الوسطيّ لا يُبقي آيةً استُرجعت معلَنةً غائبة (‏noah_warsh 5:20 و5:36 · ctc_gapsplit) وحارسُ promote يردّها."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import promote                                                        # noqa: E402
import stage_transform as st                                          # noqa: E402

GAPS5 = [12, 20, 36, 48, 72, 117]


def cand(entries_of_5, absent=GAPS5, extra_gaps=None):
    ev = {f"5:{a}": {"method": "ctc_window", "detail": f"قياس {a}"} for a in absent}
    gaps = {"5": {"absent": list(absent), "reason": "source_truncated", "evidence": ev}}
    gaps.update(extra_gaps or {})
    return {
        "entries": [{"ayahId": f"5:{a}", "startMs": a, "endMs": a + 1} for a in entries_of_5],
        "transform": {"op": "ctc_gapsplit:5|declare_gap:5", "truncatedGaps": gaps,
                      "declarations": {"5": {"op": "declare_gap", "reasonCode": "SOURCE_TRUNCATED"}},
                      "reasonCode": "SOURCE_TRUNCATED", "reasonUser": "س",
                      "gapAyahs": 6, "droppedEntries": 6},
    }


ALL5 = [a for a in range(1, 121)]


class Prune(unittest.TestCase):
    def test_recovered_ayahs_removed_rest_kept_verbatim(self):
        out = cand([a for a in ALL5 if a not in (12, 48, 72, 117)])      # 20 و36 استُرجعتا
        ev0 = copy.deepcopy(out["transform"]["truncatedGaps"]["5"]["evidence"])
        got = st.prune_recovered_gaps(out)
        self.assertEqual(got, {"5": [20, 36]})
        rec = out["transform"]["truncatedGaps"]["5"]
        self.assertEqual(rec["absent"], [12, 48, 72, 117])
        self.assertEqual(rec["reason"], "source_truncated")
        for a in (12, 48, 72, 117):
            self.assertEqual(rec["evidence"][f"5:{a}"], ev0[f"5:{a}"])
        self.assertNotIn("5:20", rec["evidence"])
        self.assertEqual(out["transform"]["gapAyahs"], 4)
        self.assertIn("5", out["transform"]["declarations"])
        self.assertIsNone(promote.gap_declared_present_error(out))

    def test_empty_declaration_removed(self):
        out = cand(ALL5, absent=[20, 36])
        out["transform"]["gapAyahs"] = 2
        st.prune_recovered_gaps(out)
        tr = out["transform"]
        self.assertNotIn("truncatedGaps", tr)
        self.assertNotIn("5", tr["declarations"])
        self.assertNotIn("declare_gap", tr["op"])
        self.assertEqual(tr["gapAyahs"], 0)

    def test_untouched_when_nothing_recovered(self):
        out = cand([a for a in ALL5 if a not in GAPS5])
        before = copy.deepcopy(out)
        self.assertEqual(st.prune_recovered_gaps(out), {})
        self.assertEqual(out, before)


class Guard(unittest.TestCase):
    def test_present_ayah_declared_absent_refused(self):
        out = cand([a for a in ALL5 if a not in (12, 48, 72, 117)])
        why = promote.gap_declared_present_error(out)
        self.assertIn("⛔", why)
        self.assertIn("5:20", why)
        self.assertIn("5:36", why)
        self.assertNotIn("5:12", why)

    def test_sound_declaration_passes(self):
        out = cand([a for a in ALL5 if a not in GAPS5])
        self.assertIsNone(promote.gap_declared_present_error(out))

    def test_index_gate_wires_guard(self):
        out = cand([a for a in ALL5 if a not in (12, 48, 72, 117)])
        out.update({"refineVersion": "x", "missing": {"count": 4, "ids": []}})
        self.assertIn("حاضرةً", promote.index_gate(out) or "")


class Mutation(unittest.TestCase):
    def test_disabled_pruning_fails_the_check(self):
        out = cand([a for a in ALL5 if a not in (12, 48, 72, 117)])
        orig = st.prune_recovered_gaps
        try:
            st.prune_recovered_gaps = lambda o: {}                    # طفرةٌ تعطّل الحذف
            st.prune_recovered_gaps(out)
            self.assertIsNotNone(promote.gap_declared_present_error(out))   # فيسقط الاختبار الإيجابيّ أعلاه
        finally:
            st.prune_recovered_gaps = orig
        st.prune_recovered_gaps(out)
        self.assertIsNone(promote.gap_declared_present_error(out))


if __name__ == "__main__":
    unittest.main()
