"""طريقُ عقدة التخزين في archive.org (‏`archive_node` · fixV 2026-10-05 · فخفاخ 5bad920f).

    python -m unittest tools/index_qa/test_archive_node.py

يُختبر بطرفيه: الروابطُ تُبنى من بيانات البند كما هي، **ولا يُقبل** ما لا يطابق حجمَ البند
وبصمةَ md5 الناشر — ولا ما لم يُعلن له حجمٌ أو بصمة (‏فلا بايتاتٌ بلا شاهد).
"""
from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import archive_node as A                                         # noqa: E402

META = {"dir": "/7/items/my--item", "server": "ia800.us.archive.org",
        "d1": "ia801502.us.archive.org", "d2": "ia601502.us.archive.org",
        "files": [{"name": "033Al-ahzeb.mp3", "size": "12011310", "md5": "ABCDEF0123456789abcdef0123456789"},
                  {"name": "nosize.mp3", "md5": "a" * 32},
                  {"name": "nomd5.mp3", "size": "12"}]}


class Parse(unittest.TestCase):
    def test_download_url(self):
        self.assertEqual(A.parse_download_url("https://archive.org/download/my--item/033Al-ahzeb.mp3"),
                         ("my--item", "033Al-ahzeb.mp3"))

    def test_percent_decoded(self):
        self.assertEqual(A.parse_download_url("https://archive.org/download/it/a%20b.mp3")[1], "a b.mp3")

    def test_other_hosts_ignored(self):
        for u in ("https://server16.mp3quran.net/x/001.mp3", "https://archive.org/details/it",
                  "", None, "ftp://archive.org/download/it/f.mp3"):
            self.assertIsNone(A.parse_download_url(u))


class Candidates(unittest.TestCase):
    def test_order_and_quoting(self):
        urls = A.node_candidates(META, "my--item", "033Al-ahzeb.mp3")
        self.assertEqual(urls, ["https://ia801502.us.archive.org/7/items/my--item/033Al-ahzeb.mp3",
                                "https://ia601502.us.archive.org/7/items/my--item/033Al-ahzeb.mp3",
                                "https://ia800.us.archive.org/7/items/my--item/033Al-ahzeb.mp3"])

    def test_no_dir_no_candidates(self):
        self.assertEqual(A.node_candidates({"server": "x", "dir": ""}, "i", "f.mp3"), [])
        self.assertEqual(A.node_candidates(None, "i", "f.mp3"), [])

    def test_expected_size_md5(self):
        self.assertEqual(A.expected_size_md5(META, "033Al-ahzeb.mp3"),
                         (12011310, "abcdef0123456789abcdef0123456789"))
        self.assertEqual(A.expected_size_md5(META, "nosize.mp3")[0], None)
        self.assertEqual(A.expected_size_md5(META, "nomd5.mp3")[1], None)
        self.assertEqual(A.expected_size_md5(META, "ghost.mp3"), (None, None))


class Verify(unittest.TestCase):
    def test_match_required(self):
        self.assertTrue(A.matches(10, "ab", 10, "ab"))
        self.assertTrue(A.matches(10, "AB", 10, "ab"))

    def test_size_or_md5_mismatch_refused(self):
        self.assertFalse(A.matches(9, "ab", 10, "ab"))
        self.assertFalse(A.matches(10, "cd", 10, "ab"))

    def test_unknown_expectation_refused(self):
        """بايتاتٌ بلا حجمٍ أو بصمةٍ معلنَين لا تُقبل من هذا الطريق."""
        self.assertFalse(A.matches(10, "ab", None, "ab"))
        self.assertFalse(A.matches(10, "ab", 10, None))
        self.assertFalse(A.matches(10, "ab", 0, "ab"))


class FetchGuards(unittest.TestCase):
    """`fetch_verified` لا يكتب شيئاً لرابطٍ ليس من archive.org ولا لبندٍ بلا شاهد."""
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.out = os.path.join(self.tmp, "a.mp3")
        self._meta = A.metadata

    def tearDown(self):
        A.metadata = self._meta

    def test_non_archive_url(self):
        A.metadata = lambda *a, **k: META
        self.assertIsNone(A.fetch_verified("https://server16.mp3quran.net/x/001.mp3", self.out))
        self.assertFalse(os.path.exists(self.out))

    def test_item_without_md5(self):
        A.metadata = lambda *a, **k: META
        self.assertIsNone(A.fetch_verified("https://archive.org/download/my--item/nomd5.mp3", self.out))
        self.assertFalse(os.path.exists(self.out))

    def test_md5_is_publisher_digest_of_bytes(self):
        body = b"abc" * 7
        self.assertTrue(A.matches(len(body), hashlib.md5(body).hexdigest(),  # noqa: S324
                                  len(body), hashlib.md5(body).hexdigest()))  # noqa: S324


if __name__ == "__main__":
    unittest.main()
