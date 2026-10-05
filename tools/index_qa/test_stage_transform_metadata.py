"""صدق وصف التحويل لا يعتمد على بقاء عدد المداخل كما كان."""
import copy
import unittest

from tools.index_qa.stage_transform import entry_change_counts, staged_transform_metadata


class StageMetadataTests(unittest.TestCase):
    def test_recovered_ayahs_are_counted_and_local_flag_is_not_inherited(self):
        old = [{"ayahId": "63:1", "startMs": 0, "endMs": 1000}]
        new = old + [{"ayahId": "63:2", "startMs": 1000, "endMs": 2000},
                     {"ayahId": "63:3", "startMs": 2000, "endMs": 3000}]
        prior = {"note": "مرشح محلي غير منشور", "unpublishedLocalCandidate": True,
                 "provenance": {"parentTransform": {"reasonCode": "SOURCE_TRUNCATED"}},
                 "sourceRepair": {"surah": 63}, "unknown": {"retained": True}}
        saved = copy.deepcopy(prior)
        metadata = staged_transform_metadata(prior, *entry_change_counts(old, new))
        self.assertIn("حدود متغيرة في 0", metadata["note"])
        self.assertIn("مداخل مضافة 2", metadata["note"])
        self.assertIn("مداخل محذوفة 0", metadata["note"])
        self.assertIn("ليس حكم جودة", metadata["note"])
        self.assertNotIn("unpublishedLocalCandidate", metadata)
        self.assertEqual(prior, saved)
        for key in ("provenance", "sourceRepair", "unknown"):
            self.assertEqual(metadata[key], prior[key])

    def test_timing_only_describes_zero_added_or_removed(self):
        old = [{"ayahId": "63:1", "startMs": 0, "endMs": 1000}]
        new = [{"ayahId": "63:1", "startMs": 30, "endMs": 990}]
        metadata = staged_transform_metadata("أثر قديم", *entry_change_counts(old, new))
        self.assertIn("حدود متغيرة في 1", metadata["note"])
        self.assertIn("مداخل مضافة 0", metadata["note"])
        self.assertIn("مداخل محذوفة 0", metadata["note"])
        self.assertEqual(metadata["opAsGiven"], "أثر قديم")


if __name__ == "__main__":
    unittest.main()
