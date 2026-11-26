#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختباراتُ `timing_witness.py` الخالصة (‏بلا نموذج): تطبيعُ الكلمة الأولى وربطُ ترقيم QWA بالكوفيّ."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import timing_witness as TW                                  # noqa: E402
from timing_witness import first_norm, kufi_from_qwa, QWA_RIWAYAT     # noqa: E402


class Norm(unittest.TestCase):
    def test_strips_marks_and_hamza_seats(self):
        self.assertEqual(first_norm("تَبَٰرَكَ"), "تبرك")
        self.assertEqual(first_norm("ٱلَّذِى"), "الذي")
        self.assertEqual(first_norm("أُو۟لَٰٓئِكَ"), first_norm("اولئك"))
        self.assertEqual(first_norm("فَسَلَٰمٌ"), "فسلم")


class Kufi(unittest.TestCase):
    SEQ = [("قل", 1000, 0.9), ("هو", 1400, 0.9), ("الله", 1800, 0.9), ("قل", 9000, 0.8), ("الله", 9500, 0.7)]

    def test_nearest_matching_first_word(self):
        out = kufi_from_qwa(self.SEQ, {1: "قل", 2: "الله"}, {1: 8800, 2: 1900})
        self.assertEqual(out, {1: (9000, 0.8), 2: (1800, 0.9)})

    def test_no_match_outside_window_or_wrong_word(self):
        self.assertEqual(kufi_from_qwa(self.SEQ, {1: "قل"}, {1: 5000}), {})       # أبعدُ من 3ث
        self.assertEqual(kufi_from_qwa(self.SEQ, {1: "لم"}, {1: 1000}), {})
        self.assertEqual(kufi_from_qwa(self.SEQ, {1: ""}, {1: 1000}), {})

    def test_supported_riwayat(self):
        self.assertEqual(QWA_RIWAYAT, ("hafs", "warsh", "qalun"))


if __name__ == "__main__":
    unittest.main()


class PauseAround(unittest.TestCase):
    def test_pause_end_found_and_none_when_continuous(self):
        import tempfile
        import wave
        import numpy as np
        sr = 16000
        t = np.arange(sr * 3) / sr
        x = (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
        x[int(1.0 * sr):int(1.5 * sr)] = 0.0005 * np.random.RandomState(0).randn(int(0.5 * sr))   # سكتة 1.0–1.5ث
        with tempfile.TemporaryDirectory() as d:
            for name, sig in (("p.wav", x), ("c.wav", (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32))):
                with wave.open(f"{d}/{name}", "wb") as w:
                    w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
                    w.writeframes((sig * 32767).astype(np.int16).tobytes())
            got = TW.pause_around(f"{d}/p.wav", 1550)
            self.assertIsNotNone(got)
            self.assertAlmostEqual(got[1], 1500, delta=40)
            self.assertIsNone(TW.pause_around(f"{d}/c.wav", 1550))
