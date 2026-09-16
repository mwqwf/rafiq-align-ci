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
    phase = 2 * np.pi * (300 * t + 0.5 * 1600 * t * t)
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
            # نعزل **الفك** المستقل عن اختلاف مرشّح إعادة أخذ العينات:
            # libsndfile يفك MP3 كاملاً، ثم يمر المرجع lossless عبر مرشح ffmpeg
            # نفسه إلى 16kHz. المقارنة السابقة استعملت np.interp الخطي للمرجع
            # مقابل swresample للمسار الفعلي، فكانت تقيس مرشحين لا مفككين.
            ref_wav = Path(td) / "independent-reference.wav"
            sf.write(ref_wav, ref, ref_rate, subtype="FLOAT")
            ref_done = subprocess.run(
                ["ffmpeg", "-nostdin", "-v", "error", "-i", str(ref_wav),
                 "-f", "f32le", "-ac", "1", "-ar", "16000", "pipe:1"],
                capture_output=True, check=False,
            )
            self.assertEqual(
                ref_done.returncode, 0, ref_done.stderr.decode(errors="replace")
            )
            self.assertEqual(len(ref_done.stdout) % 4, 0)
            ref16 = np.frombuffer(ref_done.stdout, dtype="<f4").copy()
        self.assertEqual(rate, 16000)
        self.assertEqual(len(got), 8000)
        self.assertEqual(len(ref16), len(got))
        def wave_corr_at(lag, right):
            if lag < 0:
                a0, b0 = got[:lag], right[-lag:]
            elif lag > 0:
                a0, b0 = got[lag:], right[:-lag]
            else:
                a0, b0 = got, right
            a0, b0 = a0 - a0.mean(), b0 - b0.mean()
            return float(np.dot(a0, b0) / (np.linalg.norm(a0) * np.linalg.norm(b0)))

        # التشابه العيني تشخيصي فقط: مفككا MP3 المستقلان يختلفان طورياً.
        wave_corr, wave_lag = max(
            (wave_corr_at(test_lag, ref16), test_lag)
            for test_lag in range(-320, 321)
        )

        def spectral(x):
            # إطار 32م.ث وقفزة 5م.ث: مقدار الطيف يلغي اختلاف الطور بين المفككين،
            # ويبقي مسار التردد الزمني الذي يكشف انزياح النافذة.
            size, hop = 512, 80
            window = np.hanning(size).astype("float32")
            frames = np.stack([
                x[i:i + size] * window
                for i in range(0, len(x) - size + 1, hop)
            ])
            mag = np.log1p(np.abs(np.fft.rfft(frames, axis=1))[:, 1:])
            return mag / np.maximum(np.linalg.norm(mag, axis=1, keepdims=True), 1e-12)

        def spectral_match(left, right, lag):
            if lag < 0:
                a0, b0 = left[:lag], right[-lag:]
            elif lag > 0:
                a0, b0 = left[lag:], right[:-lag]
            else:
                a0, b0 = left, right
            return float(np.mean(np.sum(a0 * b0, axis=1)))

        left_spec, ref_spec = spectral(got), spectral(ref16)
        spectral_corr, frame_lag = max(
            (spectral_match(left_spec, ref_spec, test_lag), test_lag)
            for test_lag in range(-4, 5)
        )
        print(
            f"independent-decode waveform_corr={wave_corr:.9f} "
            f"sample_lag={wave_lag}; spectral_corr={spectral_corr:.9f} "
            f"frame_lag={frame_lag}"
        )
        self.assertLessEqual(abs(wave_lag), 160, f"انزياح زائد: {wave_lag} عينة")
        self.assertGreater(spectral_corr, 0.98)
        self.assertLessEqual(abs(frame_lag), 2)  # 2 × 5م.ث = 10م.ث

        # ضابط موجب: انزياح مصطنع 15م.ث يجب أن يتجاوز حد العقد 10م.ث.
        shifted = np.concatenate((np.zeros(240, dtype="float32"), ref16[:-240]))
        shifted_spec = spectral(shifted)
        shifted_corr, shifted_lag = max(
            (spectral_match(left_spec, shifted_spec, test_lag), test_lag)
            for test_lag in range(-4, 5)
        )
        print(
            f"shift-control spectral_corr={shifted_corr:.9f} "
            f"frame_lag={shifted_lag}"
        )
        self.assertGreater(shifted_corr, 0.98)
        self.assertGreater(abs(shifted_lag), 2)


    def test_truncated_real_mp3_cannot_become_a_judgment(self):
        with tempfile.TemporaryDirectory() as td:
            mp3 = _make_chirp_mp3(td)
            damaged = Path(td) / "truncated.mp3"
            raw = mp3.read_bytes()
            damaged.write_bytes(raw[:len(raw) // 2])
            with self.assertRaises(RuntimeError):
                R._ffmpeg_window_pcm(damaged, 2400, 2900)

    def test_zero_returncode_with_decoder_error_is_rejected(self):
        pcm = np.ones(8000, dtype="<f4")
        done = subprocess.CompletedProcess(
            [], 0, stdout=pcm.tobytes(),
            stderr=b"[mp3float] Header missing\nError while decoding stream",
        )
        with mock.patch.object(R.subprocess, "run", return_value=done):
            with self.assertRaisesRegex(RuntimeError, "rc=0"):
                R._ffmpeg_window_pcm("damaged.mp3", 0, 500)

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
