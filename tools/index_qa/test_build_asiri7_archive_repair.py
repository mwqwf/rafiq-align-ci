"""Offline guards for the Asiri Araf evidence bundle; no network or models."""
import copy
import unittest

import build_asiri7_archive_repair as B


class EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.metadata = B.checked(B.METADATA)
        cls.primary = B.checked(B.PRIMARY)
        cls.independent = B.checked(B.INDEPENDENT)
        cls.comparison = B.checked(B.COMPARISON)
        cls.targeted = B.checked(B.TARGETED)
        cls.expanded = B.checked(B.EXPANDED)

    def validate(self, **changes):
        values = {name: copy.deepcopy(getattr(self, name)) for name in
                  ("primary", "independent", "comparison", "targeted", "expanded", "metadata")}
        values.update(changes)
        return B.validate_evidence(**values)

    def test_actual_evidence_passes_and_keeps_low_confidence(self):
        alignment = self.validate()
        self.assertEqual(len(alignment["entries"]), 206)
        self.assertEqual([alignment["entries"][n - 1]["conf"] for n in (13, 48, 54, 131, 188)],
                         [.44, .44, .368, .446, .348])

    def test_full_alignment_disagreement_fails(self):
        independent = copy.deepcopy(self.independent)
        independent["alignment"]["entries"][47]["endMs"] -= 1
        with self.assertRaises(ValueError):
            self.validate(independent=independent)

    def test_rejected_short_window_must_remain_rejected(self):
        targeted = copy.deepcopy(self.targeted)
        targeted["measurementComplete"] = True
        with self.assertRaises(ValueError):
            self.validate(targeted=targeted)

    def test_both_expanded_windows_are_required(self):
        expanded = copy.deepcopy(self.expanded)
        expanded["alignment"]["numericWindowAudit"].pop()
        with self.assertRaises(ValueError):
            self.validate(expanded=expanded)

    def test_expanded_boundary_disagreement_fails(self):
        expanded = copy.deepcopy(self.expanded)
        expanded["expandedAyah48Comparison"][0]["fullEndDeltaMs"] = 1
        with self.assertRaises(ValueError):
            self.validate(expanded=expanded)

    def test_missing_middle_witness_fails(self):
        comparison = copy.deepcopy(self.comparison)
        comparison["witnesses"] = [w for w in comparison["witnesses"]
                                   if w["name"] != "middle-7:123-159"]
        with self.assertRaises(ValueError):
            self.validate(comparison=comparison)


if __name__ == "__main__":
    unittest.main()
