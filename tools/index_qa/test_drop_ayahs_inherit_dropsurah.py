#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""توريثُ `drop_ayahs` لإعلان `dropSurah` القائم بدل رفضه (‏أمر القائد 2026-11-10).

العطبُ المقيس: قارئٌ له سورةٌ محجوبةٌ كاملةً (‏benkirane_warsh: س23 · 3siri: س23) لا يمكن حجبُ آياتٍ وسطيّةٍ في سورةٍ
أخرى عنده (‏13:27–30 · 36:46–52): كان الردُّ «التوريثُ لا يكون إلا مع --already-absent، وحذفُ مداخلَ تحته يردّه حارسُ
الترقية». ولا يُلتفّ بـ`--already-absent` (‏بابُه لما كان غائباً أصلاً) بل يورّث الحجبُ الإعلانَ القديم **حرفاً** بالدوالّ
المشتركة في `declarations.py`، وتقبل `promote.inherited_drops` الناتجَ لأنّ ما يفقده المنشورُ هو المحجوبُ المعلَنُ بدليله وحده.

    python -m unittest tools/index_qa/test_drop_ayahs_inherit_dropsurah.py -v
"""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "alignment_v3"))

import declarations                                              # noqa: E402
import drop_ayahs                                                # noqa: E402
import promote                                                   # noqa: E402
import stage_transform                                           # noqa: E402

LIVE = "timings/warsh/benkirane_warsh.jz"
LIVE_SHA = "ab12cd34" + "5" * 56
STAGE = "timings-staging/warsh/benkirane_warsh.0a1b2c3d.jz"
STAGE_SHA = "0a1b2c3d" + "7" * 56
DROPPED = 23                                       # السورةُ المحجوبةُ كاملةً في المنشور
OLD_USER = "تسجيل سورة المؤمنون عند الناشر ناقص فهي غير متاحة بصوت هذا القارئ."
OLD_REASON = "المصدر ينتهي قبل 23:60 بقياس CTC"
OLD_EVIDENCE = {"method": "ctc_window", "detail": "نافذة CTC 23:60 لا تجد أثراً بعد الدقيقة 31"}
NEW_USER = "تسجيل سورة الرعد ينقصه بعض آياتها."
C = promote._AYAH_COUNTS


def _ev(s, ayahs):
    return {f"{s}:{a}": {"method": "whisper", "detail": f"شاهد Whisper: لا أثر للآية {s}:{a}"} for a in ayahs}


def _entries(skip_surahs=(), skip_ids=()):
    out = []
    for s in range(1, 115):
        if s in skip_surahs:
            continue
        for a in range(1, C[s - 1] + 1):
            if f"{s}:{a}" in skip_ids:
                continue
            out.append({"ayahId": f"{s}:{a}", "startMs": a * 1000, "endMs": a * 1000 + 900,
                        "fileRef": f"{s:03d}.mp3", "confBand": "HIGH"})
    return out


def published(code="SOURCE_TRUNCATED", with_records=True):
    """المنشورُ حيّاً: `op=drop_surah:23` وس23 بلا مداخل وسائرُ السور تامّة (‏كحال benkirane_warsh).
    ‏`with_records` يضع سجلَّ السورة المحجوبة في `declarations` بسببٍ ودليلٍ؛ وبدونه يُشتقّ من الحقول العليا."""
    ids = [f"{DROPPED}:{a}" for a in range(1, C[DROPPED - 1] + 1)]
    key = {"source_truncated": "source_truncated", "OTHER": "other"}.get(code.lower() if code != "OTHER" else "OTHER",
                                                                         "source_truncated")
    tr = {"op": f"drop_surah:{DROPPED}", "fromSha256": "9" * 64, "fromKey": LIVE, "reason": OLD_REASON,
          "reasonUser": OLD_USER, "reasonCode": code}
    if with_records:
        tr["declarations"] = {str(DROPPED): {"op": "drop_surah", "reasonCode": code, "reasonUser": OLD_USER,
                                             "reason": OLD_REASON, "evidence": copy.deepcopy(OLD_EVIDENCE)}}
    return {"riwaya": "warsh", "reciterId": "benkirane_warsh", "ayahCount": 6236, "refineVersion": "r1",
            "entries": _entries(skip_surahs=(DROPPED,)),
            "missing": {"count": len(ids), "byReason": {key: len(ids)}, "ids": ids},
            "transform": tr}


def drop(idx, key=LIVE, sha=LIVE_SHA, ayahs=None, code="SOURCE_TRUNCATED", user=NEW_USER, ev=None, **kw):
    ayahs = ayahs or {13: [27, 28, 29, 30]}
    ev = ev if ev is not None else {k: v for s, a in ayahs.items() for k, v in _ev(s, a).items()}
    return drop_ayahs.drop_ayahs(idx, ayahs, copy.deepcopy(ev), reason=f"قياس {sorted(ayahs)}", reason_user=user,
                                 reason_code=code, from_sha=sha, from_key=key, **kw)


class OldDeclarationSurvives(unittest.TestCase):
    """الإعلانُ القديم لا يُمحى ولا يتغيّر حرفاً: الرمزُ والسببُ وreasonUser والدليل."""

    def setUp(self):
        self.parent = published()
        self.out = drop(copy.deepcopy(self.parent))
        self.tr = self.out["transform"]

    def test_old_declaration_remains_verbatim(self):
        old = self.parent["transform"]["declarations"][str(DROPPED)]
        self.assertEqual(self.tr["declarations"][str(DROPPED)], old)
        self.assertEqual(old["reasonCode"], "SOURCE_TRUNCATED")
        self.assertEqual(self.tr["declarations"][str(DROPPED)]["reasonUser"], OLD_USER)
        self.assertEqual(self.tr["declarations"][str(DROPPED)]["reason"], OLD_REASON)
        self.assertEqual(self.tr["declarations"][str(DROPPED)]["evidence"], OLD_EVIDENCE)

    def test_top_fields_carried_verbatim(self):
        self.assertEqual(self.tr["dropSurah"], [DROPPED])
        self.assertEqual(self.tr["reasonCode"], "SOURCE_TRUNCATED")
        self.assertEqual(self.tr["reasonUser"], OLD_USER)
        self.assertEqual((self.tr["fromKey"], self.tr["fromSha256"]), (LIVE, LIVE_SHA))

    def test_new_gap_has_its_own_record(self):
        self.assertEqual(self.tr["declarations"]["13"],
                         {"op": "declare_gap", "reasonCode": "SOURCE_TRUNCATED", "reasonUser": NEW_USER,
                          "reason": "قياس [13]"})
        self.assertEqual(self.tr["truncatedGaps"]["13"]["absent"], [27, 28, 29, 30])
        self.assertEqual(self.tr["op"], "declare_gap:13")          # لا يبدأ بـdrop_surah ⇒ يُتحقَّق من المنشور

    def test_old_declaration_derived_from_top_fields_when_no_records(self):
        """أصلٌ قديمٌ بلا حقل declarations: يُشتقّ سجلُّ السورة المحجوبة من الحقول العليا ويبقى رمزُه وسببُه."""
        out = drop(published(with_records=False))
        self.assertEqual(out["transform"]["declarations"][str(DROPPED)],
                         {"op": "drop_surah", "reasonCode": "SOURCE_TRUNCATED", "reasonUser": OLD_USER,
                          "reason": OLD_REASON})
        self.assertEqual(out["transform"]["reasonUser"], OLD_USER)

    def test_entries_only_the_named_ayahs_removed(self):
        keep = {e["ayahId"]: e for e in self.parent["entries"]}
        for a in (27, 28, 29, 30):
            keep.pop(f"13:{a}")
        self.assertEqual({e["ayahId"]: e for e in self.out["entries"]}, keep)    # الحدودُ لا تُمَدّ ولا تُمسّ
        self.assertEqual(self.out["missing"]["count"], len(self.parent["missing"]["ids"]) + 4)
        self.assertEqual(self.out["missing"]["byReason"]["source_truncated"], len(self.parent["missing"]["ids"]) + 4)

    def test_other_code_declaration_keeps_its_own_code(self):
        """سورةٌ محجوبةٌ برمز OTHER (‏حجبٌ مؤقّت) تبقى برمزها، والحجبُ الجديد برمزه هو — لا يُخلط رمزان في حقلٍ واحد."""
        out = drop(published(code="OTHER"))
        d = out["transform"]["declarations"]
        self.assertEqual(d[str(DROPPED)]["reasonCode"], "OTHER")
        self.assertEqual(d["13"]["reasonCode"], "SOURCE_TRUNCATED")
        self.assertEqual(out["transform"]["reasonCode"], "OTHER")


class PromoteAcceptsOutput(unittest.TestCase):
    """الناتجُ يمرّ على inherited_drops وdeclared_truncated_gaps وindex_gate التي لم تُرخَ."""

    def setUp(self):
        self.parent = published()
        self.out = drop(copy.deepcopy(self.parent))

    def test_inherited_drops_accepts(self):
        self.assertEqual(promote.inherited_drops(self.out, self.parent, LIVE_SHA), ({str(DROPPED)}, None))

    def test_declared_truncated_gaps_accepts(self):
        ok, why = promote.declared_truncated_gaps(self.out, 13)
        self.assertTrue(ok, why)

    def test_index_gate_accepts(self):
        self.assertIsNone(promote.index_gate(self.out, parent=self.parent, parent_sha=LIVE_SHA))

    def test_other_code_needs_owner_approval_as_before(self):
        parent = published(code="OTHER")
        out = drop(copy.deepcopy(parent))
        self.assertEqual(promote.inherited_drops(out, parent, LIVE_SHA, frozenset({str(DROPPED)})), ({str(DROPPED)}, None))
        self.assertIsNotNone(promote.inherited_drops(out, parent, LIVE_SHA)[1])

    def test_two_surahs_chained_through_staging(self):
        """3siri: 36:46–52 فوق مرشّحٍ مرحليٍّ سبق أن حُجبت فيه 13:27–30 — الإعلانان معاً والمحجوبةُ كاملةً."""
        step2 = drop(copy.deepcopy(self.out), key=STAGE, sha=STAGE_SHA, ayahs={36: list(range(46, 53))})
        tr = step2["transform"]
        self.assertEqual(sorted(tr["truncatedGaps"]), ["13", "36"])
        self.assertEqual(tr["dropSurah"], [DROPPED])
        self.assertEqual((tr["fromKey"], tr["fromSha256"]), (LIVE, LIVE_SHA))
        self.assertEqual(tr["declarations"][str(DROPPED)], self.parent["transform"]["declarations"][str(DROPPED)])
        self.assertEqual(tr["op"], "declare_gap:36|declare_gap:13")
        for s in (13, 36):
            self.assertTrue(promote.declared_truncated_gaps(step2, s)[0])
        self.assertEqual(promote.inherited_drops(step2, self.parent, LIVE_SHA), ({str(DROPPED)}, None))
        self.assertIsNone(promote.index_gate(step2, parent=self.parent, parent_sha=LIVE_SHA))


class InheritedDropsStillStrict(unittest.TestCase):
    """الاستثناءُ في inherited_drops لا يقبل فقدَ مدخلٍ سوى المحجوبِ المعلَنِ بدليله."""

    def setUp(self):
        self.parent = published()
        self.out = drop(copy.deepcopy(self.parent))
        self.lost = "إعلان الغياب الموروث مع فقد مداخل منشورة"

    def check(self, out):
        return promote.inherited_drops(out, self.parent, LIVE_SHA)[1]

    def test_extra_lost_entry_refused(self):
        out = copy.deepcopy(self.out)
        out["entries"] = [e for e in out["entries"] if e["ayahId"] != "13:5"]
        self.assertEqual(self.check(out), self.lost)

    def test_lost_entry_in_another_surah_refused(self):
        out = copy.deepcopy(self.out)
        out["entries"] = [e for e in out["entries"] if e["ayahId"] != "2:5"]
        self.assertEqual(self.check(out), self.lost)

    def test_gap_without_evidence_refused(self):
        out = copy.deepcopy(self.out)
        del out["transform"]["truncatedGaps"]["13"]["evidence"]["13:28"]
        self.assertEqual(self.check(out), self.lost)

    def test_gap_without_declaration_refused(self):
        out = copy.deepcopy(self.out)
        out["transform"]["op"] = "refine"
        self.assertEqual(self.check(out), self.lost)

    def test_gap_naming_fewer_than_lost_refused(self):
        out = copy.deepcopy(self.out)
        out["entries"] = [e for e in out["entries"] if e["ayahId"] != "13:31"]
        self.assertEqual(self.check(out), self.lost)

    def test_gap_on_the_inherited_dropped_surah_not_excused(self):
        out = copy.deepcopy(self.out)
        out["transform"]["truncatedGaps"][str(DROPPED)] = {"absent": [5], "reason": "source_truncated", "evidence": {}}
        out["entries"] = [e for e in out["entries"] if e["ayahId"] != "13:5"]
        self.assertEqual(self.check(out), self.lost)

    def test_no_gap_at_all_still_refuses_loss(self):
        """الاختبارُ القائم test_losing_existing_ayah_refuses بصورته هنا: فقدٌ بلا إعلان حجبٍ يُردّ."""
        out = copy.deepcopy(self.out)
        out["transform"].pop("truncatedGaps")
        self.assertEqual(self.check(out), self.lost)


class DropAyahsRefusals(unittest.TestCase):
    """الحرّاسُ الأخرى في drop_ayahs كما هي مع الإعلان الموروث."""

    def setUp(self):
        self.parent = published()

    def refused(self, needle, **kw):
        with self.assertRaises(SystemExit) as cm:
            drop(copy.deepcopy(kw.pop("idx", self.parent)), **kw)
        self.assertIn(needle, str(cm.exception))

    def test_dropped_surah_itself_refused(self):
        """لا drop_ayahs على سورةٍ هي نفسها محجوبةٌ كاملةً."""
        self.refused("ولا تورّث هذه الأداةُ ذلك الإعلان", ayahs={DROPPED: [5]})

    def test_dropped_surah_refused_together_with_valid_one(self):
        self.refused("ولا تورّث هذه الأداةُ ذلك الإعلان", ayahs={13: [27], DROPPED: [5]})

    def test_first_ayah_refused(self):
        self.refused("لا يُحجب أولُ السورة", ayahs={13: [1]})

    def test_last_ayah_refused(self):
        self.refused("لا يُحجب أولُ السورة", ayahs={13: [43]})

    def test_over_quarter_refused(self):
        self.refused("يتجاوز ربع آيات السورة", ayahs={13: list(range(10, 22))})

    def test_missing_evidence_refused(self):
        self.refused("لا دليلَ قياسٍ للآية 13:30", ev=_ev(13, [27, 28, 29]))

    def test_no_mixing_of_codes_in_one_surah_header(self):
        """حجبٌ سابقٌ بـSOURCE_TRUNCATED ثمّ حجبٌ ثانٍ بـTIMING_UNDER_REPAIR فوقه ⇒ يُردّ (‏ولا يُخلط رمزان)."""
        step1 = drop(copy.deepcopy(self.parent))
        ev = _ev(36, range(46, 53))
        for rec in ev.values():
            rec["heard"] = {"witness": "whisper-large", "runId": 12345, "text": "نصٌّ مسموع"}
        with self.assertRaises(SystemExit) as cm:
            drop(step1, key=STAGE, sha=STAGE_SHA, ayahs={36: list(range(46, 53))}, code="TIMING_UNDER_REPAIR", ev=ev)
        self.assertIn("ولا يُخلط رمزان", str(cm.exception))

    def test_prior_record_on_requested_surah_refused(self):
        p = copy.deepcopy(self.parent)
        p["transform"]["declarations"]["13"] = {"op": "declare_gap", "reasonCode": "SOURCE_TRUNCATED", "reasonUser": "x"}
        self.refused("سجلُّ إعلانٍ", idx=p)

    def test_unpublished_origin_of_staged_parent_refused(self):
        staged = drop(copy.deepcopy(self.parent))
        staged["transform"]["fromKey"] = STAGE
        with self.assertRaises(SystemExit) as cm:
            drop(staged, key=STAGE, sha=STAGE_SHA, ayahs={36: list(range(46, 53))})
        self.assertIn("مجهولُ المنشأ", str(cm.exception))

    def test_already_absent_door_is_unchanged(self):
        """--already-absent لم يُلمس: مداخلُ السورة يجب أن تساوي آياتِها ناقص المسمّاة، وإلا رُدّ."""
        with self.assertRaises(SystemExit) as cm:
            drop(copy.deepcopy(self.parent), already_absent=True)
        self.assertIn("ليست كلَّ آياتها ناقص المسمّاة", str(cm.exception))


class StageTransformInheritsBoth(unittest.TestCase):
    """stage_transform يورّث الحجبَ الوسطيَّ ومعه إعلانَ الإسقاط (‏وإلا ضاع الثاني وردّه index_gate)."""

    def setUp(self):
        self.parent = published()
        self.pidx = drop(copy.deepcopy(self.parent))              # المنشورُ بعد الترقية: حجبٌ وسطيٌّ + dropSurah

    def candidate(self):
        """مرشّحٌ حوّل سورةً أخرى فوق المنشور: مداخلُه من الأب، وترويستُه جديدة بلا إعلانات."""
        out = {k: v for k, v in self.pidx.items() if k != "transform"}
        out["entries"] = copy.deepcopy(self.pidx["entries"])
        out["transform"] = {"op": "ctc_surah_splice:2", "fromSha256": "e" * 64, "fromKey": LIVE}
        return out

    def test_both_declarations_carried_and_accepted(self):
        out = self.candidate()
        stage_transform.inherit_truncated_gaps(self.pidx, out, realigned={2})
        tr = out["transform"]
        self.assertEqual(tr["dropSurah"], [DROPPED])
        self.assertEqual((tr["reasonCode"], tr["reasonUser"]), ("SOURCE_TRUNCATED", OLD_USER))
        self.assertEqual(tr["declarations"][str(DROPPED)], self.parent["transform"]["declarations"][str(DROPPED)])
        self.assertEqual(tr["truncatedGaps"], self.pidx["transform"]["truncatedGaps"])
        tr.update(fromKey=LIVE, fromSha256=LIVE_SHA)
        self.assertEqual(promote.inherited_drops(out, self.parent, LIVE_SHA), ({str(DROPPED)}, None))
        self.assertTrue(promote.declared_truncated_gaps(out, 13)[0])

    def test_conflicting_reason_refused(self):
        out = self.candidate()
        out["transform"]["reasonUser"] = "نصٌّ آخر للمستخدم"
        with self.assertRaises(SystemExit) as cm:
            stage_transform.inherit_truncated_gaps(self.pidx, out, realigned={2})
        self.assertIn("يخالف إعلانَ الأصل", str(cm.exception))

    def test_candidate_that_restored_the_dropped_surah_does_not_inherit_it(self):
        out = self.candidate()
        out["entries"] += [{"ayahId": f"{DROPPED}:{a}", "startMs": a, "endMs": a + 1, "fileRef": "x"}
                           for a in range(1, C[DROPPED - 1] + 1)]
        stage_transform.inherit_truncated_gaps(self.pidx, out, realigned={DROPPED})
        self.assertNotIn("dropSurah", out["transform"])

    def test_parent_without_drop_surah_unchanged(self):
        p = published()
        p["entries"] = _entries()
        p["missing"] = {"count": 0, "byReason": {}, "ids": []}
        p["transform"] = {"op": "refine"}
        pidx = drop(p)
        out = {"entries": copy.deepcopy(pidx["entries"]), "missing": copy.deepcopy(pidx["missing"]),
               "transform": {"op": "ctc_surah_splice:2"}}
        stage_transform.inherit_truncated_gaps(pidx, out, realigned={2})
        self.assertNotIn("dropSurah", out["transform"])


if __name__ == "__main__":
    unittest.main()
