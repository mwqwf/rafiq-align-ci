#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختباراتُ إحصاء نوافذ المداخل (‏2026-11-07) — الموجبُ والسوالبُ الإلزاميّة.

    python -m unittest tools/index_qa/test_entry_window_census.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import entry_window_census as E                                       # noqa: E402

# نصوصٌ اصطناعيّةٌ للاختبار وحدَه (‏لا قرآنَ مولَّداً): كلماتٌ مجرّدةٌ تحاكي بنيةَ الآيات.
T = {1: "الف باء جيم دال هاء واو زاي".split(),
     2: "حاء طاء ياء كاف لام ميم نون".split(),
     3: "سين عين غين فاء صاد قاف راء شين".split(),
     4: "الف باء جيم دال هاء واو زاي حاء".split()}      # 4 تشبه 1 (متشابهة نصّاً)


def toks(words, p=0.9, t0=0):
    return [(w, t0 + i * 400, p) for i, w in enumerate(words)]


class JudgeEntry(unittest.TestCase):
    def test_exact_passes(self):
        r = E.judge_entry(2, toks(T[2]), T)
        self.assertEqual(r["verdict"], "pass", r)

    def test_other_ayah_after_rejected(self):
        # الآية 2 ثم بدءُ الآية 3 (‏ثلاثُ كلماتٍ من غيرها) — النافذةُ تحمل صوتَ آيةٍ أخرى
        r = E.judge_entry(2, toks(T[2] + T[3][:3]), T)
        self.assertEqual((r["verdict"], r["reason"]), ("reject", "آية أخرى"), r)
        self.assertEqual(r["otherAyah"], 3)

    def test_other_ayah_before_rejected(self):
        r = E.judge_entry(2, toks(T[3][-3:] + T[2]), T)
        self.assertEqual((r["verdict"], r["reason"]), ("reject", "آية أخرى"), r)

    def test_two_adjacent_words_of_next_ayah_rejected(self):
        r = E.judge_entry(2, toks(T[2] + T[3][:2]), T)
        self.assertEqual((r["verdict"], r["reason"]), ("reject", "آية أخرى"), r)

    def test_own_ayah_twice_is_excess(self):
        r = E.judge_entry(2, toks(T[2] + T[2]), T)
        self.assertEqual((r["verdict"], r["reason"]), ("reject", "زيادة"), r)

    def test_excess_unrelated_words_rejected(self):
        extra = "ظاء ذال ضاد خاء ثاء تاء".split()
        r = E.judge_entry(2, toks(T[2] + extra), T)
        self.assertEqual((r["verdict"], r["reason"]), ("reject", "زيادة"), r)

    def test_truncated_rejected(self):
        r = E.judge_entry(2, toks(T[2][:4]), T)
        self.assertEqual((r["verdict"], r["reason"]), ("reject", "نقص"), r)

    def test_missing_head_rejected(self):
        r = E.judge_entry(2, toks(T[2][3:]), T)
        self.assertEqual((r["verdict"], r["reason"]), ("reject", "نقص"), r)

    def test_low_confidence_rejected(self):
        r = E.judge_entry(2, toks(T[2], p=0.4), T)
        self.assertEqual((r["verdict"], r["reason"]), ("reject", "نقص"), r)

    def test_silence_rejected(self):
        r = E.judge_entry(2, [], T)
        self.assertEqual((r["verdict"], r["reason"]), ("reject", "نقص"), r)

    def test_window_wholly_another_ayah_rejected(self):
        r = E.judge_entry(2, toks(T[3]), T)
        self.assertEqual((r["verdict"], r["reason"]), ("reject", "آية أخرى"), r)

    def test_similar_verse_text_is_not_flagged_as_other(self):
        # الآية 1 والآية 4 متشابهتان: تفريغُ الآية 1 بكلمةٍ زائدةٍ هي ختامُ 4 لا يُعدّ «آية أخرى» إن لم يبلغ ثلاثاً جديدة
        r = E.judge_entry(1, toks(T[1]), T)
        self.assertEqual(r["verdict"], "pass", r)

    def test_word_bounds_are_pin_heard_bounds(self):
        n = len(T[2])
        lo, hi = max(E.K, int(E.PH.W_LEN_LO * n)), int(E.PH.W_LEN_HI * n) + 1
        r = E.judge_entry(2, toks(T[2]), T)
        self.assertEqual(r["wordBounds"], [lo, hi])
        self.assertIs(E.MIN_WORD_P, E.PH.W_MIN_WORD_P)
        self.assertEqual(E.REPEAT_SIM, 0.7)


class SurahVerdict(unittest.TestCase):
    def test_one_reject_rejects_surah(self):
        rows = [{"ayah": 1, "verdict": "pass", "reason": ""}, {"ayah": 2, "verdict": "reject", "reason": "زيادة"}]
        v = E.surah_verdict(rows)
        self.assertFalse(v["ok"])
        self.assertEqual(v["rejectedAyahs"], [2])

    def test_all_pass(self):
        self.assertTrue(E.surah_verdict([{"ayah": 1, "verdict": "pass", "reason": ""}])["ok"])

    def test_empty_is_not_ok(self):
        self.assertFalse(E.surah_verdict([])["ok"])


def cmap(entries):
    """{آية: (مرساة[بدء،نهاية]، جودة، [[بدء،نهاية،تشابه]])} ⇒ خريطةٌ مختصرة."""
    return {"anchors": {str(a): [am, q, occ] for a, (am, q, occ) in entries.items()}}


class MeasuredRepeats(unittest.TestCase):
    def test_two_separate_performances_counts(self):
        m = cmap({2: ([10000, 20000], 0.9, [[40000, 50000, 0.85]])})
        self.assertIn(2, E.measured_repeats(m, T))

    def test_below_similarity_not_counted(self):
        m = cmap({2: ([10000, 20000], 0.9, [[40000, 50000, 0.65]])})
        self.assertEqual(E.measured_repeats(m, T), {})

    def test_overlapping_occurrence_is_same_performance(self):
        m = cmap({2: ([10000, 20000], 0.9, [[11000, 19000, 0.9]])})
        self.assertEqual(E.measured_repeats(m, T), {})

    def test_low_quality_anchor_is_not_a_performance(self):
        m = cmap({2: ([10000, 20000], 0.3, [[40000, 50000, 0.85]])})
        self.assertEqual(E.measured_repeats(m, T), {})

    def test_occurrence_on_similar_verse_excluded(self):
        # الآية 1 لها أداءٌ ثانٍ يقع على مرساة الآية 4 المتشابهة نصّاً ⇒ ليس تكراراً
        m = cmap({1: ([0, 10000], 0.9, [[30000, 40000, 0.8]]),
                  4: ([30000, 40000], 0.9, [])})
        r = E.measured_repeats(m, T)
        self.assertNotIn(1, r)

    def test_occurrence_on_dissimilar_verse_still_counts(self):
        m = cmap({2: ([0, 10000], 0.9, [[30000, 40000, 0.8]]),
                  3: ([30000, 40000], 0.9, [])})
        self.assertIn(2, E.measured_repeats(m, T))

    def test_full_heardmap_format(self):
        m = {"heardMap": {"2": {"anchorMs": [0, 9000], "anchorQuality": 0.9, "occurrences": [[30000, 39000, 0.9]]}}}
        self.assertIn(2, E.measured_repeats(m, T))


if __name__ == "__main__":
    unittest.main()
