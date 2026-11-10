import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audio_sha_update as u
import graft_surahs as g

C = g.ayah_counts()


def idx(sha, surahs=(55, 56)):
    ents = [{"ayahId": f"{s}:{a}", "fileRef": f"f{s}"} for s in surahs for a in range(1, C[s - 1] + 1)]
    return {"entries": ents, "audioSha256": sha}


def old():
    return [f"old{i}" for i in range(1, 115)]


class T(unittest.TestCase):
    recs = {55: {"fileRef": "f55", "sha256": "NEW55"}, 56: {"fileRef": "f56", "sha256": "NEW56"}}

    def test_whole_surah_rewindowed_updates(self):
        i = idx(old())
        full = u.full_surahs([55], "55:1-78", C)
        self.assertEqual(full, [55])
        self.assertEqual(u.update(i, self.recs, full, log=lambda *_: None), [55])
        self.assertEqual(i["audioSha256"][54], "NEW55")
        self.assertEqual(i["audioSha256"][55], "old56")

    def test_whole_surah_in_two_ranges_updates(self):
        self.assertEqual(u.full_surahs([55], "55:1-40,55:41-78", C), [55])

    def test_partial_rewindow_does_not_update(self):
        i = idx(old())
        full = u.full_surahs([55], "55:1-70", C)
        self.assertEqual(full, [])
        u.update(i, self.recs, full, log=lambda *_: None)
        self.assertEqual(i["audioSha256"][54], "old55")

    def test_gap_in_ranges_is_partial(self):
        self.assertEqual(u.full_surahs([55], "55:1-30,55:40-78", C), [])

    def test_no_rewindow_is_whole(self):
        self.assertEqual(u.full_surahs([55, 56], "55:1-70", C), [56])

    def test_compact_layout(self):
        i = idx(["a", "b"])
        self.assertEqual(u.update(i, self.recs, [56], log=lambda *_: None), [56])
        self.assertEqual(i["audioSha256"], ["a", "NEW56"])

    def test_unknown_layout_untouched(self):
        i = idx(["a", "b", "c"])
        self.assertEqual(u.update(i, self.recs, [55], log=lambda *_: None), [])
        self.assertEqual(i["audioSha256"], ["a", "b", "c"])

    def test_fileref_mismatch_rejected(self):
        with self.assertRaises(SystemExit):
            u.update(idx(old()), {55: {"fileRef": "other", "sha256": "X"}}, [55], log=lambda *_: None)


if __name__ == "__main__":
    unittest.main()
