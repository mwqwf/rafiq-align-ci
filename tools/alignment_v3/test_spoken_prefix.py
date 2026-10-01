import copy
import unittest

from tools.alignment_v3.ctc_spoken_prefix import insert_first


class PrefixRestoreTest(unittest.TestCase):
    def setUp(self):
        self.sha = "a" * 64
        self.idx = {"audioSha256": [self.sha] * 114, "entries": [
            {"ayahId": "3:2", "fileRef": "https://example.test/003.mp3", "startMs": 10000, "endMs": 20000},
            {"ayahId": "3:3", "fileRef": "https://example.test/003.mp3", "startMs": 20000, "endMs": 30000}]}
        self.proof = {"firstConf": .8, "anchorConf": .8, "anchorStartMs": 10100,
                      "firstStartMs": 3000, "snapped": True}

    def test_preserves_anchor_and_does_not_mutate_parent(self):
        old = copy.deepcopy(self.idx)
        row = insert_first(self.idx, 3, self.sha, self.proof)
        self.assertEqual(row["endMs"], self.idx["entries"][0]["startMs"])
        self.assertEqual(self.idx, old)
        self.proof["snapped"] = False
        row = insert_first(self.idx, 3, self.sha, self.proof)
        self.assertEqual(row["conf"], .74)
        self.assertEqual(row["confBand"], "MED")

    def test_rejects_wrong_audio_anchor_low_confidence_and_impossible_interval(self):
        for key, val in [("anchorStartMs", 12000), ("anchorConf", .44),
                         ("firstConf", .44), ("firstStartMs", 10001)]:
            with self.subTest(key=key):
                proof = dict(self.proof, **{key: val})
                with self.assertRaises(ValueError):
                    insert_first(self.idx, 3, self.sha, proof)
        with self.assertRaises(ValueError):
            insert_first(self.idx, 3, "b" * 64, self.proof)
        self.idx["entries"].append({"ayahId": "3:1"})
        with self.assertRaises(ValueError):
            insert_first(self.idx, 3, self.sha, self.proof)


if __name__ == "__main__":
    unittest.main()
