"""Offline mutation guards for the Fakhfakh Sad candidate evidence."""
import copy
import unittest

import build_fakhfakh38_archive_repair as B


class EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audit = B.checked(B.AUDIT)
        cls.primary = B.checked(B.PRIMARY)
        cls.independent = B.checked(B.INDEPENDENT)

    def validate(self, **changes):
        values = {name: copy.deepcopy(getattr(self, name))
                  for name in ("primary", "independent", "audit")}
        values.update(changes)
        return B.validate_evidence(**values)

    def test_actual_evidence_passes(self):
        alignment = self.validate()
        self.assertEqual(len(alignment["entries"]), 88)
        self.assertEqual((alignment["entries"][0]["startMs"],
                          alignment["entries"][-1]["endMs"]), (6104, 972313))

    def test_full_alignment_disagreement_fails(self):
        independent = copy.deepcopy(self.independent)
        independent["alignment"]["entries"][-1]["endMs"] -= 1
        with self.assertRaises(ValueError):
            self.validate(independent=independent)

    def test_ending_boundary_witness_is_required(self):
        independent = copy.deepcopy(self.independent)
        independent["boundaryComparisons"].pop()
        with self.assertRaises(ValueError):
            self.validate(independent=independent)

    def test_middle_witness_is_required(self):
        independent = copy.deepcopy(self.independent)
        independent["openingMiddleEndingComparison"] = [
            row for row in independent["openingMiddleEndingComparison"]
            if row["witness"] != "middle-40-48"
        ]
        with self.assertRaises(ValueError):
            self.validate(independent=independent)

    def test_publisher_pcm_equality_is_required(self):
        audit = copy.deepcopy(self.audit)
        audit["comparisons"]["archive2025EqualsPublisherDecodedMono16k"] = False
        with self.assertRaises(ValueError):
            self.validate(audit=audit)

    def test_production_performance_match_is_required(self):
        audit = copy.deepcopy(self.audit)
        audit["comparisons"]["productionVersusArchive2025Mono8kCrossCorrelation"]["windows"][2]["correlation"] = .95
        with self.assertRaises(ValueError):
            self.validate(audit=audit)


if __name__ == "__main__":
    unittest.main()
