#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختباراتُ التشديدات الثلاثة (أ ب ج) لحكم المدخل (‏2026-11-08).

    python -m unittest tools/index_qa/test_entry_window_tightenings.py

القياساتُ اصطناعيّةٌ (‏لا نماذجَ ولا صوت)، والنصوصُ كلماتٌ مجرّدةٌ لا قرآنَ مولَّداً.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import entry_window_census as E                                       # noqa: E402

T = {1: "الف باء جيم دال هاء واو زاي".split(),
     2: "حاء طاء ياء كاف لام ميم نون".split(),
     3: "سين عين غين فاء صاد قاف راء شين".split(),
     4: "ظاء ذال ضاد خاء ثاء تاء".split(),
     5: "الف باء جيم دال هاء واو زاي".split()}        # 5 مطابقةٌ نصّاً للآية 1 (‏بعيدةٌ عنها: ليست ±2)
T2 = dict(T)
T2[3] = list(T[2])                                      # 3 مطابقةٌ نصّاً للآية 2 (‏جارةٌ ±1)

def toks(words, p=0.9):
    return [(w, i * 400, p) for i, w in enumerate(words)]


class Tightenings(unittest.TestCase):
    # (أ) حدٌّ أدنى لتشابه الآية بالتفريغ
    def test_a_sim_floor_blocks_low_similarity_pass(self):
        # الآية أقربُ من الجارات بهامشٍ لكنّ التشابه متدنٍّ: 3 كلماتٍ صحيحةٍ من 7 وبقيّتُها شاذّة
        heard = T[1][:2] + ["صصصصصصص", "ضضضضضضض", "ططططططط", "ظظظظظظظظ", "ثثثثثثثثث"]
        r = E.judge_entry(1, toks(heard), T)
        self.assertLess(r["simSelf"], E.SIM_FLOOR, r)
        self.assertEqual((r["verdict"], r["reason"]), ("reject", "نقص"), r)

    def test_a_floor_keeps_documented_sound_entries(self):
        # أدنى مدخلٍ سليمٍ موثّقٍ في المعايرة مرّ بتشابه 0.411 (‏33:53 fakhfakh_qalun)؛ والأرضيّةُ تحته
        self.assertLessEqual(E.SIM_FLOOR, 0.411)
        self.assertEqual(E.SIM_FLOOR, 0.40)
        r = E.judge_entry(2, toks(T[2]), T)
        self.assertEqual(r["verdict"], "pass", r)

    # (ب) كلماتُ الجارة تُردّ «زيادة» لا تُسجَّل فقط
    def test_b_neighbour_words_reject_as_excess_even_within_count(self):
        # الآية 2 (7 كلمات) بعد استبدال ثلاثٍ منها بكلمات الجارة 3 ⇒ العددُ في الحدّ لكنّ فيه كلماتِ جارة
        heard = T[2][:4] + T[3][:3]
        r = E.judge_entry(2, toks(heard), T)
        self.assertEqual((r["verdict"], r["reason"]), ("reject", "زيادة"), r)
        self.assertEqual(r["containsAyah"], 3)

    def test_b_not_triggered_by_own_text(self):
        r = E.judge_entry(2, toks(T[2]), T)
        self.assertEqual(r["verdict"], "pass", r)
        self.assertNotIn("containsAyah", r)

    # (ج) الجارةُ المطابقةُ نصّاً منافِسة
    def test_c_identical_neighbour_undecided_rejected(self):
        r = E.judge_entry(2, toks(T2[2]), T2)               # بلا نوافذ ⇒ لا حسمَ بالموضع
        self.assertEqual((r["verdict"], r["reason"]), ("reject", "آية أخرى"), r)
        self.assertEqual(r["identicalRival"], [3])

    def test_c_identical_neighbour_overlapping_windows_rejected(self):
        win = {2: (0, 5000), 3: (4000, 9000)}
        r = E.judge_entry(2, toks(T2[2]), T2, win)
        self.assertEqual(r["reason"], "آية أخرى", r)

    def test_c_identical_neighbour_out_of_order_rejected(self):
        win = {2: (6000, 9000), 3: (0, 5000)}               # الآية 3 قبل 2 زمناً
        self.assertEqual(E.judge_entry(2, toks(T2[2]), T2, win)["reason"], "آية أخرى")

    def test_c_identical_neighbour_decided_by_position_passes(self):
        win = {2: (0, 5000), 3: (5000, 9000)}
        r = E.judge_entry(2, toks(T2[2]), T2, win)
        self.assertEqual(r["verdict"], "pass", r)
        r3 = E.judge_entry(3, toks(T2[3]), T2, win)
        self.assertEqual(r3["verdict"], "pass", r3)

    def test_c_non_neighbour_identical_is_not_a_rival(self):
        # 1 و5 متطابقتان لكن بينهما أكثر من ±2
        r = E.judge_entry(1, toks(T[1]), T)
        self.assertEqual(r["verdict"], "pass", r)

    def test_baseline_kept_for_before_column(self):
        # القاعدةُ السابقةُ تمرّر ما تردّه (ج) و(ب): هذا هو الفرقُ الذي يقيسه جدولُ قبل/بعد
        self.assertEqual(E.judge_entry_baseline(2, toks(T2[2]), T2)["verdict"], "pass")
        self.assertEqual(E.judge_entry_baseline(2, toks(T[2][:4] + T[3][:3]), T)["verdict"], "pass")


if __name__ == "__main__":
    unittest.main()
