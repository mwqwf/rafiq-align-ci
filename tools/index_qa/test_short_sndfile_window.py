#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نافذةُ libsndfile الناقصة بلا استثناء (‏إطارٌ تالفٌ وسط الملفّ · mhsny/006 · fixU 2026-10-04)
تُحال إلى ffmpeg بقواعد رفضه، ولا تُفرَّغ فارغةً فتسقط بـ«array of sample points is empty»."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import run as R  # noqa: E402


class _Model:
    def transcribe(self, y):
        return [SimpleNamespace(text=f"n={len(y)}")]


class ShortSndfileWindowTest(unittest.TestCase):
    def _run(self, sf_rows, ff=None):
        job = {"id": "6:14", "url": "u", "startMs": 1000, "endMs": 3000}
        sf_mod = mock.MagicMock()
        sf_mod.info.return_value = SimpleNamespace(samplerate=16000)
        sf_mod.read.return_value = (np.zeros((sf_rows, 1), dtype="float32"), 16000)
        with mock.patch.dict(sys.modules, {"soundfile": sf_mod}), \
                mock.patch.object(R, "_local_model", return_value=_Model()), \
                mock.patch.object(R, "_prefetch"), \
                mock.patch.object(R, "_range_pcm", return_value=None), \
                mock.patch.object(R, "_local_audio", return_value="a.mp3"), \
                mock.patch.object(R, "_local_is_cbr", return_value=True), \
                mock.patch.object(R, "_ffmpeg_window_pcm", side_effect=ff) as fw:
            res, errs = R.local_run([job])
        return res, errs, fw

    def test_empty_libsndfile_window_falls_back_to_ffmpeg(self):
        res, errs, fw = self._run(0, ff=lambda *a, **k: (np.ones(32000, dtype="float32"), 16000))
        self.assertTrue(fw.called)
        self.assertEqual(errs, {})
        self.assertEqual(res["6:14"]["text"], "n=32000")

    def test_short_window_falls_back_and_ffmpeg_refusal_stays_an_error(self):
        def refuse(*a, **k):
            raise RuntimeError("ffmpeg أبلغ خطأ فك مع rc=0: Invalid data")
        res, errs, fw = self._run(5000, ff=refuse)
        self.assertTrue(fw.called)
        self.assertIn("6:14", errs)
        self.assertNotIn("6:14", res)

    def test_full_window_does_not_touch_ffmpeg(self):
        res, errs, fw = self._run(32000)
        self.assertFalse(fw.called)
        self.assertEqual(res["6:14"]["text"], "n=32000")


if __name__ == "__main__":
    unittest.main()
