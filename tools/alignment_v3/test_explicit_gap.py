import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ctc_gapsplit as G


class ExplicitGap(unittest.TestCase):
    def setUp(self):
        self.entries = {1: {"startMs": 5020, "endMs": 27200},
                        4: {"startMs": 28280, "endMs": 44560}}

    def test_separated_gap_requires_explicit_request(self):
        # A 1080 ms silence does not prove that ayahs 2 and 3 are absent from the audio.
        self.assertNotIn(("gap", 2, 3), G.plan_splits(self.entries, 227, lambda _: "", 1))
        self.assertEqual(G.explicit_gap(self.entries, 227, 2, 3), ("gap", 2, 3))

    def test_present_ayah_cannot_be_replaced_as_a_missing_ayah(self):
        self.entries[2] = {"startMs": 20000, "endMs": 24000}
        with self.assertRaises(ValueError):
            G.explicit_gap(self.entries, 227, 2, 3)

    def test_missing_anchor_and_out_of_range_are_refused(self):
        for b0, b1 in [(1, 3), (2, 227), (3, 2), (2, 4)]:
            with self.subTest(bounds=(b0, b1)), self.assertRaises(ValueError):
                G.explicit_gap(self.entries, 227, b0, b1)


if __name__ == "__main__":
    unittest.main()
