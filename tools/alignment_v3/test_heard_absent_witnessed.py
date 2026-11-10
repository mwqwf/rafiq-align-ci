#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختباراتُ توصيل «مسمّاةٌ غائبةٌ لكنّها مسموعةٌ» (‏ctc-absent-witnessed-1 · قرار القائد 2026-11-10) بباب `heard_absent`:
الاستثناءُ في `agreed_anchors` لا يُرخي إلا ما أثبتته `witnessed_exemptions` (‏بشاهدَي float32 والشروط كلِّها)، وكلُّ ما سواه يبقى
على ردّه القديم حرفاً. منطقُ الشروط نفسُه واختباراتُ تحوّره في `tools/index_qa/test_heard_witnessed_absent.py` (‏الحالةُ الحقيقيّة: الكردي س4 4:127).

    python -m unittest tools/alignment_v3/test_heard_absent_witnessed.py
"""
import copy
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "index_qa"))

import heard_absent as HA  # noqa: E402
import test_heard_witnessed_absent as W  # noqa: E402

E = HA.HeardAbsentError
S, A, N = W.S, W.A, W.N


def _rec(a, q=0.9):
    return {"anchorMs": [a * 10000, a * 10000 + 8000], "anchorQuality": q, "heardMs": None, "score": None, "occurrences": []}


def maps(absent_q=0.3):
    gm = {str(a): _rec(a) for a in range(1, N + 1) if a != A}
    gm[str(A)] = {"anchorMs": list(W.CLAIM), "anchorQuality": absent_q, "heardMs": None, "score": None,
                  "occurrences": [[5527000, 5540000, 0.514]]}
    rm = {str(a): _rec(a) for a in range(1, N + 1) if a != A}
    rm[str(A)] = {"anchorMs": None, "anchorQuality": None, "heardMs": None, "score": None, "occurrences": []}
    return gm, rm


def exempt(gm, rm, wits=None):
    return HA.witnessed_exemptions(S, N, [A], gm, rm, W._pair() if wits is None else wits, W.META, W.SHA, ref_words=W.ref)


class Wiring(unittest.TestCase):
    def test_old_refusal_without_witnesses(self):
        gm, rm = maps()
        with self.assertRaisesRegex(E, "مسمّاةٌ غائبةٌ لكنّها مسموعةٌ في خريطة العامّة"):
            HA.agreed_anchors(gm, rm, N, [A])

    def test_exemption_accepted_and_agreed_anchors_passes(self):
        gm, rm = maps()
        ok, refused = exempt(gm, rm)
        self.assertEqual(refused, {})
        self.assertEqual(sorted(ok), [A])
        self.assertEqual(ok[A]["mapQuality"], 0.3)
        out, notes = HA.agreed_anchors(gm, rm, N, [A], witnessed=set(ok))
        self.assertIsNone(out[A - 1])                              # بلا مِرساةٍ: الآيةُ تبقى غائبةً بلا مدخل
        self.assertIsNotNone(out[A - 2])
        self.assertIsNotNone(out[A])
        self.assertEqual(notes["disputed"], [])

    def test_exemption_only_for_proven_ayah(self):
        gm, rm = maps()
        ok, refused = exempt(gm, rm, wits={"run-a": W._wit("medium", own_head=True), "run-b": W._wit("small")})
        self.assertEqual(ok, {})
        self.assertIn("الآية الغائبة", refused[A])
        with self.assertRaisesRegex(E, "مسمّاةٌ غائبةٌ لكنّها مسموعةٌ"):
            HA.agreed_anchors(gm, rm, N, [A], witnessed=set(ok))

    def test_quality_half_not_exempted(self):
        gm, rm = maps(absent_q=0.5)
        ok, refused = exempt(gm, rm)
        self.assertEqual(ok, {})
        self.assertIn("الردُّ القديمُ باقٍ", refused[A])
        with self.assertRaisesRegex(E, "مسمّاةٌ غائبةٌ لكنّها مسموعةٌ"):
            HA.agreed_anchors(gm, rm, N, [A], witnessed=set(ok))

    def test_expected_duration_is_measured_from_peer_anchors(self):
        gm, rm = maps()
        ok, _ = exempt(gm, rm)                                             # الأقرانُ بـ8000م.ث ⇒ المتوقَّعُ ≈8000 والفجوةُ 3000 < 4000
        self.assertEqual(sorted(ok), [A])
        gm2, rm2 = maps()
        for a in range(1, N + 1):                                          # الأقرانُ بمدّةٍ قصيرةٍ ⇒ المتوقَّعُ صغيرٌ ⇒ تردّ الفجوةُ 3000
            if a != A:
                for m in (gm2, rm2):
                    m[str(a)]["anchorMs"][1] = a * 10000 + 400
        ok2, refused2 = exempt(gm2, rm2)
        self.assertEqual(ok2, {})
        self.assertIn("متّسعٌ", refused2[A])

    def test_strong_match_elsewhere_still_refuses_even_if_witnessed(self):
        gm, rm = maps()
        gm[str(A)]["occurrences"] = [[5527000, 5540000, 0.82]]
        ok, _ = exempt(gm, rm)
        self.assertEqual(sorted(ok), [A])
        with self.assertRaisesRegex(E, "مطابقةٌ قويّة"):
            HA.agreed_anchors(gm, rm, N, [A], witnessed=set(ok))

    def test_witnessed_set_must_be_named_ayahs(self):
        gm, rm = maps()
        with self.assertRaisesRegex(E, "غيرِ مسمّاة"):
            HA.agreed_anchors(gm, rm, N, [A], witnessed={A, 100})

    def test_unnamed_unheard_ayah_still_refused(self):
        gm, rm = maps()
        for m in (gm, rm):
            m["50"] = {"anchorMs": [1, 2], "anchorQuality": 0.05, "heardMs": None, "score": None, "occurrences": []}
        ok, _ = exempt(gm, rm)
        with self.assertRaisesRegex(E, "غائبٌ غيرُ مسمّى"):
            HA.agreed_anchors(gm, rm, N, [A], witnessed=set(ok))

    def test_no_candidates_means_no_exemption_needed(self):
        gm, rm = maps()
        gm[str(A)] = copy.deepcopy(rm[str(A)])
        ok, refused = exempt(gm, rm)
        self.assertEqual((ok, refused), ({}, {}))
        HA.agreed_anchors(gm, rm, N, [A])                          # يمرّ كما كان

    def test_first_last_and_quarter_guards_precede_everything(self):
        gm, rm = maps()
        for bad in ([1], [N], list(range(60, 105))):
            with self.assertRaises(E):
                HA.agreed_anchors(gm, rm, N, bad, witnessed={bad[0]})

    def test_second_ayah_candidate_still_needs_both_witnesses(self):
        gm, rm = maps()
        ok, refused = exempt(gm, rm, wits={"run-a": W._wit("medium")})
        self.assertEqual(ok, {})
        self.assertIn("شاهدان", refused[A])


if __name__ == "__main__":
    unittest.main()
