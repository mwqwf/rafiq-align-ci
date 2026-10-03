import unittest
from tools.index_qa.drop_surah import pruned_surah_maps


class PrunedSurahMapsTest(unittest.TestCase):
    """السورةُ المُسقطةُ تُحذف من خرائط السور، والحاضرةُ يبقى سجلُّها فيبقى إحصاؤها لازماً."""

    def setUp(self):
        self.idx = {"engineVersion": "align-0.2",
                    "engineBySurah": {"41": "ctc-heardmap-1", "37": "ctc-gapsplit-1"},
                    "sourceBySurah": {"41": "alt"},
                    "alignmentModelBySurah": {"37": {"id": "m"}},
                    "dualFixEvidenceBySurah": {"41": {}}}

    def test_dropped_surah_leaves_every_map(self):
        out = pruned_surah_maps(self.idx, [41])
        self.assertEqual(out["engineBySurah"], {"37": "ctc-gapsplit-1"})
        self.assertEqual(out["sourceBySurah"], {})
        self.assertEqual(out["dualFixEvidenceBySurah"], {})
        self.assertNotIn("alignmentModelBySurah", out)   # لم يتغيّر فلا يُكتب

    def test_present_surah_keeps_its_record(self):
        out = pruned_surah_maps(self.idx, [3])
        self.assertEqual(out, {})
        self.assertIn("37", pruned_surah_maps(self.idx, [41, 3])["engineBySurah"])

    def test_source_not_mutated(self):
        pruned_surah_maps(self.idx, [41])
        self.assertIn("41", self.idx["engineBySurah"])


if __name__ == "__main__":
    unittest.main()
