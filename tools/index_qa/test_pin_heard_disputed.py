#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختباراتُ توصيل «المرساة المتنازَع عليها» (#101) بالفحص المسبق داخل `pin_heard.pin` (‏2026-11-10).

كان `pin()` يردّ أيَّ صفٍّ منحرف قبل أن يصل `--disputed` إلى حكمه، فلا يجتمع تثبيتٌ مع آيةٍ متنازَعةٍ باقية.
والتصحيحُ: يُستثنى **المدّعى المثبَتُ وحدَه** بـ`heard_gate.disputed_verdict` بشروطه الستّة وسقفِ 10٪، وكلُّ ادّعاءٍ
لم يثبت يُردّ بسببه، وأيُّ انحرافٍ غير مدّعى يُردّ كما كان.

التجهيزُ: الفهرسُ الحقيقيّ لـ3siri س10 (‏bc63afc4) وخريطةُ float32 الحقيقيّة 42756633030 والشاهدُ الحقيقيّ 42756381986،
**مع تعديلٍ مُعلَن**: تُكمَل الخريطةُ الجزئيّةُ بمراسٍ على المنشور للآيات غير المقيسة، وتُساوى مراسي الآيات 4·5·50·51·70·71 بالمنشور (‏فلا تبقى منحرفة) كي يبقى 53 وحدَه يحتاج تثبيتاً و55 وحدَه
يُدّعى؛ والشاهدُ زوجٌ مركّبٌ كما في test_heard_disputed (‏انظر `_pair`). لاختبار التوصيل لا دليلاً على الفهرس.

    python -m unittest tools.index_qa.test_pin_heard_disputed
"""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import heard_gate as H                                           # noqa: E402
import pin_heard as P                                            # noqa: E402
import test_heard_disputed as T                                  # noqa: E402

SURAH = 10
EQUALISED = (4, 5, 50, 51, 70, 71)
PIN = {53: None}                                                  # ‏المرساةُ تُملأ من الخريطة


def _hmap(equalise=EQUALISED):
    """الخريطةُ الحقيقيّة وقد أُسقطت مراسي `equalise` على بدء المنشور."""
    h = copy.deepcopy(T.HMAP)
    for e in T.ENTS["entries"]:                              # ‏الخريطةُ الحقيقيّة جزئيّة (18/109)؛ تُكمَل بمراسٍ على المنشور
        a = int(e["ayahId"].split(":")[1])                   # ‏حتى لا يردّ شرطُ «المقيس أقلّ من النصف» ما ليس موضوعَ الاختبار
        if str(a) not in h["heardMap"]:
            h["heardMap"][str(a)] = {"anchorMs": [e["startMs"], e["startMs"] + 4000], "anchorQuality": 0.8,
                                     "occurrences": [[e["startMs"], e["startMs"] + 4000, 0.8]]}
    for a in equalise:
        st = T.start(a)
        rec = h["heardMap"][str(a)]
        rec["anchorMs"] = [st, st + 4000]
        rec["occurrences"] = [[st, st + 4000, rec.get("anchorQuality", 0.8)]]
    return h


def _idx():
    return {"riwaya": "hafs", "reciterId": "3siri", "entries": copy.deepcopy(T.ENTS["entries"]),
            "audioSha256": [T.SHA] * 114, "engineVersion": "x"}


def _wits(claims=("55",)):
    """زوجٌ مركّبٌ لآياتٍ مدّعاة (‏بدل `_pair` لآيةٍ واحدة): كلُّ آيةٍ من الشاهد الحقيقيّ."""
    a = copy.deepcopy(T.WIT)
    a["ayahs"] = {k: a["ayahs"][k] for k in claims}
    for rec in a["ayahs"].values():
        for w in rec["words"]:
            if w["w"] == "ألا" and w["s"] == 1545744:
                w["p"] = 0.9
    b = copy.deepcopy(a)
    b["model"] = "small"
    for rec in b["ayahs"].values():
        for w in rec["words"]:
            w["s"] += 40
            w["e"] += 40
    return {"run-a": a, "run-b": b}


def _run(claims, wits, hmap=None, pins=None):
    hmap = hmap or _hmap()
    pins = pins or {53: T.anchor(53) if False else int(hmap["heardMap"]["53"]["anchorMs"][0])}

    def check(probe, _rows):
        rec = P.disputed_claims(probe, SURAH, hmap, claims, "", wits=wits)
        return {int(k) for k in rec[str(SURAH)]}

    return P.pin(_idx(), SURAH, hmap, pins, disputed=check)


class Wiring(unittest.TestCase):
    def test_without_claim_the_remaining_deviation_is_refused_as_before(self):
        with self.assertRaises(SystemExit) as c:
            P.pin(_idx(), SURAH, _hmap(), {53: int(_hmap()["heardMap"]["53"]["anchorMs"][0])})
        self.assertIn("55", str(c.exception))
        self.assertIn("حكمُ السماع", str(c.exception))

    def test_proven_claim_passes_and_only_it(self):
        out, report, changed = _run({55: 54}, _wits())
        self.assertIn(53, changed)
        self.assertNotIn(55, changed)                       # ‏المتنازَعة لا يُمسّ بدؤها
        s55 = [e for e in out["entries"] if e["ayahId"] == "10:55"][0]
        self.assertEqual(s55["startMs"], T.start(55))

    def test_single_witness_refused(self):
        w = _wits()
        w.pop("run-b")
        with self.assertRaises(SystemExit) as c:
            _run({55: 54}, w)
        self.assertIn("شاهدان", str(c.exception))

    def test_witness_head_outside_300ms_refused(self):
        w = _wits()
        for r in w.values():                                 # ‏يُزاح الشاهدان معاً فيبعد المطلعُ عن المنشور
            for rec in r["ayahs"].values():
                for x in rec["words"]:
                    x["s"] -= 400
                    x["e"] -= 400
        with self.assertRaises(SystemExit) as c:
            _run({55: 54}, w)
        self.assertIn("بعيدٌ عن المنشور", str(c.exception))

    def test_anchor_inside_own_text_is_repetition_not_dispute(self):
        # ‏10:4 الحقيقيّة: المرساةُ على تكرار «إليه مرجعكم جميعاً» = نصُّ الآية نفسِها. تُترك 4 على مرساتها الحقيقيّة منحرفةً وتُدّعى.
        h = _hmap(equalise=(5, 50, 51, 70, 71))
        w = _wits(("55", "4"))
        with self.assertRaises(SystemExit) as c:
            _run({55: 54, 4: 3}, w, hmap=h)
        self.assertIn("تكرار", str(c.exception))

    def test_unclaimed_deviation_refused_even_with_a_proven_claim(self):
        h = _hmap(equalise=(4, 5, 51, 70, 71))               # ‏50 تبقى منحرفةً وغيرَ مدّعاة
        with self.assertRaises(SystemExit) as c:
            _run({55: 54}, _wits(), hmap=h)
        self.assertIn("50", str(c.exception))
        self.assertIn("حكمُ السماع", str(c.exception))

    def test_over_ten_percent_refused(self):
        with mock.patch.object(P, "heard_gate_n_ayahs", return_value=5):      # ‏1 من 5 = 20٪ > 10٪
            with self.assertRaises(SystemExit) as c:
                _run({55: 54}, _wits())
        self.assertIn("10", str(c.exception))

    def test_claim_on_an_ayah_that_is_not_deviant_refused(self):
        with self.assertRaises(SystemExit) as c:
            _run({55: 54, 6: 5}, _wits())
        self.assertIn("ليست منحرفة", str(c.exception))

    def test_default_keeps_old_behaviour(self):
        # ‏`disputed=None` يردّ المنحرفَ الباقي كما كان حرفاً
        with self.assertRaises(SystemExit):
            P.pin(_idx(), SURAH, _hmap(), {53: int(_hmap()["heardMap"]["53"]["anchorMs"][0])}, disputed=None)


if __name__ == "__main__":
    unittest.main()
