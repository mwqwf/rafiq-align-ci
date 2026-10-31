#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختباراتُ «حجب آياتٍ غائبةٍ في الوسط» (أمر المالك 2026-10-31): أداةُ `drop_ayahs` والباب الثالث
`promote.declared_truncated_gaps` وتوريثُه في `stage_transform`.

    python -m unittest tools/index_qa/test_drop_ayahs.py
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
import promote                                                   # noqa: E402
import stage_transform                                           # noqa: E402

S, N = 79, 46                      # النازعات: 46 آية، الربعُ = 11
EV = {"method": "ctc_window", "detail": "نافذة الجارتين: لا صوتَ للآية، ثقة 0.9"}


def _idx():
    ents = [{"ayahId": f"{S}:{a}", "startMs": a * 1000, "endMs": a * 1000 + 900,
             "fileRef": "f", "confBand": "HIGH"} for a in range(1, N + 1)]
    return {"riwaya": "hafs", "reciterId": "x", "entries": ents, "ayahCount": 6236,
            "missing": {"count": 6236 - N, "byReason": {"unknown": 6236 - N},
                        "ids": [f"{s}:{a}" for s in range(1, 115) if s != S
                                for a in range(1, promote._AYAH_COUNTS[s - 1] + 1)]}}


def _ev(absent):
    return {f"{S}:{a}": dict(EV) for a in absent}


def _make(absent=(15, 17, 18), **kw):
    args = dict(reason="قياس CTC", reason_user="تسجيلُ هذه السورة ينقصه بعضُ آياتها.",
                reason_code="SOURCE_TRUNCATED", from_sha="a" * 64, from_key="timings/hafs/x.jz")
    args.update(kw)
    ev = args.pop("evidence", _ev(absent))
    return drop_ayahs.drop_ayahs(_idx(), {S: sorted(absent)}, ev, **args)


class Accept(unittest.TestCase):
    def test_accepted_and_boundaries_untouched(self):
        out = _make()
        ok, why = promote.declared_truncated_gaps(out, S)
        self.assertTrue(ok, why)
        src = {e["ayahId"]: e for e in _idx()["entries"]}
        self.assertEqual(len(out["entries"]), N - 3)
        for e in out["entries"]:
            self.assertEqual(e, src[e["ayahId"]])        # startMs/endMs لم يتغيّرا
        for a in (15, 17, 18):
            self.assertIn(f"{S}:{a}", out["missing"]["ids"])
        self.assertEqual(out["missing"]["byReason"]["source_truncated"], 3)
        tr = out["transform"]
        self.assertIn(f"declare_gap:{S}", tr["op"])
        self.assertEqual(tr["reasonCode"], "SOURCE_TRUNCATED")
        self.assertEqual(tr["truncatedGaps"][str(S)]["absent"], [15, 17, 18])
        self.assertEqual(len(out["entries"]) + out["missing"]["count"], 6236)

    def test_parse_ayahs(self):
        self.assertEqual(drop_ayahs.parse_ayahs("79:15, 79:17,79:18"), {79: [15, 17, 18]})
        with self.assertRaises(SystemExit):
            drop_ayahs.parse_ayahs("79:15,79:15")
        with self.assertRaises(SystemExit):
            drop_ayahs.parse_ayahs("79:99")

    def test_quarter_boundary_accepted(self):
        out = _make(absent=tuple(range(2, 13)))          # 11 = ربع 46 (عدداً صحيحاً)
        self.assertTrue(promote.declared_truncated_gaps(out, S)[0])


class RejectTool(unittest.TestCase):
    def test_no_evidence(self):
        with self.assertRaises(SystemExit):
            _make(evidence={f"{S}:15": dict(EV), f"{S}:17": dict(EV)})
        with self.assertRaises(SystemExit):
            _make(evidence={**_ev((15, 17, 18)), f"{S}:18": {"method": "guess", "detail": "x"}})

    def test_first_or_last(self):
        for bad in ((1, 5), (5, N)):
            with self.assertRaises(SystemExit):
                _make(absent=bad)

    def test_over_quarter(self):
        with self.assertRaises(SystemExit):
            _make(absent=tuple(range(2, 14)))            # 12 > ربع

    def test_no_reason_user_or_banned_or_code(self):
        with self.assertRaises(SystemExit):
            _make(reason_user="")
        with self.assertRaises(SystemExit):
            _make(reason_user="بأمر المالك")
        with self.assertRaises(SystemExit):
            _make(reason_code="OTHER")

    def test_surah_not_complete_in_source(self):
        idx = _idx()
        idx["entries"] = [e for e in idx["entries"] if e["ayahId"] != f"{S}:20"]
        idx["missing"]["ids"].append(f"{S}:20"); idx["missing"]["count"] += 1
        with self.assertRaises(SystemExit):
            drop_ayahs.drop_ayahs(idx, {S: [15]}, _ev([15]), reason="r", reason_user="u",
                                  reason_code="SOURCE_TRUNCATED", from_sha="a", from_key="k")


class RejectPromote(unittest.TestCase):
    def setUp(self):
        self.out = _make()

    def bad(self, mut):
        o = copy.deepcopy(self.out)
        mut(o)
        ok, why = promote.declared_truncated_gaps(o, S)
        self.assertFalse(ok, why)
        return why

    def test_no_evidence(self):
        self.bad(lambda o: o["transform"]["truncatedGaps"][str(S)]["evidence"].pop(f"{S}:17"))

    def test_first_last(self):
        def m(o):
            o["transform"]["truncatedGaps"][str(S)]["absent"] = [1, 15, 17, 18]
        self.bad(m)
        def m2(o):
            o["transform"]["truncatedGaps"][str(S)]["absent"] = [15, 17, 18, N]
        self.bad(m2)

    def test_entries_mismatch(self):
        self.bad(lambda o: o["entries"].pop(3))                          # مدخلٌ ناقصٌ غيرُ معلَن
        self.bad(lambda o: o["entries"].append({"ayahId": f"{S}:15", "startMs": 1, "endMs": 2}))

    def test_absent_not_in_missing(self):
        self.bad(lambda o: o["missing"]["ids"].remove(f"{S}:17"))
        def m(o):
            o["missing"]["byReason"]["source_truncated"] = 2
        self.bad(m)

    def test_over_quarter(self):
        o = _make(absent=tuple(range(2, 13)))
        o["transform"]["truncatedGaps"][str(S)]["absent"].append(13)
        self.assertFalse(promote.declared_truncated_gaps(o, S)[0])

    def test_no_user_declaration(self):
        self.bad(lambda o: o["transform"].pop("reasonUser"))
        self.bad(lambda o: o["transform"].update(reasonCode="OTHER"))
        self.bad(lambda o: o["transform"].update(op="drop_ayahs"))

    def test_changed_reason_and_dup(self):
        self.bad(lambda o: o["transform"]["truncatedGaps"][str(S)].update(reason="x"))
        self.bad(lambda o: o["transform"]["truncatedGaps"][str(S)].update(absent=[15, 15, 17]))
        self.bad(lambda o: o["transform"]["truncatedGaps"][str(S)].update(absent=[]))

    def test_tail_and_gap_not_together(self):
        self.bad(lambda o: o["transform"].update(truncatedTail={str(S): {"published": 40}}))

    def test_remaining_start_untouched(self):
        orig = drop_ayahs.drop_ayahs
        # الأداةُ ترفض أيَّ تغييرٍ لمدخلٍ باقٍ، وهنا يبقى startMs كما هو
        idx = _idx()
        out = orig(idx, {S: [15]}, _ev([15]), reason="r", reason_user="u",
                   reason_code="SOURCE_TRUNCATED", from_sha="a", from_key="k")
        self.assertEqual(out["entries"][0]["startMs"], idx["entries"][0]["startMs"])


class Inherit(unittest.TestCase):
    def test_inherited_after_other_transform(self):
        parent = _make()
        out = copy.deepcopy(parent)
        out["transform"] = {"op": "basmala_fix", "reason": "r"}      # كما يكتبه stage_transform
        out["transform"].pop("truncatedGaps", None)
        self.assertFalse(promote.declared_truncated_gaps(out, S)[0])
        stage_transform.inherit_truncated_gaps(parent, out, [])
        self.assertTrue(promote.declared_truncated_gaps(out, S)[0])
        self.assertIn(f"declare_gap:{S}", out["transform"]["op"])

    def test_not_inherited_if_entries_changed(self):
        parent = _make()
        out = copy.deepcopy(parent)
        out["transform"] = {"op": "basmala_fix"}
        out["entries"] = out["entries"][:-2]
        with self.assertRaises(SystemExit):
            stage_transform.inherit_truncated_gaps(parent, out, [])

    def test_realigned_surah_not_inherited(self):
        parent = _make()
        out = copy.deepcopy(parent)
        out["transform"] = {"op": f"realign_surah:{S}"}
        stage_transform.inherit_truncated_gaps(parent, out, [S])
        self.assertNotIn("truncatedGaps", out["transform"])


if __name__ == "__main__":
    unittest.main()
