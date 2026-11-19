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
    texts = {1: own_text.split(), 2: other_text.split()}
    ref = lambda s, a: H.disputed_cmp_words(" ".join(texts[a]))                  # noqa: E731
    wit = _wit(heard.split())
    anchor = 1000 + 400 * anchor_idx + 100
    with mock.patch.object(P, "check_witness", lambda *a, **k: None):
        return H.disputed_one(wit, 16, 1, 1000, anchor, 2, ref, None, "x")


class Norm(unittest.TestCase):
    def test_taa_heh_same(self):
        for a, b in [("وبنعمت", "وبنعمه"), ("وبنعمة", "وبنعمت"), ("نعمت", "نعمه")]:
            self.assertEqual(H.disputed_cmp_words(a), H.disputed_cmp_words(b), (a, b))

    def test_hamza_chair_same(self):
        self.assertEqual(H.disputed_norm_words("شيئا"), H.disputed_norm_words("شيا"))
        self.assertEqual(H.disputed_norm_words("مؤمن"), H.disputed_norm_words("مومن"))
        self.assertEqual(H.disputed_norm_words("أرأيتم"), H.disputed_norm_words("ارايتم"))

    def test_different_words_stay_different(self):
        for a, b in [("كتاب", "كتب"), ("مالك", "ملك"), ("قال", "قل"), ("رحمة", "رحم"),
                     ("بنعمه", "بنعمك"), ("شيء", "شي"), ("وبنعمت", "وبنعم")]:
            self.assertNotEqual(H.disputed_cmp_words(a), H.disputed_cmp_words(b), (a, b))

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
    def test_mutation_no_equivalence_fails(self):
        """بلا تكافؤ الرسم (‏التطبيعُ القديم وحده) تُردّ الحالتان فيسقط هذا الاختبار إن أُزيل التكافؤ."""
        with mock.patch.object(H, "rasm_equiv_word", lambda w: w), mock.patch.object(H, "_hamza_equiv_word", lambda w: w):
            ok_taa = H.disputed_cmp_words("وبنعمت") == H.disputed_cmp_words("وبنعمه")
            ok_hamza = H.disputed_norm_words("شيئا") == H.disputed_norm_words("شيا")
        self.assertFalse(ok_taa)
        self.assertFalse(ok_hamza)


if __name__ == "__main__":
    unittest.main()
