#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختباراتُ `timing_witness.py` الخالصة (‏بلا نموذج): تطبيعُ الكلمة الأولى وربطُ ترقيم QWA بالكوفيّ."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
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
