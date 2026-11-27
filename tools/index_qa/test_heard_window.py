# -*- coding: utf-8 -*-
import json, os, sys, unittest
sys.path.insert(0, os.path.dirname(__file__))
import heard_window as W


def surah(start0, n=22, step=5000):
    return {a: (start0 + (a - 1) * step, start0 + a * step, "f") for a in range(1, n + 1)}


class SpanWindow(unittest.TestCase):
    def test_no_window_when_surah_starts_near_file_head(self):
        self.assertIsNone(W.span_window(surah(0)))
        self.assertIsNone(W.span_window(surah(19_999)))

    def test_window_for_embedded_surah(self):
        s = surah(138_000)
        lo, hi = W.span_window(s)
        self.assertEqual(lo, 138_000 - W.MARGIN_MS)
        self.assertEqual(hi, 138_000 + 22 * 5000 + W.MARGIN_MS)

    def test_window_uses_only_the_envelope_not_per_ayah_values(self):
        a, b = surah(138_000), surah(138_000)
        b[10] = (b[10][0] + 3000, b[10][1] + 3000, "f")      # آيةٌ وسطى مُزاحة لا تغيّر الغلاف
        self.assertEqual(W.span_window(a), W.span_window(b))

    def test_shifted_surah_stays_covered_no_hiding(self):
        """حقنٌ: سورةٌ مُزاحةٌ ±5 و±60ث في نسخةٍ ⇒ النافذةُ المشتقّة ما زالت تحوي صوتَها الحقيقيَّ كلَّه، فيُقاس الانحرافُ كاملاً."""
        true = surah(138_000)
        t_lo, t_hi = true[1][0], true[22][1]
        for shift in (-60_000, -5_000, 5_000, 60_000):
            shifted = {a: (v[0] + shift, v[1] + shift, v[2]) for a, v in true.items()}
            lo, hi = W.span_window(shifted)
            self.assertLessEqual(lo, t_lo, shift)
            self.assertGreaterEqual(hi, t_hi, shift)

    def test_entries_without_end_use_start(self):
        s = {1: (50_000, None, "f"), 2: (60_000, None, "f")}
        self.assertEqual(W.span_window(s), (50_000 - W.MARGIN_MS if 50_000 > W.MARGIN_MS else 0, 60_000 + W.MARGIN_MS))

    def test_empty(self):
        self.assertIsNone(W.span_window({}))


if __name__ == "__main__":
    unittest.main()
