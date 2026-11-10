#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختباراتُ توصيل «المرساة المزاحة داخل نصّ الآية» (‏#107) بالفحص المسبق داخل `pin_heard.pin` (‏2026-11-10).

كما في test_pin_heard_disputed: الفهرسُ الحقيقيّ لـ3siri س10 وخريطتُه الحقيقيّةُ مكمَّلةً بمراسٍ على المنشور للآيات غير المقيسة، وتُساوى مراسي
الآيات 4·5·50·55·70·71 بالمنشور (‏فلا تبقى منحرفة) كي يبقى 53 وحدَه يحتاج تثبيتاً و51 وحدَه (‏مرساتُها الحقيقيّةُ متأخّرةٌ 2462م.ث) يُدّعى؛
والشاهدان زوجٌ مركّبٌ (‏`T._pair` في test_heard_owntext). لاختبار التوصيل لا دليلاً على الفهرس.

    python -m unittest tools.index_qa.test_pin_heard_owntext
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import pin_heard as P                                            # noqa: E402
import test_heard_owntext as O                                   # noqa: E402
import test_pin_heard_disputed as D                              # noqa: E402

SURAH = 10
EQ = (4, 5, 50, 55, 70, 71)


def _run(own_claims, wits, hmap=None, disputed=None, pins=None):
    hmap = hmap or D._hmap(equalise=EQ)
    pins = pins or {53: int(hmap["heardMap"]["53"]["anchorMs"][0])}

    def check(probe, _rows, already=0):
        rec = P.own_text_claims(probe, SURAH, hmap, own_claims, "", wits=wits, already=already)
        return {int(k) for k in rec[str(SURAH)]}

    return P.pin(D._idx(), SURAH, hmap, pins, disputed=disputed, own_text=check)


class Wiring(unittest.TestCase):
    def test_without_claim_the_deviation_is_refused_as_before(self):
        hmap = D._hmap(equalise=EQ)
        with self.assertRaises(SystemExit) as c:
            P.pin(D._idx(), SURAH, hmap, {53: int(hmap["heardMap"]["53"]["anchorMs"][0])})
        self.assertIn("51", str(c.exception))
        self.assertIn("حكمُ السماع", str(c.exception))

    def test_proven_claim_passes_and_only_it(self):
        out, _report, changed = _run([51], O._pair())
        self.assertIn(53, changed)
        self.assertNotIn(51, changed)                        # ‏المزاحةُ لا يُمسّ بدؤها
        s51 = [e for e in out["entries"] if e["ayahId"] == "10:51"][0]
        self.assertEqual(s51["startMs"], O.T.start(51))

    def test_single_witness_refused(self):
        w = O._pair()
        w.pop("run-d")
        with self.assertRaises(SystemExit) as c:
            _run([51], w)
        self.assertIn("شاهدان", str(c.exception))

    def test_witness_head_outside_300ms_refused(self):
        w = {"run-c": O._wit("medium", 600), "run-d": O._wit("small", 980)}    # ‏مطلعا الشاهدين الحقيقيّين
        with self.assertRaises(SystemExit) as c:
            _run([51], w)
        self.assertIn("بعيدٌ عن المنشور", str(c.exception))

    def test_unclaimed_deviation_refused_even_with_a_proven_claim(self):
        h = D._hmap(equalise=(4, 5, 55, 70, 71))             # ‏50 تبقى منحرفةً وغيرَ مدّعاة
        with self.assertRaises(SystemExit) as c:
            _run([51], O._pair(), hmap=h)
        self.assertIn("50", str(c.exception))
        self.assertIn("حكمُ السماع", str(c.exception))

    def test_claim_on_an_ayah_that_is_not_deviant_refused(self):
        with self.assertRaises(SystemExit) as c:
            _run([51, 6], {k: O._wit(("medium", "small")[i], (100, 160)[i]) for i, k in enumerate(("run-c", "run-d"))})
        self.assertIn("ليست منحرفة", str(c.exception))

    def test_over_ten_percent_refused(self):
        with mock.patch.object(P, "heard_gate_n_ayahs", return_value=5):      # ‏1 من 5 = 20٪
            with self.assertRaises(SystemExit) as c:
                _run([51], O._pair())
        self.assertIn("10", str(c.exception))

    def test_cap_shared_with_disputed_in_the_precheck(self):
        h = D._hmap(equalise=(4, 5, 50, 70, 71))             # ‏51 مزاحةٌ و55 متنازَعةٌ و53 تُثبَّت
        dw = D._wits(("55",))
        d_claims = {55: 54}

        def dcheck(probe, _rows):
            rec = P.disputed_claims(probe, SURAH, h, d_claims, "", wits=dw)
            return {int(k) for k in rec[str(SURAH)]}
        with mock.patch.object(P, "heard_gate_n_ayahs", return_value=109):
            out, _r, changed = _run([51], O._pair(), hmap=h, disputed=dcheck)   # ‏2 من 109 يمرّ
        self.assertIn(53, changed)
        with mock.patch.object(P, "heard_gate_n_ayahs", return_value=19):       # ‏2 من 19 = 10.5٪ مجموعُهما
            with self.assertRaises(SystemExit) as c:
                _run([51], O._pair(), hmap=h, disputed=dcheck)
        self.assertIn("10", str(c.exception))

    def test_default_keeps_old_behaviour(self):
        hmap = D._hmap(equalise=EQ)
        with self.assertRaises(SystemExit):
            P.pin(D._idx(), SURAH, hmap, {53: int(hmap["heardMap"]["53"]["anchorMs"][0])}, own_text=None)


class Writes(unittest.TestCase):
    def test_own_text_claims_embeds_witnesses_and_prechecks(self):
        i = D._idx()
        rec = P.own_text_claims(i, SURAH, D._hmap(equalise=EQ), [51], "", wits=O._pair())
        self.assertEqual(sorted(rec["10"]["51"]["witnesses"]), ["run-c", "run-d"])
        self.assertEqual(set(rec["10"]["51"]), {"witnesses"})
        with self.assertRaises(SystemExit):
            P.own_text_claims(i, SURAH, D._hmap(equalise=EQ), [51], "1")          # تشغيلةٌ واحدة بلا wits
        with self.assertRaises(SystemExit):
            P.own_text_claims(i, SURAH, D._hmap(equalise=EQ), [50], "", wits=O._pair())  # ‏50 ليست منحرفة هنا

    def test_parse_ayahs(self):
        self.assertEqual(P.parse_ayahs("62, 51،14"), [14, 51, 62])
        self.assertEqual(P.parse_ayahs(""), [])


if __name__ == "__main__":
    unittest.main()
