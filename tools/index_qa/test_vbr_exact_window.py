#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""عقدُ الفكّ الكامل الدقيق: لا قفزَ بالتقدير في MP3 غير ثابت المعدّل.

‏وقع 2026-09-26 على إحصاء `nasser_almajed@05b18814` (‏س6 من بديلٍ على archive.org):
‏ترويسةُ Xing تُعلن أقلَّ من الموجود («Xing stream size off by more than 1%»)،
‏فأخذ libsndfile طولَ الملفّ منها: ما بعد الحدّ المُعلَن صفرُ عيّنة ⇒ 213 نافذةً
‏«array of sample points is empty»، وما قبله قفزٌ تقديريٌّ يُسمِع غيرَ المطلوب.

‏يُصنع هنا ملفٌّ VBR بنبضاتٍ نغميّةٍ معلومةِ الموضع والتردّد، وتُكذَّب ترويستُه
‏عمداً (‏60% من الإطارات والبايتات)، ثم يُطلب سماعُ كلّ نبضةٍ بموضعها. بلا صوتٍ قرآني.
"""
from __future__ import annotations

import shutil
import struct
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

RATE = 44100
SECS = 60
PULSES = [(k * 5 + 1.0, 300 + 100 * k) for k in range(SECS // 5)]   # (بدايةٌ بالثانية, تردّد)
PULSE_S = 0.5


def _peak_hz(x, rate):
    x = np.asarray(x, dtype="float64")
    if not len(x):
        return None
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    return float(np.argmax(spec) * rate / len(x))


def _make_vbr(root, lie=True, cbr=False):
    rng = np.random.default_rng(7)
    a = np.zeros(RATE * SECS, dtype="float32")
    for t0, hz in PULSES:
        n = int(PULSE_S * RATE)
        t = np.arange(n) / RATE
        i = int(t0 * RATE)
        a[i:i + n] += (0.5 * np.sin(2 * np.pi * hz * t)).astype("float32")
    # ‏ضجيجٌ متفاوتُ الشدّة كلَّ ثانية يُجبر المرمِّز على تفاوت المعدّل
    env = np.repeat(rng.uniform(0, 0.08, SECS), RATE).astype("float32")
    a += env * rng.standard_normal(len(a)).astype("float32")
    wav = Path(root) / "src.wav"
    sf.write(wav, a, RATE)
    mp3 = Path(root) / ("cbr.mp3" if cbr else "vbr.mp3")
    enc = (["-b:a", "128k", "-write_xing", "0"] if cbr else ["-q:a", "5"])
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(wav),
                    "-c:a", "libmp3lame", *enc, str(mp3)], check=True)
    if cbr or not lie:
        return mp3
    d = bytearray(mp3.read_bytes())
    i = d.find(b"Xing")
    assert i > 0, "لا ترويسة Xing في ملفّ VBR"
    flags = struct.unpack(">I", d[i + 4:i + 8])[0]
    assert flags & 3 == 3, "الترويسة لا تحمل عدَّ الإطارات والبايتات"
    frames, nbytes = struct.unpack(">II", d[i + 8:i + 16])
    d[i + 8:i + 16] = struct.pack(">II", int(frames * 0.6), int(nbytes * 0.6))
    bad = Path(root) / "lying_xing.mp3"
    bad.write_bytes(bytes(d))
    return bad


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg غير مثبّت")
class ExactWindowOnLyingXingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.td = tempfile.TemporaryDirectory()
        cls.bad = _make_vbr(cls.td.name)
        cls.cbr = _make_vbr(cls.td.name, cbr=True)

    @classmethod
    def tearDownClass(cls):
        R._DECODED.clear()
        cls.td.cleanup()

    def test_mechanism_libsndfile_trusts_the_lying_header(self):
        # ‏تشخيصٌ للعطب القديم لا عقدٌ للجديد: libsndfile يرى ملفّاً أقصر من الحقيقة
        info = sf.info(str(self.bad))
        t0, _ = PULSES[-1]
        a = int((t0 + 0.1) * info.samplerate)
        x, _ = sf.read(str(self.bad), start=a, stop=a + 4000, dtype="float32")
        if info.frames / info.samplerate > SECS - 1 and len(x):
            self.skipTest("libsndfile هنا لا يثق بالترويسة — العطبُ غير مُستنسَخ")
        self.assertLess(info.frames / info.samplerate, SECS * 0.8)
        self.assertEqual(len(x), 0)            # «array of sample points is empty»

    def test_non_constant_file_is_not_trusted_to_libsndfile(self):
        self.assertFalse(R._local_is_cbr(self.bad))
        self.assertFalse(R._local_is_cbr(Path(self.td.name) / "missing.mp3"))
        self.assertTrue(R._local_is_cbr(self.cbr))

    def test_every_pulse_is_heard_at_its_place(self):
        for t0, hz in PULSES:
            with self.subTest(t0=t0):
                x, rate = R._exact_window_pcm(self.bad, int((t0 + 0.1) * 1000),
                                              int((t0 + 0.4) * 1000))
                self.assertEqual((len(x), rate), (4800, 16000))
                self.assertAlmostEqual(_peak_hz(x, rate), hz, delta=15)
                # ‏وما بين النبضات لا نغمةَ فيه: لا انزياحَ يُسمِع نبضةً في غير موضعها
                g, _ = R._exact_window_pcm(self.bad, int((t0 + 1.5) * 1000),
                                           int((t0 + 3.5) * 1000))
                self.assertLess(float(np.sqrt(np.mean(np.square(g)))), 0.12)

    def test_window_past_real_end_is_still_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "لا يبلغ"):
            R._exact_window_pcm(self.bad, (SECS + 2) * 1000, (SECS + 5) * 1000)
        # ‏والحشوُ لا يكون إلا بشروطه: الآيةُ داخل الملفّ والنقصُ كلُّه بعده
        x, _ = R._exact_window_pcm(self.bad, (SECS - 1) * 1000, (SECS + 3) * 1000,
                                   ayah_end_ms=(SECS - 1) * 1000 + 500)
        self.assertEqual(len(x), 64000)
        self.assertTrue((x[-40000:] == 0).all())
        with self.assertRaisesRegex(RuntimeError, "لا يبلغ"):
            R._exact_window_pcm(self.bad, (SECS - 1) * 1000, (SECS + 3) * 1000,
                                ayah_end_ms=(SECS + 2) * 1000)

    def test_local_run_hears_all_pulses_through_the_exact_path(self):
        heard = []
        model = SimpleNamespace(transcribe=lambda y: [SimpleNamespace(
            text=str(round(_peak_hz(y, 16000) or 0, -2)))])
        jobs = [{"id": f"D|{hz}", "url": "https://example/006.mp3",
                 "startMs": int((t0 + 0.1) * 1000), "endMs": int((t0 + 0.4) * 1000)}
                for t0, hz in PULSES]
        with (mock.patch.object(R, "_local_model", return_value=model),
              mock.patch.object(R, "_prefetch"),
              mock.patch.object(R, "_range_pcm", return_value=None),
              mock.patch.object(R, "_local_audio", return_value=str(self.bad)),
              mock.patch.object(R, "_ffmpeg_window_pcm",
                                side_effect=AssertionError("لا قفز بالتقدير"))):
            res, errs = R.local_run(jobs)
        self.assertEqual(errs, {})
        for t0, hz in PULSES:
            heard.append(float(res[f"D|{hz}"]["text"]))
        self.assertEqual(heard, [float(round(hz, -2)) for _, hz in PULSES])


class FullDecodeRejectsTest(unittest.TestCase):
    def setUp(self):
        R._DECODED.clear()
        self.td = tempfile.TemporaryDirectory()
        self.mp3 = Path(self.td.name) / "x.mp3"
        self.mp3.write_bytes(b"\0" * 100)

    def tearDown(self):
        R._DECODED.clear()
        self.td.cleanup()

    def _run(self, rc=0, pcm=None, err=b""):
        def fake(cmd, stdout=None, stderr=None, **kw):
            if pcm is not None:
                stdout.write(np.asarray(pcm, dtype="<f4").tobytes())
            return subprocess.CompletedProcess(cmd, rc, stdout=None, stderr=err)
        return mock.patch.object(R.subprocess, "run", side_effect=fake)

    def _no_cache_left(self):
        self.assertFalse(Path(str(self.mp3) + ".16k.f32").exists())
        self.assertFalse(Path(str(self.mp3) + ".16k.f32.part").exists())
        self.assertNotIn(str(self.mp3), R._DECODED)

    def test_decoder_failure_is_an_error_and_leaves_no_cache(self):
        with self._run(rc=1, err=b"Invalid data"):
            with self.assertRaisesRegex(RuntimeError, "Invalid data"):
                R._exact_window_pcm(self.mp3, 0, 500)
        self._no_cache_left()

    def test_zero_rc_with_decoder_message_is_rejected(self):
        with self._run(pcm=np.ones(16000), err=b"[mp3float] Header missing"):
            with self.assertRaisesRegex(RuntimeError, "rc=0"):
                R._exact_window_pcm(self.mp3, 0, 500)
        self._no_cache_left()

    def test_nan_is_rejected(self):
        pcm = np.ones(16000)
        pcm[100] = np.nan
        with self._run(pcm=pcm), mock.patch.object(R, "_file_duration_ms", return_value=1000.0):
            with self.assertRaisesRegex(RuntimeError, "NaN"):
                R._exact_window_pcm(self.mp3, 0, 500)
        self._no_cache_left()

    def test_decode_shorter_than_frame_count_is_rejected(self):
        # ‏فكٌّ يقف قبل آخر إطار = ملفٌّ لم يُسمع كلُّه — لا يُقصّ منه
        with self._run(pcm=np.ones(16000)), \
                mock.patch.object(R, "_file_duration_ms", return_value=5000.0):
            with self.assertRaisesRegex(RuntimeError, "لا يطابق الملفّ"):
                R._exact_window_pcm(self.mp3, 0, 500)
        self._no_cache_left()

    def test_matching_decode_is_sliced_exactly(self):
        pcm = np.arange(32000, dtype="float32")
        with self._run(pcm=pcm), mock.patch.object(R, "_file_duration_ms", return_value=2000.0):
            x, rate = R._exact_window_pcm(self.mp3, 1250, 1750)
        self.assertEqual(rate, 16000)
        np.testing.assert_array_equal(x, pcm[20000:28000])


if __name__ == "__main__":
    unittest.main()
