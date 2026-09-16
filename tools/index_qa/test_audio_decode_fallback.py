#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختباراتٌ نقية لمسار تعافي فكّ MP3؛ بلا شبكة ولا صوت قرآني."""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import run as R  # noqa: E402


class AudioDecodeFallbackTest(unittest.TestCase):
    def test_ffmpeg_window_preserves_requested_coordinates(self):
        pcm = np.linspace(-0.5, 0.5, 8000, dtype="<f4")
        done = subprocess.CompletedProcess([], 0, stdout=pcm.tobytes(), stderr=b"")
        with mock.patch.object(R.subprocess, "run", return_value=done) as call:
            got, rate = R._ffmpeg_window_pcm("broken.mp3", 1250, 1750)
        self.assertEqual(rate, 16000)
        np.testing.assert_array_equal(got, pcm)
        cmd = call.call_args.args[0]
        self.assertEqual(cmd[cmd.index("-ss") + 1], "1.250")
        self.assertEqual(cmd[cmd.index("-t") + 1], "0.500")

    def test_ffmpeg_failure_remains_an_error(self):
        done = subprocess.CompletedProcess([], 1, stdout=b"", stderr=b"decode failed")
        with mock.patch.object(R.subprocess, "run", return_value=done):
            with self.assertRaisesRegex(RuntimeError, "decode failed"):
                R._ffmpeg_window_pcm("broken.mp3", 0, 1000)

    def test_local_run_uses_fallback_only_after_soundfile_failure(self):
        pcm = np.ones(8000, dtype="float32")
        model = SimpleNamespace(transcribe=lambda _: [SimpleNamespace(text="ok")])
        job = {"id": "F|52:44", "url": "https://example/052.mp3",
               "startMs": 1000, "endMs": 1500}
        fake_sf = SimpleNamespace(info=mock.Mock(side_effect=RuntimeError("libsndfile")))
        with (mock.patch.dict(sys.modules, {"soundfile": fake_sf}),
              mock.patch.object(R, "_local_model", return_value=model),
              mock.patch.object(R, "_prefetch"),
              mock.patch.object(R, "_range_pcm", return_value=None),
              mock.patch.object(R, "_local_audio", return_value="broken.mp3"),
              mock.patch.object(R, "_ffmpeg_window_pcm", return_value=(pcm, 16000)) as fallback):
            result, errors = R.local_run([job])
        self.assertEqual(errors, {})
        self.assertEqual(result[job["id"]]["text"], "ok")
        fallback.assert_called_once_with("broken.mp3", 1000, 1500)

    def test_double_decoder_failure_stays_inconclusive(self):
        model = SimpleNamespace(transcribe=lambda _: [SimpleNamespace(text="unexpected")])
        job = {"id": "F|52:44", "url": "https://example/052.mp3",
               "startMs": 1000, "endMs": 1500}
        fake_sf = SimpleNamespace(info=mock.Mock(side_effect=RuntimeError("libsndfile")))
        with (mock.patch.dict(sys.modules, {"soundfile": fake_sf}),
              mock.patch.object(R, "_local_model", return_value=model),
              mock.patch.object(R, "_prefetch"),
              mock.patch.object(R, "_range_pcm", return_value=None),
              mock.patch.object(R, "_local_audio", return_value="broken.mp3"),
              mock.patch.object(R, "_ffmpeg_window_pcm", side_effect=RuntimeError("ffmpeg"))):
            result, errors = R.local_run([job])
        self.assertEqual(result, {})
        self.assertIn("RuntimeError: ffmpeg", errors[job["id"]])


if __name__ == "__main__":
    unittest.main()
