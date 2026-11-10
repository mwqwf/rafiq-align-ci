#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختباراتُ كتابة «الغياب المشهود» (‏`transform.witnessedAbsent` · `ctc-absent-witnessed-1`) في `drop_ayahs`، وأنّ `promote`
يقبل الإعلانَ SOURCE_TRUNCATED للآية وحدَها بقاعدة 10-31 (‏`declared_truncated_gaps`) — الحالةُ الحقيقيّة: الكردي س4 4:127.

    python -m unittest tools/index_qa/test_drop_ayahs_witnessed.py
"""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "alignment_v3"))

import drop_ayahs                                                # noqa: E402
import heard_gate as H                                           # noqa: E402
import promote                                                   # noqa: E402
import stage_transform                                           # noqa: E402
import test_heard_witnessed_absent as W                          # noqa: E402

S, A, N = W.S, W.A, W.N
EV = {"method": "ctc_window", "detail": "نافذةُ الجارتين 4:126/4:128 بنصّ الغائبة: لا صوتَ للآية (ثقة 0.2) · ctc-absent-witnessed-1"}


def _idx():
    """سورةُ 4 بلا 4:127 (‏بُنيت من المسموع وحده): المداخل 175 والغيابُ مسجَّلٌ بـsource_truncated."""
    ents = [{"ayahId": f"{S}:{a}", "startMs": a * 1000, "endMs": a * 1000 + 900, "fileRef": "f", "confBand": "HIGH"}
            for a in range(1, N + 1) if a != A]
    ids = [f"{S}:{A}"] + [f"{s}:{a}" for s in range(1, 115) if s != S for a in range(1, promote._AYAH_COUNTS[s - 1] + 1)]
    return {"riwaya": "hafs", "reciterId": "kurdi", "entries": ents, "ayahCount": 6236,
            "missing": {"count": len(ids), "byReason": {"source_truncated": 1, "unknown": len(ids) - 1}, "ids": sorted(
                ids, key=lambda x: tuple(int(p) for p in x.split(":")))}}


def _claims():
    return {str(A): {"witnesses": {r: H.disputed_src_rec(w) for r, w in W._pair().items()}, "detail": {"claimMs": W.CLAIM}}}


def _make(idx=None, witnessed="default", already=True, ayahs=(A,), **kw):
    args = dict(reason="قياس CTC", reason_user="تسجيلُ هذه السورة ينقصه بعضُ آياتها.", reason_code="SOURCE_TRUNCATED",
                from_sha="a" * 64, from_key="timings/hafs/kurdi.jz", already_absent=already,
                witnessed={str(S): _claims()} if witnessed == "default" else witnessed)
    args.update(kw)
    return drop_ayahs.drop_ayahs(idx or _idx(), {S: sorted(ayahs)}, {f"{S}:{a}": dict(EV) for a in ayahs}, **args)


class Accept(unittest.TestCase):
    def test_transform_carries_named_versioned_evidence(self):
        out = _make()
        tr = out["transform"]
        self.assertEqual(tr["witnessedAbsentVersion"], "ctc-absent-witnessed-1")
        self.assertEqual(sorted(tr["witnessedAbsent"][str(S)]), [str(A)])
        self.assertEqual(sorted(tr["witnessedAbsent"][str(S)][str(A)]["witnesses"]), ["run-a", "run-b"])

    def test_promote_accepts_the_declaration_for_the_ayah_alone(self):
        out = _make()
        ok, why = promote.declared_truncated_gaps(out, S)
        self.assertTrue(ok, why)
        self.assertEqual(out["transform"]["reasonCode"], "SOURCE_TRUNCATED")
        self.assertEqual(out["transform"]["truncatedGaps"][str(S)]["absent"], [A])
        self.assertEqual(out["transform"]["truncatedGaps"][str(S)]["reason"], "source_truncated")
        self.assertEqual(len(out["entries"]), N - 1)                      # لا مدخلَ حُذف: كانت غائبةً أصلاً
        self.assertEqual(len(out["entries"]) + out["missing"]["count"], 6236)

    def test_promote_refuses_when_evidence_missing(self):
        out = _make()
        del out["transform"]["truncatedGaps"][str(S)]["evidence"][f"{S}:{A}"]
        self.assertFalse(promote.declared_truncated_gaps(out, S)[0])

    def test_no_witnessed_leaves_transform_without_the_key(self):
        out = _make(witnessed=None)
        self.assertNotIn("witnessedAbsent", out["transform"])
        self.assertNotIn("witnessedAbsentVersion", out["transform"])
        self.assertTrue(promote.declared_truncated_gaps(out, S)[0])

    def test_old_witnessed_claims_of_other_surahs_are_carried(self):
        idx = _idx()
        idx["transform"] = {"op": "x", "witnessedAbsent": {"9": {"50": {"witnesses": {"r1": {}, "r2": {}}}}}}
        out = _make(idx)
        self.assertEqual(sorted(out["transform"]["witnessedAbsent"]), sorted(["9", str(S)]))


class Refuse(unittest.TestCase):
    def test_requires_already_absent(self):
        with self.assertRaisesRegex(SystemExit, "already-absent"):
            _make(already=False, idx=_idx())

    def test_claim_on_unnamed_ayah(self):
        cl = _claims()
        cl["100"] = cl.pop(str(A))
        with self.assertRaisesRegex(SystemExit, "غيرِ محجوبةٍ بالاسم"):
            _make(witnessed={str(S): cl})

    def test_single_witness(self):
        cl = _claims()
        cl[str(A)]["witnesses"].pop("run-b")
        with self.assertRaisesRegex(SystemExit, "شاهدان"):
            _make(witnessed={str(S): cl})

    def test_claim_for_surah_without_named_ayahs(self):
        with self.assertRaisesRegex(SystemExit, "غيرِ محجوبةٍ بالاسم"):
            _make(witnessed={"9": _claims()})

    def test_first_and_last_still_refused_by_the_tool(self):
        for a in (1, N):
            with self.assertRaises(SystemExit):
                _make(ayahs=(a,), witnessed=None)


class InheritedThroughStageTransform(unittest.TestCase):
    """(‏د · مراجعةُ القائد #108) تحويلٌ لاحقٌ يستبدل `transform` كلَّه: يجب أن يُورَّث `witnessedAbsent` مع إعلان الحجب."""

    def _child(self, parent):
        out = copy.deepcopy(parent)
        out["transform"] = {"op": "basmala_fix", "reason": "r"}          # كما يكتبه stage_transform
        return out

    def test_witnessed_absent_inherited_with_the_declaration(self):
        parent = _make()
        out = self._child(parent)
        stage_transform.inherit_truncated_gaps(parent, out, [])
        tr = out["transform"]
        self.assertEqual(tr["witnessedAbsent"], parent["transform"]["witnessedAbsent"])
        self.assertEqual(tr["witnessedAbsentVersion"], "ctc-absent-witnessed-1")
        self.assertTrue(promote.declared_truncated_gaps(out, S)[0])

    def test_without_witnessed_nothing_added(self):
        parent = _make(witnessed=None)
        out = self._child(parent)
        stage_transform.inherit_truncated_gaps(parent, out, [])
        self.assertNotIn("witnessedAbsent", out["transform"])

    def test_realigned_surah_drops_both_declaration_and_claims(self):
        parent = _make()
        out = self._child(parent)
        stage_transform.inherit_truncated_gaps(parent, out, [S])
        self.assertNotIn("witnessedAbsent", out["transform"])
        self.assertNotIn("truncatedGaps", out["transform"])

    def test_claim_outside_declared_absent_not_carried(self):
        parent = _make()
        parent["transform"]["witnessedAbsent"][str(S)]["100"] = parent["transform"]["witnessedAbsent"][str(S)].pop(str(A))
        out = self._child(parent)
        with self.assertRaisesRegex(SystemExit, "خارج المحجوب المعلَن"):
            stage_transform.inherit_truncated_gaps(parent, out, [])


if __name__ == "__main__":
    unittest.main()
