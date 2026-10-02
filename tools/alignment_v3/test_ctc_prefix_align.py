# -*- coding: utf-8 -*-
"""حُرّاسُ `ctc_prefix_align.py` (الذيلُ المبتور · أمر المالك 2026-10-02): ثقةٌ ومدّةٌ وصعودٌ وصوتٌ بعد N."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ctc_prefix_align as P  # noqa: E402

N, TOTAL = 30, 766_902


def _rows(keep=N, n=64, conf=0.7, dur=20_000):
    rows, t = [], 7_000
    for k in range(n):
        if k < keep:
            rows.append({"ayahIdx": k, "startMs": t, "endMs": t + dur, "conf": conf, "snapped": True})
            t += dur
        else:
            rows.append({"ayahIdx": k, "startMs": None, "endMs": None, "conf": 0.0, "snapped": False})
    return rows, t


class PrefixGuards(unittest.TestCase):
    counts = [50] * 64

    def test_clean_prefix_passes(self):
        rows, sink = _rows()
        self.assertIsNone(P.prefix_error(rows, N, self.counts, sink, TOTAL))

    def test_low_confidence_refused(self):
        rows, sink = _rows()
        rows[14]["conf"] = 0.4
        self.assertIn("ثقةُ CTC", P.prefix_error(rows, N, self.counts, sink, TOTAL))

    def test_duration_outside_band_refused(self):
        rows, sink = _rows()
        counts = list(self.counts); counts[3] = 200       # 20ث لـ200 حرف = 0.25× المتوقَّع
        self.assertIn("مدّتُها", P.prefix_error(rows, N, counts, sink, TOTAL))

    def test_no_audio_after_n_refused(self):
        rows, sink = _rows()
        self.assertIn("لا صوتَ بعد", P.prefix_error(rows, N, self.counts, sink, sink + 200))

    def test_sink_must_start_at_end_of_n(self):
        rows, sink = _rows()
        self.assertIn("البالوعة", P.prefix_error(rows, N, self.counts, sink + 5, TOTAL))

    def test_build_rows_caps_unsnapped_and_blanks_tail(self):
        segs = [(k * 20.0, k * 20.0 + 20.0, -0.4) for k in range(N + 1)]
        rows, sink = P.build_rows(segs, 64, N, [], TOTAL)         # لا صمتَ ⇒ لا انطباق
        self.assertEqual(len(rows), 64)
        self.assertTrue(all(r["conf"] <= 0.74 for r in rows[:N]))
        self.assertTrue(all(r["startMs"] is None for r in rows[N:]))
        self.assertEqual(sink, rows[N - 1]["endMs"])
        with self.assertRaises(ValueError):
            P.build_rows(segs[:-1], 64, N, [], TOTAL)


if __name__ == "__main__":
    unittest.main()
