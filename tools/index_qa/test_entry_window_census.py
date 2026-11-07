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
     4: "الف باء جيم دال هاء واو زاي حاء".split(),      # 4 تشبه 1 (متشابهة نصّاً)
     5: "ظاء ذال ضاد".split(),                            # آيةٌ قصيرة (لاختبار آيتين)
     6: "خاء ثاء تاء طاء ظاء ذال ضاد".split(),
     7: "ألف إباء آجيم".split()}


def toks(words, p=0.9, t0=0):
    return [(w, t0 + i * 400, p) for i, w in enumerate(words)]


class JudgeEntry(unittest.TestCase):
    def test_exact_passes(self):
        r = E.judge_entry(2, toks(T[2]), T)
        self.assertEqual(r["verdict"], "pass", r)

    def test_other_ayah_after_rejected(self):
        # الآية 2 ثم بدءُ الآية 3 (‏ثلاثُ كلماتٍ من غيرها) — النافذةُ تحمل صوتَ آيةٍ أخرى
        # يُردّ بالزيادة (‏10 > 8) ويُسجَّل في containsAyah أنّ فيه نصَّ الآية 3 (‏للتقرير)
        r = E.judge_entry(2, toks(T[2] + T[3][:3]), T)
        self.assertEqual((r["verdict"], r["reason"]), ("reject", "زيادة"), r)
        self.assertEqual(r["containsAyah"], 3)

    def test_other_ayah_before_rejected(self):
        r = E.judge_entry(2, toks(T[3][-3:] + T[2]), T)
        self.assertEqual((r["verdict"], r["reason"]), ("reject", "زيادة"), r)
        self.assertEqual(r["containsAyah"], 3)

    def test_two_adjacent_words_of_next_ayah_rejected(self):
        # 9 كلمات ⇒ فوق الحدّ 8 ⇒ تُردّ (‏بالزيادة: كلمتان لا تكفيان لتسمية «آية أخرى» بالتثليث)
        r = E.judge_entry(2, toks(T[2] + T[3][:2]), T)
        self.assertEqual(r["verdict"], "reject", r)

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

    def test_similar_neighbour_without_margin_rejected(self):
        # الآيتان 1 و4 متشابهتان (‏فجوة التشابه ≈ 0.07 < الهامش 0.10) ⇒ لا هامشَ للأقرب ⇒ تُردّ (‏التباس)
        t = {1: T[1], 2: T[4], 3: T[3]}        # متجاورتان (‏±2) فتنافسان
        r = E.judge_entry(1, toks(T[1]), t)
        self.assertEqual((r["verdict"], r["reason"], r["nearestOther"]), ("reject", "آية أخرى", 2), r)
        self.assertLess(r["gap"], E.NEAREST_MARGIN)

    def test_rasm_spelling_difference_passes(self):
        # فرقُ إملاءٍ في كلمةٍ طرفيّة (‏«تبرك» ↔ «تبارك») لا يردّ آيةً سليمة (‏مسارُ التشابه)
        heard = list(T[2])
        heard[0] = "حااء"
        heard[-1] = "نونن"
        r = E.judge_entry(2, toks(heard), T)
        self.assertEqual(r["verdict"], "pass", r)

    def test_dissimilar_head_closer_to_neighbour_rejected(self):
        # رأسٌ من الآية 3 وذيلٌ من الآية 2: الجارةُ 3 أقربُ ⇒ تُردّ
        heard = T[3][:5] + T[2][5:]
        r = E.judge_entry(2, toks(heard), T)
        self.assertEqual(r["verdict"], "reject", r)

    def test_one_extra_word_over_fuzzy_band_rejected(self):
        # 7 كلمات ⇒ الحدّ الأعلى 8 (‏1.2×)؛ تسعٌ تُردّ (‏المسارُ المشابه أضيقُ من التامّ)
        r = E.judge_entry(2, toks(T[2] + ["ظاء", "ذال"]), T)
        self.assertEqual((r["verdict"], r["reason"]), ("reject", "زيادة"), r)

    def test_word_bounds_are_pin_heard_bounds(self):
        import math
        n = len(T[2])
        lo, hi = max(E.K, math.ceil(E.PH.W_FUZZ_LEN_LO * n)), math.floor(E.PH.W_FUZZ_LEN_HI * n)
        r = E.judge_entry(2, toks(T[2]), T)
        self.assertEqual(r["wordBounds"], [lo, hi])
        self.assertIs(E.MIN_WORD_P, E.PH.W_MIN_WORD_P)
        self.assertIs(E.FUZZ_SIM, E.PH.W_FUZZ_SIM)
        self.assertEqual(E.REPEAT_SIM, 0.7)


class Nearest(unittest.TestCase):
    """القاعدةُ الجديدة (‏أمر القائد 2026-11-07): الأقربُ بهامشٍ + توحيدُ الكتابة + التحوّر."""

    def test_margin_is_a_code_constant(self):
        self.assertEqual(E.NEAREST_MARGIN, 0.10)
        self.assertEqual(E.NEAREST_RADIUS, 2)

    def test_mutation_entry_carrying_neighbour_text_rejected(self):
        # مدخلُ الآية 2 يحمل نصَّ الآية 3 (‏كحالة 67:19 التي حملت نصَّ 18) ⇒ يُردّ حتماً
        for host, carried in ((2, 3), (3, 2), (2, 1)):
            r = E.judge_entry(host, toks(T[carried]), T)
            self.assertEqual((r["verdict"], r["reason"]), ("reject", "آية أخرى"), (host, carried, r))
            self.assertEqual(r["otherAyah"], carried, r)

    def test_mutation_never_passes_even_with_full_confidence_and_fitting_length(self):
        # الآية 3 (8 كلمات) في نافذة الآية 2 (7 كلمات): العددُ في الحدّ [6,8] والثقةُ 1.0 ومع ذلك تُردّ
        r = E.judge_entry(2, toks(T[3], p=1.0), T)
        self.assertEqual(r["wordBounds"], [6, 8])
        self.assertEqual(r["verdict"], "reject", r)

    def test_two_ayat_entry_rejected_as_excess(self):
        # مدخلٌ بنصّ آيتين: الآية 2 (7) + الآية 5 القصيرة (3) = 10 > 8 ⇒ زيادة
        r = E.judge_entry(2, toks(T[2] + T[5]), T)
        self.assertEqual((r["verdict"], r["reason"]), ("reject", "زيادة"), r)

    def test_two_equal_ayat_entry_rejected(self):
        r = E.judge_entry(2, toks(T[2] + T[3]), T)
        self.assertEqual(r["verdict"], "reject", r)

    def test_nearest_with_margin_passes_despite_noise(self):
        heard = list(T[3])
        heard[3] = "فااء"
        r = E.judge_entry(3, toks(heard), T)
        self.assertEqual(r["verdict"], "pass", r)
        self.assertGreaterEqual(r["gap"], E.NEAREST_MARGIN)

    def test_identical_text_neighbour_is_not_a_rival(self):
        t = dict(T)
        t[9] = list(T[2])                       # آيةٌ نصُّها نصُّ 2 تماماً (‏جوارٌ بالمدى ±2 مع 8 و10)
        t[8] = list(T[6])
        self.assertEqual(E.rivals(9, t), [7, 8])        # 2 نفسُها نصّاً ليست منافِسة
        r = E.judge_entry(9, toks(T[2]), t)
        self.assertEqual(r["verdict"], "pass", r)

    def test_rivals_radius_is_two(self):
        t = {i: [f"ك{i}", f"ل{i}", f"م{i}"] for i in range(1, 9)}
        self.assertEqual(E.rivals(4, t), [2, 3, 5, 6])
        self.assertEqual(E.rivals(1, t), [2, 3])

    def test_far_ayah_is_not_a_rival(self):
        # نصُّ الآية 6 لا يُنافس الآية 2 (‏بُعدُ 4) ⇒ لا يُردّ المدخلُ بسببها
        t = {1: T[1], 2: T[2], 3: T[3], 6: T[2][:6] + ["ياء"]}
        self.assertNotIn(6, E.rivals(2, t))

    def test_unify_removes_diacritics_hamza_forms_and_tatweel(self):
        self.assertEqual(E._unify_ref(["أَلْمُلْكُ", "إِلَيْهِ", "آمَنَ", "مُؤْمِنُونَ", "شَيْءٍ", "ٱلْقُرْءَانَ", "تَبَـٰرَكَ"]),
                         E._unify_ref(["الملك", "اليه", "امن", "مومنون", "شي", "القران", "تبرك"]))
        self.assertEqual(E._unify("ى"), E._unify("ي"))

    def test_both_sides_unified_before_comparison(self):
        # مرجعٌ بالحركات والهمزات وتفريغٌ بدونها (‏وعكسُه) يتطابقان
        ref = {1: ["أَلْف", "بَاء", "جِيم", "دَال", "هَاء", "وَاو", "زَاي"], 2: T[2], 3: T[3]}
        r = E.judge_entry(1, toks(["الف", "باء", "جيم", "دال", "هاء", "واو", "زاي"]), ref)
        self.assertEqual(r["verdict"], "pass", r)
        r2 = E.judge_entry(1, toks(["أَلْف", "بَاء", "جِيم", "دَال", "هَاء", "وَاو", "زَاي"]),
                           {1: T[1], 2: T[2], 3: T[3]})
        self.assertEqual(r2["verdict"], "pass", r2)

    def test_confidence_constants_still_from_pin_heard(self):
        self.assertIs(E.MIN_WORD_P, E.PH.W_MIN_WORD_P)
        self.assertIs(E.MEAN_WORD_P, E.PH.W_MEAN_WORD_P)
        self.assertEqual((E.FUZZ_LO, E.FUZZ_HI), (E.PH.W_FUZZ_LEN_LO, E.PH.W_FUZZ_LEN_HI))


class Pairs(unittest.TestCase):
    class A:
        def __init__(self, pairs="", key="", surahs=""):
            self.pairs, self.key, self.surahs = pairs, key, surahs

    def test_parse_pairs(self):
        r = E._parse_pairs(self.A(pairs="timings/a/x.jz=1,2;timings/b/y.jz=3\ntimings/c/z.jz=4"))
        self.assertEqual(r, [("timings/a/x.jz", "1,2"), ("timings/b/y.jz", "3"), ("timings/c/z.jz", "4")])

    def test_single_key(self):
        self.assertEqual(E._parse_pairs(self.A(key="k", surahs="1")), [("k", "1")])

    def test_published_key_needs_flag(self):
        E._check_key("timings/qalun/x.jz", True)
        E._check_key("timings-staging/qalun/x.jz", False)
        for k, pub in (("timings/qalun/x.jz", False), ("timings-staging/qalun/x.jz", True),
                       ("timings/qalun/x/y.jz", True), ("timings/qalun/x.json", True), ("state/a/b.jz", True)):
            with self.assertRaises(SystemExit):
                E._check_key(k, pub)


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
