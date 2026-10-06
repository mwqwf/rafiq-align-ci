import os
import sys
import unittest
from unittest import mock

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ctc_seg as C


class ChunkedAlignmentTests(unittest.TestCase):
    def test_full_audio_groups_overlap_without_averaging_timings(self):
        texts = ["lead"] + [f"v{i}" for i in range(10)]
        calls = []

        def fake_segment(lpz, n_samples, group):
            frame_start = 1000 - lpz.shape[0]
            self.assertEqual(lpz.shape[0] * 16000, n_samples)
            calls.append((tuple(group), frame_start))
            call_shift = len(calls) / 10
            out = []
            for text in group:
                if text == "lead":
                    out.append((199.0 - frame_start, 199.5 - frame_start, -0.1))
                else:
                    verse = int(text[1:])
                    absolute = 200 + verse * 20 + call_shift
                    out.append((absolute - frame_start, absolute + 5 - frame_start, -0.2))
            return out

        with mock.patch.object(C, "_segment", side_effect=fake_segment):
            merged, evidence = C._segment_overlapping_groups(
                np.zeros((1000, 3)), 16000000, texts, 1, 5, 2)

        self.assertEqual([(0, 5), (3, 8), (6, 10)], [
            (g["startAyahIdx"], g["endAyahIdxExclusive"]) for g in evidence["groups"]])
        self.assertEqual(10, len(merged))
        self.assertEqual(4, len(evidence["overlapAyahs"]))
        self.assertAlmostEqual(0.1, evidence["maxStartDisagreementSeconds"])
        # Verse 3 is closer to the centre of the first claim, so that measured
        # claim is selected verbatim rather than averaging 260.1 and 260.2.
        self.assertEqual((260.1, 265.1, -0.2), merged[3])
        self.assertEqual([0, 100, 160], [frame_start for _, frame_start in calls])
        self.assertEqual("lead", calls[0][0][0])
        self.assertTrue(all("lead" not in group for group, _ in calls[1:]))
        self.assertEqual(("v1", "v2", "v3", "v4", "v5", "v6", "v7"), calls[1][0])
        self.assertEqual(("v4", "v5", "v6", "v7", "v8", "v9"), calls[2][0])
        self.assertEqual([(0, 0), (1, 2), (4, 2)], [
            (g["contextStartAyahIdx"], g["contextVerseCount"])
            for g in evidence["groups"]])

    def test_invalid_group_contract_is_rejected(self):
        args = (np.zeros((2, 2)), 10, ["v0", "v1"], 0)
        for group_size, overlap in ((1, 1), (2, 0), (2, 2)):
            with self.subTest(group_size=group_size, overlap=overlap):
                with self.assertRaises(ValueError):
                    C._segment_overlapping_groups(*args, group_size, overlap)
        with self.assertRaisesRegex(ValueError, "prior_context_seconds"):
            C._segment_overlapping_groups(*args, 2, 1, 0)

    def test_incomplete_group_population_is_rejected(self):
        with mock.patch.object(C, "_segment", return_value=[]):
            with self.assertRaisesRegex(RuntimeError, "incomplete utterance"):
                C._segment_overlapping_groups(
                    np.zeros((2, 2)), 10, ["v0", "v1"], 0, 2, 1)

    def test_numeric_windows_remeasure_only_bounded_context(self):
        def fake_segment(lpz, n_samples, texts):
            self.assertEqual(("v1", "v2", "v3", "v4", "v5"), tuple(texts))
            self.assertEqual(140, lpz.shape[0])
            self.assertEqual(2240000, n_samples)
            return [(10 + i, 11 + i, -0.2) for i in range(5)]

        spec={"id":"v3","startAyahIdx":1,"endAyahIdxExclusive":6,
              "targetAyahIdxs":[3],"audioStartMs":20000,"audioEndMs":160000}
        with mock.patch.object(C,"_segment",side_effect=fake_segment):
            result=C._segment_numeric_windows(
                np.zeros((1000,3)),16000000,[f"v{i}" for i in range(8)],[spec])
        self.assertEqual(1,len(result))
        self.assertEqual([3],result[0]["targetAyahIdxs"])
        self.assertEqual((30.0,31.0,-0.2),result[0]["segments"][0])

    def test_numeric_windows_reject_edge_target_and_incomplete_output(self):
        base={"id":"bad","startAyahIdx":1,"endAyahIdxExclusive":4,
              "targetAyahIdxs":[1],"audioStartMs":0,"audioEndMs":1000}
        with self.assertRaisesRegex(ValueError,"preceding and following"):
            C._segment_numeric_windows(np.zeros((10,2)),160000,["a"]*5,[base])
        good={**base,"targetAyahIdxs":[2]}
        with mock.patch.object(C,"_segment",return_value=[]):
            with self.assertRaisesRegex(RuntimeError,"incomplete"):
                C._segment_numeric_windows(np.zeros((10,2)),160000,["a"]*5,[good])


if __name__ == "__main__":
    unittest.main()
