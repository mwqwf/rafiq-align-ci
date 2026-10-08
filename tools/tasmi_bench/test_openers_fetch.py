#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""حارس انتقال فحص المطالع إلى عقدة Archive الموثّقة بعد إخفاق الطريق العام."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import openers_scan as O  # noqa: E402


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return b"a" * 40000


class FetchHead(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = os.path.join(self.tmp.name, "a.mp3")

    def tearDown(self):
        self.tmp.cleanup()

    def test_primary_path_does_not_call_archive_node(self):
        with mock.patch.object(O.urllib.request, "urlopen", return_value=_Response()), \
                mock.patch.object(O, "archive_fetch_verified") as fallback:
            self.assertEqual(O.fetch_head("https://example.test/a.mp3", self.out), self.out)
        self.assertEqual(Path(self.out).stat().st_size, 40000)
        fallback.assert_not_called()

    def test_archive_node_recovers_after_three_primary_failures(self):
        def verified(_url, dst):
            Path(dst).write_bytes(b"verified")
            return "https://ia.example/item/a.mp3", 8

        with mock.patch.object(O.urllib.request, "urlopen", side_effect=OSError("HTTP 500")) as primary, \
                mock.patch.object(O.time, "sleep"), \
                mock.patch.object(O, "archive_fetch_verified", side_effect=verified) as fallback:
            self.assertEqual(
                O.fetch_head("https://archive.org/download/item/a.mp3", self.out), self.out)
        self.assertEqual(primary.call_count, 3)
        fallback.assert_called_once()
        self.assertEqual(Path(self.out).read_bytes(), b"verified")

    def test_failure_remains_failure_without_verified_fallback(self):
        with mock.patch.object(O.urllib.request, "urlopen", side_effect=OSError("HTTP 500")) as primary, \
                mock.patch.object(O.time, "sleep"), \
                mock.patch.object(O, "archive_fetch_verified", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "HTTP 500"):
                O.fetch_head("https://archive.org/download/item/a.mp3", self.out)
        self.assertEqual(primary.call_count, 3)


if __name__ == "__main__":
    unittest.main()
