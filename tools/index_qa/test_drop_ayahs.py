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


# ─── TIMING_UNDER_REPAIR: الرمزُ الثاني (‏آياتٌ يُسمع في مدخلها صوتُ غيرها) ───
TUR = "TIMING_UNDER_REPAIR"
HEARD = {"witness": "ctc_opener_probe", "runId": 25123456789, "text": "وَالنَّازِعَاتِ غَرْقًا"}


def _ev_tur(absent, heard=HEARD):
    out = {}
    for a in absent:
        r = dict(EV)
        if heard is not None:
            r["heard"] = dict(heard) if isinstance(heard, dict) else heard
        out[f"{S}:{a}"] = r
    return out


def _make_tur(absent=(15, 17, 18), **kw):
    ev = kw.pop("evidence", _ev_tur(absent))
    kw.setdefault("reason_code", TUR)
    return _make(absent=absent, evidence=ev, **kw)


class SourceTruncatedUnchanged(unittest.TestCase):
    """سلوكُ SOURCE_TRUNCATED لم يتغيّر حرفاً: المفتاحُ والسببُ والعدّاد كما كانت، و`heard` لا يُنسخ ولا يُشترط."""

    def test_same_bytes_as_before(self):
        out = _make()
        tr = out["transform"]
        self.assertEqual(tr["reasonCode"], "SOURCE_TRUNCATED")
        self.assertEqual(tr["truncatedGaps"][str(S)]["reason"], "source_truncated")
        self.assertEqual(out["missing"]["byReason"]["source_truncated"], 3)
        self.assertNotIn("timing_under_repair", out["missing"]["byReason"])
        self.assertEqual(tr["truncatedGaps"][str(S)]["evidence"][f"{S}:15"], EV)      # لا حقلَ heard

    def test_heard_ignored_not_copied(self):
        out = _make(evidence=_ev_tur((15, 17, 18)))
        self.assertNotIn("heard", out["transform"]["truncatedGaps"][str(S)]["evidence"][f"{S}:15"])
        self.assertTrue(promote.declared_truncated_gaps(out, S)[0])


class TimingUnderRepair(unittest.TestCase):
    def test_accepted(self):
        out = _make_tur()
        ok, why = promote.declared_truncated_gaps(out, S)
        self.assertTrue(ok, why)
        tr = out["transform"]
        self.assertEqual(tr["reasonCode"], TUR)
        self.assertEqual(tr["truncatedGaps"][str(S)]["reason"], "timing_under_repair")
        self.assertEqual(tr["truncatedGaps"][str(S)]["evidence"][f"{S}:17"]["heard"], HEARD)
        by = out["missing"]["byReason"]
        self.assertEqual(by["timing_under_repair"], 3)
        self.assertEqual(by.get("source_truncated", 0), 0)     # لا يُعدّ بتراً فلا يُعفى من العتبة
        src = {e["ayahId"]: e for e in _idx()["entries"]}
        for e in out["entries"]:
            self.assertEqual(e, src[e["ayahId"]])
        self.assertEqual(len(out["entries"]) + out["missing"]["count"], 6236)

    def test_not_excused_from_missing_threshold(self):
        """بقاؤها «غيرَ معلَّلٍ» في عتبة الغياب هو الاتجاهُ الأشدّ: لا يُخفَّف حارسُ index_gate."""
        out = _make_tur()
        miss = out["missing"]
        excused = max(0, min(int(miss["byReason"].get("source_truncated", 0)), miss["count"]))
        self.assertEqual(excused, 0)

    def test_third_code_rejected_tool(self):
        for code in ("OTHER", "SOURCE_CORRUPT", "NO_PUBLISHED_RECORDING", "timing_under_repair", ""):
            with self.assertRaises(SystemExit, msg=code):
                _make_tur(reason_code=code)

    def test_third_code_rejected_promote(self):
        for code in ("OTHER", "SOURCE_CORRUPT", None):
            o = _make_tur()
            o["transform"]["reasonCode"] = code
            self.assertFalse(promote.declared_truncated_gaps(o, S)[0], code)

    def test_code_and_reason_must_agree(self):
        o = _make_tur()
        o["transform"]["reasonCode"] = "SOURCE_TRUNCATED"           # دليلُ سماعٍ لكن رمزٌ آخر: يُردّ
        self.assertFalse(promote.declared_truncated_gaps(o, S)[0])
        o = _make()
        o["transform"]["reasonCode"] = TUR                          # رمزٌ جديدٌ بسجلّ البتر: يُردّ
        self.assertFalse(promote.declared_truncated_gaps(o, S)[0])

    def test_no_heard_evidence_rejected_tool(self):
        with self.assertRaises(SystemExit):
            _make_tur(evidence=_ev_tur((15, 17, 18), heard=None))
        for bad in ({"witness": "", "runId": 1, "text": "x"}, {"witness": "w", "runId": 0, "text": "x"},
                    {"witness": "w", "runId": "abc", "text": "x"}, {"witness": "w", "runId": 1, "text": " "},
                    {"witness": "w", "runId": 1}, {"runId": 1, "text": "x"}, "نصّ"):
            with self.assertRaises(SystemExit, msg=str(bad)):
                _make_tur(evidence=_ev_tur((15, 17, 18), heard=bad))

    def test_one_ayah_missing_heard_rejected_tool(self):
        ev = _ev_tur((15, 17, 18))
        ev[f"{S}:17"].pop("heard")
        with self.assertRaises(SystemExit):
            _make_tur(evidence=ev)

    def test_no_heard_evidence_rejected_promote(self):
        o = _make_tur()
        o["transform"]["truncatedGaps"][str(S)]["evidence"][f"{S}:17"].pop("heard")
        self.assertFalse(promote.declared_truncated_gaps(o, S)[0])
        o = _make_tur()
        o["transform"]["truncatedGaps"][str(S)]["evidence"][f"{S}:15"]["heard"]["text"] = ""
        self.assertFalse(promote.declared_truncated_gaps(o, S)[0])

    def test_first_or_last_rejected(self):
        for ab in ((1, 15), (15, N)):
            with self.assertRaises(SystemExit):
                _make_tur(absent=ab)
        o = _make_tur()
        o["transform"]["truncatedGaps"][str(S)]["absent"] = [1, 15, 17, 18]
        self.assertFalse(promote.declared_truncated_gaps(o, S)[0])

    def test_over_quarter_rejected(self):
        with self.assertRaises(SystemExit):
            _make_tur(absent=tuple(range(2, 14)))                   # 12 > ربع 46
        self.assertTrue(promote.declared_truncated_gaps(_make_tur(absent=tuple(range(2, 13))), S)[0])
        o = _make_tur(absent=tuple(range(2, 13)))
        o["transform"]["truncatedGaps"][str(S)]["absent"].append(13)
        self.assertFalse(promote.declared_truncated_gaps(o, S)[0])

    def test_reason_user_mandatory_and_banned_words(self):
        with self.assertRaises(SystemExit):
            _make_tur(reason_user=" ")
        with self.assertRaises(SystemExit):
            _make_tur(reason_user="أمر المالك")
        o = _make_tur()
        o["transform"].pop("reasonUser")
        self.assertFalse(promote.declared_truncated_gaps(o, S)[0])

    def test_by_reason_must_count(self):
        o = _make_tur()
        o["missing"]["byReason"]["timing_under_repair"] = 2
        self.assertFalse(promote.declared_truncated_gaps(o, S)[0])
        o = _make_tur()
        o["missing"]["byReason"] = {"source_truncated": 3}          # عدُّها بغير مفتاحها: يُردّ
        self.assertFalse(promote.declared_truncated_gaps(o, S)[0])

    def test_inherited(self):
        parent = _make_tur()
        out = copy.deepcopy(parent)
        out["transform"] = {"op": "basmala_fix", "reason": "r"}
        stage_transform.inherit_truncated_gaps(parent, out, [])
        self.assertEqual(out["transform"]["reasonCode"], TUR)
        ok, why = promote.declared_truncated_gaps(out, S)
        self.assertTrue(ok, why)
        self.assertEqual(out["transform"]["truncatedGaps"][str(S)]["evidence"][f"{S}:15"]["heard"], HEARD)

    def test_inherited_with_conflicting_code_rejected(self):
        parent = _make_tur()
        out = copy.deepcopy(parent)
        out["transform"] = {"op": "x", "reasonCode": "SOURCE_TRUNCATED", "reasonUser": "u"}
        with self.assertRaises(SystemExit):
            stage_transform.inherit_truncated_gaps(parent, out, [])

    def test_no_mixing_codes_in_one_header(self):
        """أصلٌ يعلن حجباً بـSOURCE_TRUNCATED في س79 لا يُحجب فوقه بالرمز الآخر في سورةٍ أخرى."""
        base = _idx()
        src_out = _make()                                            # س79 معلَنةٌ بالبتر
        s2 = 80                                                      # عبس: 42 آية
        n2 = promote._AYAH_COUNTS[s2 - 1]
        src_out["entries"] += [{"ayahId": f"{s2}:{a}", "startMs": 10 ** 6 + a * 1000, "endMs": 10 ** 6 + a * 1000 + 900,
                                "fileRef": "f", "confBand": "HIGH"} for a in range(1, n2 + 1)]
        src_out["missing"]["ids"] = [i for i in src_out["missing"]["ids"] if not i.startswith(f"{s2}:")]
        src_out["missing"]["count"] -= n2
        ev = {f"{s2}:5": {**EV, "heard": dict(HEARD)}}
        with self.assertRaises(SystemExit):
            drop_ayahs.drop_ayahs(src_out, {s2: [5]}, ev, reason="r", reason_user="تسجيلُ هذه السورة ينقصه بعضُ آياتها.",
                                  reason_code=TUR, from_sha="a" * 64, from_key="timings/hafs/x.jz")
        self.assertIsNotNone(base)


class DropParentRefused(unittest.TestCase):
    """⛔ (‏2026-11-10 · 3siri bc63afc4) أصلٌ يعلن إسقاطَ سورةٍ كاملة لا يُمحى إعلانُه بصمت.
    ⭐ (أمر القائد 2026-11-10 · توريث dropSurah) كان الحجبُ بالحذف فوقه مردوداً؛ والآن يُورَّث الإعلانُ حرفاً
    (‏التفصيلُ والتحوّرُ في `test_drop_ayahs_inherit_dropsurah.py`) ويبقى مردوداً: الصيغةُ النصّيّةُ لـ`transform`،
    والحجبُ على السورة المحجوبة نفسِها."""

    def _parent(self, tr):
        i = _idx()
        i["transform"] = tr
        return i

    def _drop(self, parent, code="SOURCE_TRUNCATED", ev=None):
        return drop_ayahs.drop_ayahs(parent, {S: [15, 17, 18]}, ev or _ev_tur((15, 17, 18)), reason="قياس",
                                     reason_user="توقيتُ هذه الآيات قيد الإصلاح.", reason_code=code,
                                     from_sha="a" * 64, from_key="timings/hafs/x.jz")

    def test_drop_surah_56_other_parent_inherited(self):
        """الحالةُ نفسُها: أصلٌ يحمل dropSurah=[56] بسبب OTHER، والحجبُ الجديد TIMING_UNDER_REPAIR أو SOURCE_TRUNCATED."""
        user = "توقيتُ هذه السورة لهذا القارئ قيد الإصلاح، فحُجب مؤقّتاً."
        p = self._parent({"op": "drop_surah:56", "dropSurah": [56], "reasonCode": "OTHER", "reasonUser": user})
        for code in (TUR, "SOURCE_TRUNCATED"):
            out = self._drop(copy.deepcopy(p), code)
            tr = out["transform"]
            self.assertEqual((tr["dropSurah"], tr["reasonCode"], tr["reasonUser"]), ([56], "OTHER", user))
            self.assertEqual(tr["declarations"]["56"]["reasonCode"], "OTHER")
            self.assertEqual(tr["declarations"][str(S)]["reasonCode"], code)

    def test_op_only_and_field_only_inherited_and_text_form_refused(self):
        for tr in ({"op": "drop_surah:48,56", "reasonCode": "OTHER", "reasonUser": "x"},
                   {"op": "heard_pin:9", "dropSurah": [56], "reasonCode": "OTHER", "reasonUser": "x"}):
            out = self._drop(self._parent(tr), TUR)
            self.assertTrue(out["transform"]["dropSurah"])
            self.assertEqual(out["transform"]["reasonUser"], "x")
        with self.assertRaises(SystemExit):
            self._drop(self._parent("drop_surah:56"), TUR)

    def test_parent_without_drop_unchanged(self):
        out = self._drop(self._parent({"op": "heard_pin:9"}), TUR)
        self.assertEqual(out["transform"]["reasonCode"], TUR)


if __name__ == "__main__":
    unittest.main()
