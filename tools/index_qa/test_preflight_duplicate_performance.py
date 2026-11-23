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
    SEG_MIN_S, classify_ratio, classify_start, envelope_peaks, main, repeated_segment, report, segment_run,
    synthesize_repeated_envelope,
)
import random


def _speechlike(n, seed):
    """غلافٌ شبيهٌ بالكلام بلا تكرار: مقاطع بطول عشوائيّ وطاقة عشوائيّة ووقفات."""
    rng = random.Random(seed)
    out = []
    while len(out) < n:
        out.extend([rng.uniform(0.2, 1.0) + rng.uniform(-0.05, 0.05) for _ in range(rng.randint(2, 9))])
        out.extend([rng.uniform(0.0, 0.05)] * rng.randint(0, 2))
    return out[:n]


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

    def test_partial_copy_is_caught_by_segments(self):
        """نمط الرباني س7: جزءٌ من الملف (600ث) منسوخٌ في وسطه ⇒ الارتباط الكلّيّ ضعيف والمقطعيّ يكشفه."""
        base = _speechlike(3000, 7)
        env = base[:2000] + base[100:700] + base[2000:]          # نسخةُ 100–700 عند 2000
        r = report(float(len(env)), None, None, envelope=env)
        seg = r["envelope"].get("repeated_segment")
        self.assertIsNotNone(seg, r["envelope"])
        self.assertEqual(r["verdict"], "repeated_segment")
        self.assertGreaterEqual(seg["run_s"], SEG_MIN_S)
        self.assertAlmostEqual(seg["lag_s"], 1900, delta=2)
        self.assertNotIn("suggested_trim", r)                     # لا قصّ مقترح لمقطعٍ داخليّ

    def test_no_repeat_stays_clean(self):
        """سالبٌ: غلافٌ بلا تكرار لا يُتّهم (صفر اتّهامٍ كاذب)."""
        for seed in (1, 2, 3):
            env = _speechlike(2500, seed)
            r = report(float(len(env)), 2500.0, None, envelope=env)
            self.assertIsNone(r["envelope"].get("repeated_segment"), seed)
            self.assertEqual(r["verdict"], "ok_by_duration", seed)

    def test_short_local_repeat_below_min_is_not_flagged(self):
        """تكرارُ آيةٍ واحدة (≈100ث كما في المروش س4) دون SEG_MIN_S لا يُعدّ تكراراً للملف."""
        base = _speechlike(2500, 11)
        env = base[:1500] + base[1400:1500] + base[1500:]
        self.assertIsNone(repeated_segment(env, [100]))
        self.assertLess(segment_run(env, 100)["run_s"], SEG_MIN_S)

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
