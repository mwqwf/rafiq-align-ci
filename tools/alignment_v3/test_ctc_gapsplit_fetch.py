#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""حارسُ انتقال تنزيل CTC إلى عقدة Archive الموثّقة بعد إخفاق الطريق العام."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ctc_gapsplit as G  # noqa: E402


class _Response:
    headers = {"Content-Length": "3"}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return b"abc"


class Fetch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = os.path.join(self.tmp.name, "a.mp3")

    def tearDown(self):
        self.tmp.cleanup()

    def test_primary_path_does_not_call_archive_node(self):
        with mock.patch.object(G.urllib.request, "urlopen", return_value=_Response()), \
                mock.patch.object(G, "archive_fetch_verified") as fallback:
            G.fetch("https://example.test/a.mp3", self.out)
        self.assertEqual(Path(self.out).read_bytes(), b"abc")
        fallback.assert_not_called()

    def test_archive_node_recovers_after_six_primary_failures(self):
        def verified(_url, dst):
            Path(dst).write_bytes(b"verified")
            return "https://ia.example/item/a.mp3", 8

        with mock.patch.object(G.urllib.request, "urlopen", side_effect=OSError("HTTP 500")) as primary, \
                mock.patch.object(G, "archive_fetch_verified", side_effect=verified) as fallback:
            G.fetch("https://archive.org/download/item/a.mp3", self.out)
        self.assertEqual(primary.call_count, 6)
        fallback.assert_called_once()
        self.assertEqual(Path(self.out).read_bytes(), b"verified")

    def test_failure_remains_failure_without_verified_fallback(self):
        with mock.patch.object(G.urllib.request, "urlopen", side_effect=OSError("HTTP 500")) as primary, \
                mock.patch.object(G, "archive_fetch_verified", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "HTTP 500"):
                G.fetch("https://archive.org/download/item/a.mp3", self.out)
        self.assertEqual(primary.call_count, 6)


if __name__ == "__main__":
    unittest.main()
