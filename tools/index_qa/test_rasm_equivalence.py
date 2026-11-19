#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختباراتُ تكافؤ الرسم وحده في مقارِن المتنازَع (`heard_gate.disputed_norm_words` ← `disputed_one`).

الحالتان الحقيقيّتان (‏النفيس · النحل 16:73): الرسمُ «وبنعمت» والتفريغُ «وبنعمه»؛ و«شيئا» مقابل «شيا».
⛔ لا عتبةَ ولا نسبةَ ولا شرطَ يتغيّر: كلمتان مختلفتا اللفظ تبقيان مختلفتين، وآيةٌ مختلفةُ النصّ تُردّ.
اختبارُ الطفرة: يُعطَّل التكافؤ فيسقط قبولُ الحالتين (‏`test_mutation_*`).

    python -m unittest tools/index_qa/test_rasm_equivalence.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import heard_gate as H                                           # noqa: E402
import pin_heard as P                                            # noqa: E402


def _wit(words, start=1000):
    """شاهدٌ مصطنعٌ بكلماتٍ مرتّبة كلٌّ بثقة 0.99 وفاصل 400م.ث؛ النافذةُ تحيط بها."""
    ws = [{"w": w, "s": start + 400 * i, "e": start + 400 * i + 350, "p": 0.99} for i, w in enumerate(words)]
    return {"ayahs": {"1": {"words": ws, "windowMs": [start - 5000, start + 400 * len(words) + 5000]}}}


def _run(own_text, other_text, heard, anchor_idx):
    raws = {1: own_text, 2: other_text}
    texts = {1: own_text.split(), 2: other_text.split()}
    ref = lambda s, a: H.disputed_norm_words(" ".join(texts[a]))                  # noqa: E731
    wit = _wit(heard.split())
    anchor = 1000 + 400 * anchor_idx + 100
    with mock.patch.object(P, "check_witness", lambda *a, **k: None):
        return H.disputed_one(wit, 16, 1, 1000, anchor, 2, ref, None, "x", raw_ref=lambda s, a: raws[a])


def _taa_eq(ref_raw, heard_word):
    """هل يكافئ تفريغُ heard_word كلمةَ المرجع الخامّ ref_raw بتكافؤ التاء المفتوحة (‏المرجعُ الخامّ وحدَه يؤهّل)؟"""
    ref = H.disputed_norm_words(ref_raw)
    q = H.open_taa_ref_words([ref_raw])
    return H.taa_fold_heard(H.disputed_norm_words(heard_word), q) == ref


class Norm(unittest.TestCase):
    def test_taa_listed_stems_accept(self):
        for a, b in [("وبنعمت", "وبنعمه"), ("رحمت", "رحمه"), ("وبنعمت", "وبنعمت"), ("بِنِعۡمَتِ", "بنعمه"), ("جَنَّتُ", "جنه")]:
            self.assertTrue(_taa_eq(a, b), (a, b))

    def test_alef_before_taa_rejected(self):
        for a, b in [("جنات", "جنه"), ("جَنَّٰتٍ", "جنه"), ("كلمات", "كلمه"), ("كَلِمَٰتُ", "كلمه")]:
            self.assertFalse(_taa_eq(a, b), (a, b))

    def test_allat_vs_allah_rejected(self):
        raw = H.disputed_raw_text("hafs", 53, 19)
        q = H.open_taa_ref_words([raw])
        self.assertEqual(q, set())
        ref = H.disputed_norm_words(raw)
        self.assertNotEqual(H.taa_fold_heard(H.disputed_norm_words("افرأيتم الله والعزى"), q), ref)
        self.assertFalse(_taa_eq("ٱللَّٰتَ", "الله"))
        self.assertFalse(_taa_eq("اللات", "الله"))

    def test_taa_unlisted_rejected(self):
        for a, b in [("قالت", "قاله"), ("كتبت", "كتبه"), ("فقالت", "فقاله"), ("ضربت", "ضربه"), ("هيهات", "هيهاه"), ("ذات", "ذاه"), ("ولات", "ولاه"), ("مرضات", "مرضاه")]:
            self.assertFalse(_taa_eq(a, b), (a, b))

    def test_heard_alone_never_activates(self):
        # المرجعُ «ه» (‏ليس في القائمة بالتاء) والتفريغُ «ت»: لا طيّ
        self.assertEqual(H.taa_fold_heard(["وبنعمه"], set()), ["وبنعمه"])
        self.assertEqual(H.taa_fold_heard(["نعمه"], H.open_taa_ref_words(["قالت"])), ["نعمه"])

    def test_stems_exist_in_mushaf_text(self):
        import re as _re
        sys.path.insert(0, str(P._REPO_ROOT / "tools" / "alignment"))
        from common import load_text, norm
        words = {norm(w) for a in load_text("hafs") for w in a.split()}
        for st in H.OPEN_TAA_STEMS:
            self.assertTrue(any(st in H._prefix_strips(w) for w in words), st)
        self.assertEqual(len(H.OPEN_TAA_STEMS), 14)

    def test_hamza_chair_same(self):
        self.assertEqual(H.disputed_norm_words("شيئا"), H.disputed_norm_words("شيا"))
        self.assertEqual(H.disputed_norm_words("مؤمن"), H.disputed_norm_words("مومن"))
        self.assertEqual(H.disputed_norm_words("أرأيتم"), H.disputed_norm_words("ارايتم"))

    def test_different_words_stay_different(self):
        for a, b in [("كتاب", "كتب"), ("مالك", "ملك"), ("قال", "قل"), ("رحمة", "رحم"),
                     ("بنعمه", "بنعمك"), ("شيء", "شي")]:
            self.assertNotEqual(H.disputed_norm_words(a), H.disputed_norm_words(b), (a, b))
        self.assertFalse(_taa_eq("وبنعمت", "وبنعم"))

    def test_word_count_unchanged(self):
        self.assertEqual(len(H.disputed_norm_words("وبنعمت الله شيئا ءامنوا")), 4)


class Disputed(unittest.TestCase):
    OWN = "وبنعمت الله هم يكفرون"
    OTHER = "ثم ينكرونها وأكثرهم الكافرون"

    def test_16_73_taa_accepts(self):
        why, d = _run(self.OWN, self.OTHER, "وبنعمه الله هم يكفرون ثم ينكرونها وأكثرهم الكافرون", 5)
        self.assertIsNone(why, why)
        self.assertEqual(d["headMs"], 1000)

    def test_16_73_shay_accepts(self):
        why, d = _run("شيئا ولا يستطيعون هم", self.OTHER, "شيا ولا يستطيعون هم ثم ينكرونها وأكثرهم الكافرون", 5)
        self.assertIsNone(why, why)

    def test_different_ayah_text_rejected(self):
        why, d = _run(self.OWN, self.OTHER, "وبنعمك الله هم يكفرون ثم ينكرونها وأكثرهم الكافرون", 5)
        self.assertIsNotNone(why)
        self.assertIsNone(d)

    def test_different_word_rejected_in_head(self):
        why, _ = _run("شيئا ولا يستطيعون هم", self.OTHER, "شي ولا يستطيعون هم ثم ينكرونها وأكثرهم الكافرون", 5)
        self.assertIsNotNone(why)

    def test_anchor_text_not_other_ayah_rejected(self):
        why, _ = _run(self.OWN, self.OTHER, "وبنعمه الله هم يكفرون ثم يكفرونها وأكثرهم الكافرون", 5)
        self.assertIsNotNone(why)


class Mutation(unittest.TestCase):
    def test_mutation_empty_list_fails_acceptance(self):
        """تفريغُ القائمة يُسقط قبولَ «وبنعمت»/«رحمت»؛ وتعطيلُ الهمزة يُسقط «شيئا»."""
        with mock.patch.object(H, "OPEN_TAA_STEMS", frozenset()):
            self.assertFalse(_taa_eq("وبنعمت", "وبنعمه"))
            self.assertFalse(_taa_eq("رحمت", "رحمه"))
            why, _ = _run("وبنعمت الله هم يكفرون", "ثم ينكرونها وأكثرهم الكافرون",
                          "وبنعمه الله هم يكفرون ثم ينكرونها وأكثرهم الكافرون", 5)
            self.assertIsNotNone(why)
        with mock.patch.object(H, "_hamza_equiv_word", lambda w: w):
            self.assertNotEqual(H.disputed_norm_words("شيئا"), H.disputed_norm_words("شيا"))


if __name__ == "__main__":
    unittest.main()
