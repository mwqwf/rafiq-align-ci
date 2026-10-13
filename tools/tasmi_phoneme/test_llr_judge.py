"""⚖️ حُرّاسُ `llr_judge.py` بلا صوتٍ ولا نموذج: الآلةُ نفسُها التي في `WordLlr.kt` (‏الحالاتُ الاصطناعيّةُ نفسُها في `WordLlrTest`)."""
import math
import unittest

import numpy as np

from llr_judge import judge, join, path_score, refine
from ctc_align import align

V, D = 6, 1


def row(sym, p=0.9):
    rest = (1 - p) / (V - 1)
    return [math.log(p if i == sym else rest) for i in range(V)]


def frames(*syms):
    return np.array([row(s) for s in syms])


def spoken(middle):
    return frames(0, 2, 2, 3, 3, 0, D, 0, *middle, 0, D, 0, 2, 2, 0, 2, 2, 0)


W = [[2, 3], [4, 5], [2, 2]]


class LlrTest(unittest.TestCase):
    def test_spoken_expected_clears(self):
        ev = refine(spoken([4, 4, 5, 5]), W, {1: None}, D)
        self.assertGreater(ev[1][4], 3.0)
        self.assertEqual(judge(ev[1][4], 3.0), "CLEAR")

    def test_truly_missing_keeps(self):
        ev = refine(spoken([0, 0, 0, 0]), W, {1: None}, D)
        self.assertLess(ev[1][4], 0.0)
        self.assertEqual(judge(ev[1][4], 3.0), "KEEP")

    def test_substituted_heard_is_what_was_said(self):
        ev = refine(spoken([3, 3, 3, 3]), W, {1: [3, 3]}, D)
        self.assertLess(ev[1][4], -3.0)

    def test_substituted_but_expected_was_said(self):
        ev = refine(spoken([4, 4, 5, 5]), W, {1: [3, 3]}, D)
        self.assertGreater(ev[1][4], 3.0)

    def test_judge_margins(self):
        self.assertEqual(judge(2.9, 3.0), "KEEP"); self.assertEqual(judge(3.0, 3.0), "CLEAR")
        self.assertEqual(judge(None, 3.0), "NO_EVIDENCE"); self.assertEqual(judge(float("nan"), 3.0), "NO_EVIDENCE")

    def test_impossible_alignment_gives_no_evidence(self):
        self.assertEqual(refine(frames(2, 3), W, {0: None, 2: None}, D), {0: None, 2: None})

    def test_path_score_matches_align_and_rejects(self):
        x = frames(0, 2, 2, 0, 3, 0)
        _, score = align(x, [2, 3])
        self.assertAlmostEqual(path_score(x, [2, 3]), score)
        self.assertIsNone(path_score(x, [2, 3], hi=1))
        self.assertIsNone(path_score(x, [0]))
        self.assertAlmostEqual(path_score(x, [], lo=1, hi=3), float(x[1:3, 0].sum()))

    def test_join(self):
        self.assertEqual(join([[2], [], [3, 4]], D), [2, D, 3, 4]); self.assertEqual(join([], D), [])


if __name__ == "__main__":
    unittest.main()
