# -*- coding: utf-8 -*-
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import source_drift_report as R  # noqa: E402


def row(rid, s, etag, mag=1.0):
    return {"riwaya": "hafs", "reciter": rid, "surah": s, "etag": etag, "flags": ["endBeyondFile"],
            "magnitudeSec": mag, "fileSec": 1, "lastEndSec": 2, "lastModified": "x"}


class T(unittest.TestCase):
    def test_known_same_etag_is_silent(self):
        new, old = R.split_new([row("a", 1, "abcdef0123456789")], {"hafs/a/1": "abcdef012345"})
        self.assertEqual((len(new), old), (0, 1))

    def test_changed_etag_or_unknown_key_is_new_sorted_by_magnitude(self):
        rows = [row("a", 1, "zzzzzzzzzzzzzz", 2.0), row("b", 2, "q", 9.0), row("c", 3, "k", 5.0)]
        new, old = R.split_new(rows, {"hafs/a/1": "abcdef012345", "hafs/c/3": "k"})
        self.assertEqual([r["reciter"] for r in new], ["b", "a"])
        self.assertEqual(old, 1)

    def test_render_arabic_and_no_block_statement(self):
        txt = R.render([row("a", 1, "e")], 0, 2, [])
        self.assertIn("لا حجبَ", txt)
        self.assertIn("hafs/a", txt)


if __name__ == "__main__":
    unittest.main()
