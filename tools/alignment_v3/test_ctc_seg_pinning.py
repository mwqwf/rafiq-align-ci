"""🔐 (2026-11-03 · التدقيق الأمني) نموذجُ CTC العامّ لا يُحمَّل إلا بمراجعةٍ وبصمةٍ مثبّتتين،
والتنزيلُ له سقفٌ ومخطّطاتٌ مسموحة. تفشل هذه الاختبارات بلا الإصلاح."""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "alignment"))

import ctc_seg as C  # noqa: E402
import common  # noqa: E402


class PinnedModel(unittest.TestCase):
    def test_unpinned_hub_id_refused(self):
        with self.assertRaises(ValueError):
            C._pinned_source("someone/other-wav2vec2")

    def test_local_dir_passes_through(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(C._pinned_source(d), d)

    def test_default_is_pinned(self):
        rev, sha = C._PINNED[C.MODEL_ID]
        self.assertEqual(len(rev), 40)
        self.assertEqual(len(sha), 64)


class FetchCap(unittest.TestCase):
    def test_scheme_refused(self):
        with self.assertRaises(ValueError):
            common.fetch_retry("ftp://example.invalid/x.mp3", os.devnull, attempts=1)

    def test_size_cap(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "a.bin")
            with open(src, "wb") as f:
                f.write(b"\0" * 5000)
            dst = os.path.join(d, "b.bin")
            with self.assertRaises(IOError):
                common.fetch_retry("file://" + src, dst, attempts=1, max_bytes=1000)
            self.assertFalse(os.path.exists(dst))
            common.fetch_retry("file://" + src, dst, attempts=1)
            self.assertEqual(os.path.getsize(dst), 5000)


if __name__ == "__main__":
    unittest.main()
