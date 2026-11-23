#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تكافؤ الألف الخنجريّة في مقارِن قصّ `--trim` (`_junction`) — حفص وورش سواء.

`common.norm` يحذف ٰ فتصير «الغَٰبرين» «الغبرين» بينما Whisper يكتب «الغابرين».
مسار المتنازَع (`disputed_norm_words`) يطوي ٰ←ا قبل norm؛ هذا الاختبار يثبت أنّ `_junction`
يستعمل التكافؤ نفسَه، وأنّ كلمةً مختلفةَ اللفظ تبقى مردودة. ⛔ لا عتبةَ تُغيَّر.

    python -m unittest tools/index_qa/test_pin_heard_trim_ortho.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import heard_gate as H                                           # noqa: E402
import pin_heard as P                                            # noqa: E402


def _wit(words, start=10000, model="medium"):
    ws = [{"w": w, "s": start + 400 * i, "e": start + 400 * i + 350, "p": 0.95} for i, w in enumerate(words)]
    return {"surah": 7, "riwaya": "warsh", "fileRef": "https://x/007.mp3", "sha256": "a" * 64,
            "model": model, "computeType": "float32",
            "ayahs": {"83": {"words": ws, "windowMs": [start - 5000, start + 400 * len(words) + 5000]}}}


class DaggerAlifSameForHafsAndWarsh(unittest.TestCase):
    def test_mushaf_words_fold_identically(self):
        for rw in ("hafs", "warsh"):
            self.assertEqual(H.disputed_ref_words(rw, 7, 83)[-1], "الغابرين", rw)
            self.assertEqual(H.disputed_ref_words(rw, 7, 113)[-1], "الغالبين", rw)
            self.assertEqual(H.disputed_ref_words(rw, 7, 72)[0], "فانجيناه", rw)
            # common.norm ما زال يحذف الخنجريّة — العطب في المقارِن السابق لا في norm نفسِه
            self.assertEqual(P.ref_words_for(rw, 7, 83)[-1], "الغبرين", rw)
            self.assertEqual(P.ref_words_for(rw, 7, 113)[-1], "الغلبين", rw)
            self.assertEqual(P.ref_words_for(rw, 7, 72)[0], "فانجينه", rw)

    def test_whisper_ghabirin_matches_folded_ref(self):
        """تفريغ «الغابرين» يطابق مرجع حفص وورش بعد طيّ ٰ (‏disputed_ref أو النص الخام)."""
        heard = ["كانت", "من", "الغابرين", "وامطرنا", "عليهم", "مطرا"]
        wit = _wit(heard)
        cases = (
            (H.disputed_ref_words("warsh", 7, 83), H.disputed_ref_words("warsh", 7, 84)),
            (H.disputed_ref_words("hafs", 7, 83), H.disputed_ref_words("hafs", 7, 84)),
            (["كانت", "من", "الْغَٰبِرِينَ"], ["وَأَمْطَرْنَا", "عليهم", "مطرا"]),
        )
        for ref_prev, ref_next in cases:
            b, info = P._junction(wit, ref_prev, ref_next)
            self.assertIsNotNone(b, (ref_prev[-1], info))
            self.assertEqual(b, 10000 + 400 * 3, info)

    def test_common_norm_refs_cannot_recover_stripped_alif(self):
        """المرجع بعد common.norm («الغبرين») لا يُستعاد منه الألف — لذا الإنتاج يمرّر disputed_ref_words."""
        heard = ["كانت", "من", "الغابرين", "وامطرنا", "عليهم", "مطرا"]
        b, info = P._junction(_wit(heard), P.ref_words_for("warsh", 7, 83), P.ref_words_for("warsh", 7, 84))
        self.assertIsNone(b)
        self.assertIn("لا موضع", info)

    def test_ghalibin_matches(self):
        heard = ["كنا", "نحن", "الغالبين", "قال", "نعم", "وانكم"]
        wit = _wit(heard)
        for rw in ("hafs", "warsh"):
            b, info = P._junction(wit, H.disputed_ref_words(rw, 7, 113), H.disputed_ref_words(rw, 7, 114))
            self.assertIsNotNone(b, (rw, info))
            self.assertEqual(b, 10000 + 400 * 3, info)


class GenuinelyDifferentWordsStillFail(unittest.TestCase):
    def test_missing_pronoun_hu_rejected(self):
        """فأنجينا ≠ فأنجيناه: سقوط هاء الضمير ليس تكافؤ رسم."""
        heard = ["معكم", "من", "المنتظرين", "فانجينا", "والذين", "معه"]
        wit = _wit(heard)
        for rw in ("hafs", "warsh"):
            b, info = P._junction(wit, H.disputed_ref_words(rw, 7, 71), H.disputed_ref_words(rw, 7, 72))
            self.assertIsNone(b, rw)
            self.assertIn("لا موضع", info)

        heard_ok = ["معكم", "من", "المنتظرين", "فانجيناه", "والذين", "معه"]
        wit_ok = _wit(heard_ok)
        for rw in ("hafs", "warsh"):
            b, info = P._junction(wit_ok, H.disputed_ref_words(rw, 7, 71), H.disputed_ref_words(rw, 7, 72))
            self.assertIsNotNone(b, (rw, info))

    def test_waladhina_vs_huwa_rejected(self):
        heard = ["معكم", "من", "المنتظرين", "فانجيناه", "هو", "الذين"]
        wit = _wit(heard)
        b, info = P._junction(wit, H.disputed_ref_words("warsh", 7, 71), H.disputed_ref_words("warsh", 7, 72))
        self.assertIsNone(b)
        self.assertIn("لا موضع", info)

    def test_qala_not_equal_qul(self):
        self.assertNotEqual(H.disputed_norm_words("قال"), H.disputed_norm_words("قل"))
        self.assertNotEqual(H.disputed_norm_words("مالك"), H.disputed_norm_words("ملك"))
        self.assertNotEqual(H.disputed_norm_words("كتاب"), H.disputed_norm_words("كتب"))
        self.assertNotEqual(H.disputed_norm_words("فانجينا"), H.disputed_norm_words("فانجيناه"))

    def test_no_alif_invented_when_dagger_absent(self):
        """كلمة بلا ألف خنجريّة لا تُزاد لها ألف (مالك ≠ ملك يبقى)."""
        self.assertEqual(H.disputed_norm_words("ملك"), ["ملك"])
        self.assertEqual(H.disputed_norm_words("قل"), ["قل"])
        self.assertNotEqual(H.disputed_norm_words("مَٰلِك"), H.disputed_norm_words("ملك"))
        self.assertEqual(H.disputed_norm_words("مَٰلِك"), ["مالك"])


class ThresholdsUntouched(unittest.TestCase):
    def test_thresholds_and_witness_count_unchanged(self):
        self.assertEqual(P.W_AGREE_MS, 300)
        self.assertEqual(P.W_MIN_WORD_P, 0.5)
        self.assertEqual(P.W_MEAN_WORD_P, 0.7)
        self.assertEqual(P.W_TRIM_MIN_WITNESSES, 2)
        self.assertEqual(P.W_K, 3)
        self.assertEqual(H.DISPUTED_MIN_WITNESSES, 2)
        self.assertEqual(H.DISPUTED_MAX_PCT, 10)


if __name__ == "__main__":
    unittest.main()
