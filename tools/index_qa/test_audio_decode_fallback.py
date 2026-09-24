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


def _make_marker_mp3(root):
    """ثلاث نبضات زمنية معلومة؛ غلافها يكشف الانزياح بلا حساسية للطور."""
    rate = 44100
    audio = np.zeros(rate * 3, dtype="float32")
    for center, freq, amp in ((1.30, 440, 0.25), (1.50, 880, 0.35),
                              (1.70, 1320, 0.45)):
        width = int(0.040 * rate)
        start = int(round((center - 0.020) * rate))
        t = np.arange(width, dtype="float64") / rate
        burst = amp * np.sin(2 * np.pi * freq * t) * np.hanning(width)
        audio[start:start + width] += burst.astype("float32")
    wav = Path(root) / "markers.wav"
    mp3 = Path(root) / "markers.mp3"
    sf.write(wav, audio, rate)
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
        """ffmpeg يُقارن بـlibsndfile على نبضات زمنية معلومة تكشف الانزياح."""
        with tempfile.TemporaryDirectory() as td:
            mp3 = _make_marker_mp3(td)
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

        def envelope(x):
            # RMS في إطار 10م.ث وقفزة 5م.ث: يلغي فرق الطور ولون مرشح MP3،
            # ويبقي مواقع النبضات الثلاثة، وهي المطلوب من إحداثيات النافذة.
            size, hop = 160, 80
            return np.asarray([
                np.sqrt(np.mean(np.square(x[i:i + size], dtype="float64")))
                for i in range(0, len(x) - size + 1, hop)
            ])

        def env_corr(left, right, lag):
            if lag < 0:
                a0, b0 = left[:lag], right[-lag:]
            elif lag > 0:
                a0, b0 = left[lag:], right[:-lag]
            else:
                a0, b0 = left, right
            a0, b0 = a0 - a0.mean(), b0 - b0.mean()
            return float(np.dot(a0, b0) / (np.linalg.norm(a0) * np.linalg.norm(b0)))

        left_env, ref_env = envelope(got), envelope(ref16)
        env_corr_value, frame_lag = max(
            (env_corr(left_env, ref_env, test_lag), test_lag)
            for test_lag in range(-4, 5)
        )
        print(
            f"independent-decode waveform_corr={wave_corr:.9f} "
            f"sample_lag={wave_lag}; envelope_corr={env_corr_value:.9f} "
            f"frame_lag={frame_lag}"
        )
        self.assertLessEqual(abs(wave_lag), 160, f"انزياح زائد: {wave_lag} عينة")
        self.assertGreater(env_corr_value, 0.98)
        self.assertLessEqual(abs(frame_lag), 2)  # 2 × 5م.ث = 10م.ث

        # ضابط موجب: انزياح مصطنع 15م.ث يجب أن يتجاوز حد العقد 10م.ث.
        shifted = np.concatenate((np.zeros(240, dtype="float32"), ref16[:-240]))
        shifted_env = envelope(shifted)
        shifted_corr, shifted_lag = max(
            (env_corr(left_env, shifted_env, test_lag), test_lag)
            for test_lag in range(-4, 5)
        )
        print(
            f"shift-control envelope_corr={shifted_corr:.9f} "
            f"frame_lag={shifted_lag}"
        )
        self.assertGreater(shifted_corr, 0.98)
        self.assertGreater(abs(shifted_lag), 2)


    def test_truncated_real_mp3_cannot_become_a_judgment(self):
        with tempfile.TemporaryDirectory() as td:
            mp3 = _make_marker_mp3(td)
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


class WindowPastEndOfFileTest(unittest.TestCase):
    """نافذةٌ تمتدّ بعد نهاية الملفّ (‏yousef 102:8 · 93:11): الحشوُ بصمتٍ بشروطٍ مجتمعة."""

    def _call(self, got_ms, file_dur_ms, ayah_end_ms, start=0, end=8000):
        pcm = np.full(int(got_ms * 16), 0.25, dtype="<f4")
        with mock.patch.object(R.subprocess, "run", return_value=_done(pcm)):
            return R._ffmpeg_window_pcm("tail.mp3", start, end,
                                        ayah_end_ms=ayah_end_ms, file_dur_ms=file_dur_ms)

    def test_shortfall_after_eof_with_ayah_inside_is_padded(self):
        got, rate = self._call(got_ms=7746.5625, file_dur_ms=7750, ayah_end_ms=7400)
        self.assertEqual((len(got), rate), (128000, 16000))
        self.assertTrue((got[:123945] == 0.25).all())
        self.assertTrue((got[123945:] == 0).all())

    def test_shortfall_with_ayah_beyond_file_end_is_rejected(self):
        # ملفٌّ مبتور: الآيةُ نفسُها تنتهي بعد آخر إطار.
        with self.assertRaisesRegex(RuntimeError, "ناقصة"):
            self._call(got_ms=7746.5625, file_dur_ms=7750, ayah_end_ms=7900)

    def test_shortfall_in_middle_of_file_is_rejected(self):
        # الملفُّ أطول من النافذة: النقصُ عطبُ فكٍّ لا نهايةُ ملفّ.
        with self.assertRaisesRegex(RuntimeError, "ناقصة"):
            self._call(got_ms=5313.6875, file_dur_ms=60000, ayah_end_ms=4000)

    def test_shortfall_that_stops_before_eof_is_rejected(self):
        # الطلبُ يتجاوز النهاية لكنّ المفكوك انقطع قبلها بثانيتين: نقصٌ في الوسط.
        with self.assertRaisesRegex(RuntimeError, "ناقصة"):
            self._call(got_ms=5750, file_dur_ms=7750, ayah_end_ms=5000)

    def test_without_ayah_end_the_error_stays(self):
        with self.assertRaisesRegex(RuntimeError, "ناقصة"):
            self._call(got_ms=7746.5625, file_dur_ms=7750, ayah_end_ms=None)

    def test_real_mp3_tail_window_measured_by_frame_count(self):
        with tempfile.TemporaryDirectory() as td:
            mp3 = _make_marker_mp3(td)                    # ≈3ث
            got, rate = R._ffmpeg_window_pcm(mp3, 2000, 4000, ayah_end_ms=2900)
            self.assertEqual(len(got), 32000)
            self.assertTrue((got[-8000:] == 0).all())
            with self.assertRaisesRegex(RuntimeError, "ناقصة"):
                R._ffmpeg_window_pcm(mp3, 2000, 4000, ayah_end_ms=3500)

    def test_local_run_passes_ayah_end_only_when_job_carries_it(self):
        pcm = np.ones(8000, dtype="float32")
        model = SimpleNamespace(transcribe=lambda _: [SimpleNamespace(text="ok")])
        job = {"id": "L|102:8", "url": "https://example/102.mp3",
               "startMs": 1000, "endMs": 1500, "ayahEndMs": 1400}
        fake_sf = SimpleNamespace(info=mock.Mock(side_effect=RuntimeError("libsndfile")))
        with (mock.patch.dict(sys.modules, {"soundfile": fake_sf}),
              mock.patch.object(R, "_local_model", return_value=model),
              mock.patch.object(R, "_prefetch"),
              mock.patch.object(R, "_range_pcm", return_value=None),
              mock.patch.object(R, "_local_audio", return_value="tail.mp3"),
              mock.patch.object(R, "_ffmpeg_window_pcm", return_value=(pcm, 16000)) as fallback):
            R.local_run([job])
        fallback.assert_called_once_with("tail.mp3", 1000, 1500, ayah_end_ms=1400)


if __name__ == "__main__":
    unittest.main()
