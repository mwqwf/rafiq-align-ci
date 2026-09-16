#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""عقدُ تعافي MP3: اكتمالٌ وسلامةٌ ومرجعُ فك مستقل، بلا صوت قرآني."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent))
import run as R  # noqa: E402


def _done(pcm):
    return subprocess.CompletedProcess([], 0, stdout=np.asarray(pcm, dtype="<f4").tobytes(),
                                       stderr=b"")


def _make_chirp_mp3(root):
    """إشارة متغيرة زمنياً؛ يكشف مرجعُها أي انزياح، بخلاف نغمة ثابتة."""
    rate = 44100
    t = np.arange(rate * 3, dtype="float64") / rate
    phase = 2 * np.pi * (180 * t + 0.5 * 260 * t * t)
    wav = Path(root) / "chirp.wav"
    mp3 = Path(root) / "chirp.mp3"
    sf.write(wav, (0.35 * np.sin(phase)).astype("float32"), rate)
    made = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-i", str(wav),
         "-ar", str(rate), "-ac", "1", "-y", str(mp3)],
        capture_output=True, check=False,
    )
    if made.returncode:
        raise RuntimeError(made.stderr.decode(errors="replace"))
    return mp3


class AudioDecodeFallbackTest(unittest.TestCase):
    def test_ffmpeg_window_preserves_requested_coordinates(self):
        pcm = np.linspace(-0.5, 0.5, 8000, dtype="<f4")
        with mock.patch.object(R.subprocess, "run", return_value=_done(pcm)) as call:
            got, rate = R._ffmpeg_window_pcm("broken.mp3", 1250, 1750)
        self.assertEqual(rate, 16000)
        np.testing.assert_array_equal(got, pcm)
        cmd = call.call_args.args[0]
        self.assertEqual(cmd[cmd.index("-ss") + 1], "1.250")
        self.assertEqual(cmd[cmd.index("-t") + 1], "0.500")

    def test_partial_window_is_rejected_even_when_longer_than_point_two_seconds(self):
        # كان الشرط القديم يقبل 0.5ث لطلب 2ث لأنها أطول من 0.2ث.
        with mock.patch.object(R.subprocess, "run",
                               return_value=_done(np.ones(8000, dtype="float32"))):
            with self.assertRaisesRegex(RuntimeError, "ناقصة"):
                R._ffmpeg_window_pcm("damaged.mp3", 0, 2000)

    def test_unaligned_float_bytes_are_rejected_not_truncated(self):
        done = subprocess.CompletedProcess([], 0, stdout=b"\0" * (8000 * 4 + 1), stderr=b"")
        with mock.patch.object(R.subprocess, "run", return_value=done):
            with self.assertRaisesRegex(RuntimeError, "غير محاذى"):
                R._ffmpeg_window_pcm("damaged.mp3", 0, 500)

    def test_nan_and_inf_are_rejected(self):
        for bad in (np.nan, np.inf, -np.inf):
            pcm = np.ones(8000, dtype="<f4")
            pcm[4000] = bad
            with self.subTest(bad=bad), mock.patch.object(
                    R.subprocess, "run", return_value=_done(pcm)):
                with self.assertRaisesRegex(RuntimeError, "NaN/Inf"):
                    R._ffmpeg_window_pcm("damaged.mp3", 0, 500)

    def test_oversized_window_is_rejected(self):
        pcm = np.ones(10000, dtype="<f4")
        with mock.patch.object(R.subprocess, "run", return_value=_done(pcm)):
            with self.assertRaisesRegex(RuntimeError, "زائدة"):
                R._ffmpeg_window_pcm("shifted.mp3", 0, 500)

    def test_real_mp3_matches_independent_decoder_without_offset(self):
        """ffmpeg يُقارن بـlibsndfile على إشارة متغيرة زمنياً تكشف الانزياح."""
        with tempfile.TemporaryDirectory() as td:
            mp3 = _make_chirp_mp3(td)
            got, rate = R._ffmpeg_window_pcm(mp3, 1250, 1750)
            whole, ref_rate = sf.read(mp3, dtype="float32", always_2d=True)
            whole = whole.mean(axis=1)
            a, b = int(1.250 * ref_rate), int(1.750 * ref_rate)
            ref = whole[a:b]
            ref16 = np.interp(
                np.linspace(0, len(ref) - 1, len(got)),
                np.arange(len(ref)), ref,
            ).astype("float32")
        self.assertEqual(rate, 16000)
        self.assertEqual(len(got), 8000)
        def corr_at(lag):
            if lag < 0:
                a0, b0 = got[:lag], ref16[-lag:]
            elif lag > 0:
                a0, b0 = got[lag:], ref16[:-lag]
            else:
                a0, b0 = got, ref16
            a0, b0 = a0 - a0.mean(), b0 - b0.mean()
            return float(np.dot(a0, b0) / (np.linalg.norm(a0) * np.linalg.norm(b0)))
        # نبحث ±20م.ث ثم نسمح بنصفها فقط: اختلاف تأخير مفكّ صغير جائز،
        # أما انزياح نافذة ≥10م.ث فليس النافذة المطلوبة ويُفشل العقد.
        scored = [(corr_at(lag), lag) for lag in range(-320, 321)]
        corr, lag = max(scored)
        self.assertGreater(corr, 0.98, f"اختلاف فك: corr={corr:.5f}, lag={lag}")
        self.assertLessEqual(abs(lag), 160, f"انزياح زائد: {lag} عينة")

    def test_truncated_real_mp3_cannot_become_a_judgment(self):
        with tempfile.TemporaryDirectory() as td:
            mp3 = _make_chirp_mp3(td)
            damaged = Path(td) / "truncated.mp3"
            raw = mp3.read_bytes()
            damaged.write_bytes(raw[:len(raw) // 2])
            with self.assertRaises(RuntimeError):
                R._ffmpeg_window_pcm(damaged, 2400, 2900)

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
