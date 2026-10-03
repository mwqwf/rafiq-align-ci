# -*- coding: utf-8 -*-
"""اختباراتُ إعادة نافذة الطرفين في ctc_gapsplit (‏fixS1 · 2026-10-03): المطلعُ والخاتمةُ الحاضران
بحدٍّ معطوب، وشاهدُ «لا بسملة» — والمدى المقلوبُ والسورةُ كلُّها والمرساةُ الغائبةُ تُردّ."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ctc_gapsplit as G  # noqa: E402


def ents(n, missing=()):
    return {k: {"startMs": k * 1000, "endMs": k * 1000 + 1000} for k in range(1, n + 1) if k not in missing}


class Spec(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(G.parse_rewindow_spec("55:41-75"), (55, 41, 75, False))

    def test_head_nb(self):
        self.assertEqual(G.parse_rewindow_spec("89:1-2/nb"), (89, 1, 2, True))

    def test_nb_only_head(self):
        with self.assertRaises(ValueError):
            G.parse_rewindow_spec("89:2-3/nb")

    def test_reversed(self):
        with self.assertRaises(ValueError):
            G.parse_rewindow_spec("89:3-2")

    def test_zero(self):
        with self.assertRaises(ValueError):
            G.parse_rewindow_spec("89:0-2")


class Kind(unittest.TestCase):
    def test_interior(self):
        self.assertEqual(G.rewindow_kind(3, 4, 10, ents(10)), ("rewin", None))

    def test_head(self):
        self.assertEqual(G.rewindow_kind(1, 2, 10, ents(10)), ("rewhead", None))

    def test_tail(self):
        self.assertEqual(G.rewindow_kind(9, 10, 10, ents(10)), ("rewtail", None))

    def test_whole_surah_refused(self):
        self.assertIsNotNone(G.rewindow_kind(1, 10, 10, ents(10))[1])

    def test_beyond_refused(self):
        self.assertIsNotNone(G.rewindow_kind(9, 11, 10, ents(10))[1])

    def test_head_anchor_missing(self):
        self.assertIsNotNone(G.rewindow_kind(1, 2, 10, ents(10, missing=(3,)))[1])

    def test_tail_anchor_missing(self):
        self.assertIsNotNone(G.rewindow_kind(9, 10, 10, ents(10, missing=(8,)))[1])

    def test_interior_anchor_missing(self):
        self.assertIsNotNone(G.rewindow_kind(3, 4, 10, ents(10, missing=(5,)))[1])


if __name__ == "__main__":
    unittest.main()
