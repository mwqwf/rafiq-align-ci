import copy
import unittest
from tools.index_qa.promote import inherited_drops


class InheritedDropsTest(unittest.TestCase):
    def setUp(self):
        self.sha = "a" * 64
        self.parent = {"riwaya": "qalun", "reciterId": "reader", "entries": [{"ayahId": "107:1"}],
                       "transform": {"op": "drop_surah:24", "reasonCode": "SOURCE_TRUNCATED", "reasonUser": "التسجيل ناقص"}}
        self.idx = copy.deepcopy(self.parent)
        self.idx["transform"].update(op="ctc_surah_splice:107", dropSurah=[24], fromKey="timings/qalun/reader.jz", fromSha256=self.sha)

    def check(self):
        return inherited_drops(self.idx, self.parent, self.sha)

    def test_inherited_absence_keeps_original_user_notice(self):
        self.assertEqual(self.check(), ({"24"}, None))

    def test_no_parent_or_wrong_sha_refuses(self):
        self.assertIsNotNone(inherited_drops(self.idx, None, self.sha)[1])
        self.assertIsNotNone(inherited_drops(self.idx, self.parent, "b" * 64)[1])

    def test_new_or_previously_present_drop_refuses(self):
        self.idx["transform"]["dropSurah"] = [24, 107]
        self.assertIsNotNone(self.check()[1])
        self.idx["transform"]["dropSurah"] = [24]
        self.parent["entries"].append({"ayahId": "24:1"})
        self.assertIsNotNone(self.check()[1])

    def test_wrong_parent_identity_or_key_refuses(self):
        self.idx["transform"]["fromKey"] = "timings/qalun/other.jz"
        self.assertIsNotNone(self.check()[1])
        self.idx["transform"]["fromKey"] = "timings/qalun/reader.jz"
        self.parent["riwaya"] = "hafs"
        self.assertIsNotNone(self.check()[1])

    def test_notice_change_or_missing_notice_refuses(self):
        self.idx["transform"]["reasonUser"] = ""
        self.assertIsNotNone(self.check()[1])
        self.idx["transform"]["reasonUser"] = "التسجيل ناقص"
        self.parent["transform"]["reasonCode"] = ""
        self.assertIsNotNone(self.check()[1])

    def test_losing_existing_ayah_refuses(self):
        self.idx["entries"] = []
        self.assertIsNotNone(self.check()[1])

    def test_invalid_surah_list_refuses(self):
        for value in ([True], [0], [115], [24, 24], "24"):
            self.idx["transform"]["dropSurah"] = value
            self.assertIsNotNone(self.check()[1])


if __name__ == "__main__":
    unittest.main()
