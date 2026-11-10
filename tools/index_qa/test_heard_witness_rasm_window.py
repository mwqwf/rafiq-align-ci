#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختباراتُ مقارِن الشاهد في بوّابة السماع: الرسمُ المسمّى وامتدادُ آخر كلمةٍ مقطوعة (‏قرار القائد 2026-11-10 · nasser_almajed.a70a43a0 س6).

الحالةُ: ردّت البوّابةُ س6 «بلا شاهد Whisper يشهد لنصّها (الآيتان 72,73)»:
  6:72 «وأن أقيموا الصلاة» مسموعةٌ صحيحة والمصحفُ «الصلوه» (‏بعد norm) فسقط التطابقُ الحرفيّ؛
  6:73 قصّت نافذةُ البوّابة آخرَ كلمةٍ فخرجت «الخبي» بينما نافذةٌ أطول أعطت «الخبير» بثقة 0.99.
⚠ بدءا الآيتين (‏1276532 · 1284157) من سجلّ تثبيت nasser؛ أمّا كلماتُ التفريغ وأزمنتُها فمُعاد بناؤها من وصف الحالة
(‏ملفُّ الشاهد الأصليّ ليس في المستودع) على نصّ المصحف الحقيقيّ المحمَّل من المستودع."""
import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import heard_gate as H  # noqa: E402
import pin_heard as PH  # noqa: E402

SHA, REF, S = "a" * 64, "https://x/006.mp3", 6
GMAP = {"sha256": SHA, "fileRef": REF}
START72, START73 = 1276532, 1284157


def W(w, s, e, p=0.9):
    return {"w": w, "s": s, "e": e, "p": p}


def seq(words, start, step=450, p=0.9):
    return [W(w, start + i * step, start + i * step + 350, p) for i, w in enumerate(words)]


WORDS72 = ["وأن", "أقيموا", "الصلاة", "واتقوه", "وهو", "الذي", "إليه", "تحشرون"]
WORDS73 = ["وهو", "الذي", "خلق", "السماوات", "والأرض", "بالحق", "ويوم", "يقول", "كن", "فيكون", "قوله", "الحق", "وله",
           "الملك", "يوم", "ينفخ", "في", "الصور", "عالم", "الغيب", "والشهادة", "وهو", "الحكيم", "الخبي"]
WIN73_END = 1296000


def nasser(last73="الخبي", e73=WIN73_END, sib=True, sib_word="الخبير", sib_p=0.99, sib_s_shift=20, sib_e=1296600,
           sib_win_hi=1308000, win73_end=WIN73_END):
    w73 = seq(WORDS73[:-1], START73) + [W(last73, 1295700, e73, 0.9)]
    ays = {"72": {"windowMs": [START72 - 3000, START72 + 6000], "words": seq(WORDS72, START72)},
           "73": {"windowMs": [START73 - 3000, win73_end], "words": w73}}
    if sib:                                   # نافذةٌ أطول لآيةٍ تالية في الشاهد نفسِه تغطّي ذيل 73
        ays["74"] = {"windowMs": [1293000, sib_win_hi],
                     "words": [W(sib_word, 1295700 + sib_s_shift, sib_e, sib_p), W("وهو", 1296800, 1297100)]}
    return {"surah": S, "riwaya": "hafs", "fileRef": REF, "sha256": SHA, "model": "medium", "computeType": "float32",
            "ayahs": ays}


def ev(wit, ayahs=(72, 73), ref_words=None):
    return H._witness_eval(wit, S, GMAP, SHA, "hafs", {72: START72, 73: START73}, list(ayahs), ref_words)


def _norm(t):
    return PH._norm_words([{"w": t, "s": 0, "p": 1}])


class RealNasser(unittest.TestCase):
    def test_baseline_raw_comparator_rejects_both(self):
        """الشاهدُ الخامُ عند `pin_heard._whisper_check` (‏لا يُمسّ) يردّ الآيتين — هذا هو العطب."""
        w = nasser()
        for a, st in ((72, START72), (73, START73)):
            hm = {"heardMap": {str(a): {"anchorMs": [st, st + 1]}}}
            c, _ = PH._whisper_check(w, hm, S, a, PH.ref_words_for("hafs", S, a), fuzzy=False)
            self.assertIsNone(c, a)

    def test_both_ayahs_accepted(self):
        res, bad = ev(nasser())
        self.assertIsNone(bad)
        self.assertTrue(res[72][0], res[72][1])
        self.assertTrue(res[73][0], res[73][1])

    def test_ayah72_accepted_alone_via_rasm(self):
        res, _ = ev(nasser(sib=False), ayahs=(72,))
        self.assertTrue(res[72][0], res[72][1])

    def test_ayah73_rejected_without_longer_window(self):
        res, _ = ev(nasser(sib=False), ayahs=(73,))
        self.assertFalse(res[73][0])


class RasmClosedList(unittest.TestCase):
    REF = ["وان", "اقيموا", "الكلوه", "واتقوه", "وهو", "الذي", "اليه", "تحشرون"]

    def _one(self, third, refw=None):
        words = ["وأن", "أقيموا", third, "واتقوه", "وهو", "الذي", "إليه", "تحشرون"]
        w = nasser(sib=False)
        w["ayahs"]["72"]["words"] = seq(words, START72)
        r = list(refw or self.REF)
        return ev(w, ayahs=(72,), ref_words=lambda *_a: r)[0][72]

    def test_out_of_list_word_one_letter_apart_rejected(self):
        """«الكلوه» ليست في القائمة: «الكلاه» تُردّ ولو اختلفت بحرفٍ واحدٍ على نهج الصلوة/الصلاة."""
        self.assertFalse(self._one("الكلاة")[0])
        self.assertTrue(self._one("الكلوة")[0])          # الكلمةُ نفسُها تمرّ (‏لا فرقَ أصلاً)

    def test_listed_word_one_letter_apart_rejected(self):
        """وكلمةٌ قريبةٌ من المسمّاة (‏الصلات ≠ الصلاة) لا تُوحَّد."""
        real = PH.ref_words_for("hafs", S, 72)
        self.assertFalse(self._one("الصلات", real)[0])
        self.assertTrue(self._one("الصلاة", real)[0])

    def test_named_forms_unify(self):
        for modern, mushaf in H.RASM_FORMS.items():
            w = {"surah": S, "ayahs": {"1": {"words": [W(modern, 1, 2)]}}}
            self.assertEqual(H.rasm_unify_wit(w)["ayahs"]["1"]["words"][0]["w"], mushaf)

    def test_closed_list_covers_the_eight_named_words(self):
        mushaf = set(H.RASM_FORMS.values())
        for must in ("الصلوه", "الزكوه", "الحيوه", "مشكوه", "النجوه", "الغدوه", "منوه", "الربوا"):
            self.assertIn(must, mushaf)

    def test_fragmented_token_not_unified(self):
        w = {"surah": S, "ayahs": {"1": {"words": [W("الصلاة والزكاة", 1, 2)]}}}
        self.assertEqual(H.rasm_unify_wit(w)["ayahs"]["1"]["words"][0]["w"], "الصلاة والزكاة")

    def test_no_leak_into_other_comparators(self):
        """التوحيدُ في مقارِن الشاهد وحدَه: مقارِنُ المتنازَع (‏`disputed_norm_words`) و`norm` على حالهما."""
        self.assertNotEqual(H.disputed_norm_words("الصلاة"), H.disputed_norm_words("الصلوة"))
        self.assertNotEqual(_norm("الصلاة"), _norm("الصلوة"))


class ExtendCutWord(unittest.TestCase):
    """كلُّ شرطٍ من E1–E6 وحدَه على `extend_cut_last_word` مباشرةً (‏الكلماتُ تُرجَع كما هي إن لم يكتمل)."""
    REF = ["وهو", "الحكيم", "الخبير"]

    def run_(self, **kw):
        w = H.rasm_unify_wit(nasser(**kw))
        before = list(w["ayahs"]["73"]["words"])
        out = H.extend_cut_last_word(w, 73, self.REF)
        return before, out

    def test_extends_when_all_conditions_hold(self):
        before, out = self.run_()
        self.assertEqual(out[:-1], before[:-1])
        self.assertEqual(out[-1]["w"], "الخبير")
        self.assertEqual(out[-1]["p"], 0.99)

    def test_E1_cut_word_not_a_prefix_rejected(self):
        before, out = self.run_(last73="الخبر")           # ليست بادئةً من «الخبير»
        self.assertEqual(out, before)

    def test_E1_complete_word_not_replaced(self):
        before, out = self.run_(last73="الخبير")          # كاملةٌ أصلاً: لا شيءَ يُمدّ
        self.assertEqual(out, before)

    def test_E2_not_adjacent_to_window_edge_rejected(self):
        before, out = self.run_(e73=WIN73_END - 1000)
        self.assertEqual(out, before)

    def test_E3_cap_one_second_rejected(self):
        before, out = self.run_(sib_e=WIN73_END + 1500)
        self.assertEqual(out, before)

    def test_E3_same_start_rejected(self):
        before, out = self.run_(sib_s_shift=400)          # قراءةٌ تبدأ في موضعٍ آخر لا هي نفسُ الكلمة
        self.assertEqual(out, before)

    def test_E4_not_literal_full_match_rejected(self):
        before, out = self.run_(sib_word="الخبيث")        # بادئتُها «الخبي» لكنّها ليست «الخبير»
        self.assertEqual(out, before)

    def test_E5_low_confidence_rejected(self):
        before, out = self.run_(sib_p=0.3)
        self.assertEqual(out, before)

    def test_E6_sibling_window_must_reach_past_edge(self):
        before, out = self.run_(sib_win_hi=WIN73_END - 500)   # نافذةٌ لا تتجاوز حدَّ نافذة 73 ليست «أطول»
        self.assertEqual(out, before)

    def test_no_sibling_unchanged(self):
        before, out = self.run_(sib=False)
        self.assertEqual(out, before)


class FuzzyStaysOff(unittest.TestCase):
    def test_fuzzy_false_always(self):
        seen = []

        def spy(wit, hm, surah, a, ref, fuzzy=False):
            seen.append(fuzzy)
            return None, "x"
        with mock.patch.object(PH, "_whisper_check", spy):
            ev(nasser())
        self.assertEqual(seen, [False, False])


if __name__ == "__main__":
    unittest.main()
