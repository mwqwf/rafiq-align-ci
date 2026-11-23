#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import unittest
from triage_heard_gate import triage, collapse_ranges


SAMPLE = """# heard_gate 1 · timings-staging/hafs/ibrahim_dosri.ddf2e3b4.jz
■ timings-staging/hafs/ibrahim_dosri.ddf2e3b4.jz (ddf2e3b4) · معدّلة [14] · عيّنة [31, 39, 63, 72]
   س14: ⛔ 11 آيةً تنحرف عن موضعها المسموع > 1.5ث (أقصاها الآية 21: -848.6ث) · الآيات 5,6,13,17,21,22,23,27,28,31,32
   س31: ✅
   س39: ⛔ 1 آيةً تنحرف عن موضعها المسموع > 1.5ث (أقصاها الآية 31: -2.4ث) · الآيات 31
   س63: ✅
   س72: ✅
   ℹ️ عيّنةٌ للتقرير (لا تردّ · تُضاف لطابور الإصلاح): س39 (عيّنة): 1 آيةً تنحرف عن موضعها المسموع > 1.5ث (أقصاها الآية 31: -2.4ث) · الآيات 31
   ⇒ ⛔ بوّابةُ السماع: س14: 11 آيةً تنحرف عن موضعها المسموع > 1.5ث (أقصاها الآية 21: -848.6ث) · الآيات 5,6,13,17,21,22,23,27,28,31,32
"""


class TriageTest(unittest.TestCase):
    def test_collapse(self):
        self.assertEqual(collapse_ranges([5, 6, 13, 17, 21, 22, 23, 27, 28, 31, 32]),
                         "5-6,13,17,21-23,27-28,31-32")

    def test_dosri_sample_excluded(self):
        r = triage(SAMPLE)
        self.assertEqual(r["modified_surahs"], [14])
        self.assertEqual(r["n_rejected_surahs"], 1)
        self.assertEqual(r["rejected"][0]["surah"], 14)
        self.assertEqual(r["suggested_rewindow"], "14:5-6,13,17,21-23,27-28,31-32")
        self.assertTrue(any(s["surah"] == 39 for s in r["sample_only"]))
        self.assertFalse(r["launch"])


if __name__ == "__main__":
    unittest.main()
