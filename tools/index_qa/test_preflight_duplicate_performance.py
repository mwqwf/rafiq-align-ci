#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import array
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from preflight_duplicate_performance import (
    classify_ratio, classify_start, envelope_peaks, main, report, synthesize_repeated_envelope,
)


class PreflightTest(unittest.TestCase):
    def test_dosri_ratio_and_lead(self):
        # ملف 3942ث، مدى التوقيت 1393ث، الآية 1 عند 2548ث
        r = report(3942.8, expected_sec=1393.1, timing_start_ms=2548840)
        self.assertEqual(r["verdict"], "repeated_performance")
        self.assertGreaterEqual(r["ratio"], 2.5)
        self.assertTrue(r["leading_extra_material"])
        self.assertEqual(r["suggested_trim"]["start_ms"], 2548840)

    def test_clean_ratio(self):
        r = report(1567.6, expected_sec=1560.7)
        self.assertEqual(r["verdict"], "ok_by_duration")
        self.assertFalse(r.get("leading_extra_material"))

    def test_suspect_band(self):
        r = classify_ratio(8000, 4785)
        self.assertEqual(r["verdict"], "suspect_repeat_or_very_slow")

    def test_envelope_repeat(self):
        env = synthesize_repeated_envelope(perf_s=200, reps=3)
        peaks = envelope_peaks(env, min_lag_s=80, corr_min=0.7)
        self.assertTrue(peaks["repeated_like"])
        self.assertAlmostEqual(peaks["lag_s"], 200, delta=2)

    def test_cli_ffprobe_and_envelope_mocked(self):
        pcm = array.array("h", [min(30000, 100 + (i // 400) * 100) for i in range(400 * 260)]).tobytes()
        with mock.patch("preflight_duplicate_performance.subprocess.run") as mrun:
            mrun.side_effect = [
                mock.Mock(stdout="2167.7\n"),
                mock.Mock(stdout=pcm),
            ]
            out_path = Path("/tmp/test_preflight_out.json")
            rc = main([
                "--url", "https://example.com/010.mp3",
                "--expected-sec", "2690.5",
                "--ffprobe", "--envelope",
                "--reciter", "jelmam_qalun", "--surah", "10",
                "--out", str(out_path),
            ])
            self.assertEqual(rc, 0)
            data = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(data["verdict"], "ok_by_duration")
            self.assertEqual(data["file_sec"], 2167.7)
            self.assertEqual(data["envelope_seconds"], 260)


if __name__ == "__main__":
    unittest.main()
