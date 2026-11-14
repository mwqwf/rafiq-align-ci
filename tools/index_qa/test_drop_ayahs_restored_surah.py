#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""حجبُ آيةٍ في سورةٍ كانت محجوبةً كاملةً ثمّ استُرجعت تامّةً (‏أمر القائد 2026-11-14 · kyat س21:82 وbenkirane_warsh س23:25).

العلّةُ: `ctc_splice` أعاد محاذاةَ السورة فصارت مداخلُها كلُّها حاضرةً، لكنّ سجلَّ إعلان `drop_surah` القديم بقي موروثاً في الترويسة،
فكانت `drop_ayahs` تردّ كلَّ حجبٍ عليها بـ«لها في الأصل سجلُّ إعلانٍ». والتعديلُ ضيّق: يُستبدل سجلُّ السورة المستردّة **وحدها**
بشرطين مجتمعين (‏سجلُّها `drop_surah` + مداخلُها كلُّ آياتها)، وكلُّ حالةٍ أخرى يبقى ردُّها القديم حرفاً.

    python -m unittest tools.index_qa.test_drop_ayahs_restored_surah -v
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

LIVE = "timings/hafs/kyat.jz"
LIVE_SHA = "ab12cd34" + "5" * 56
RESTORED, STILL = 21, 56          # المستردّةُ تامّةً · وسورةٌ ما زالت محجوبةً كاملةً
OLD_TUR = {"op": "drop_surah", "reasonCode": "TIMING_UNDER_REPAIR",
           "reasonUser": "توقيت سورة الأنبياء قيد الإصلاح عند هذا القارئ.", "reason": "قيد الإصلاح"}
OLD_STILL = {"op": "drop_surah", "reasonCode": "SOURCE_TRUNCATED",
             "reasonUser": "تسجيل سورة الواقعة عند الناشر ناقص.", "reason": "المصدر ينتهي قبل 56:96"}
C = promote._AYAH_COUNTS
NEW_USER = "آيةٌ واحدةٌ من سورة الأنبياء يُسمع في مدخلها صوتُ غيرها."


def _entries(skip_surahs=(), skip_ids=(), dup=()):
    out = []
    for s in range(1, 115):
        if s in skip_surahs:
            continue
        for a in range(1, C[s - 1] + 1):
            if f"{s}:{a}" in skip_ids:
                continue
            out.append({"ayahId": f"{s}:{a}", "startMs": a * 1000, "endMs": a * 1000 + 900,
                        "fileRef": f"{s:03d}.mp3", "confBand": "HIGH"})
            if f"{s}:{a}" in dup:
                out.append(dict(out[-1]))
    return out


def restored_index(*, only_restored=False, skip_ids=(), dup=(), record=None, drop_still=True, named=True):
    """فهرسٌ سورتُه 21 تامّةٌ والإعلانُ القديمُ لها باقٍ؛ ومعه (‏افتراضاً) س56 ما زالت محجوبةً بإعلانها."""
    still = [] if (only_restored or not drop_still) else [STILL]
    miss_ids = [f"{s}:{a}" for s in still for a in range(1, C[s - 1] + 1)] + list(skip_ids)
    decls = {str(RESTORED): copy.deepcopy(record or OLD_TUR)}
    names = [RESTORED]
    if still:
        decls[str(STILL)] = copy.deepcopy(OLD_STILL)
        names.append(STILL)
    tr = {"op": "drop_surah:" + ",".join(str(n) for n in sorted(names)), "fromSha256": "9" * 64, "fromKey": LIVE,
          "reason": "قيد الإصلاح", "reasonUser": OLD_STILL["reasonUser"] if still else OLD_TUR["reasonUser"],
          "reasonCode": "SOURCE_TRUNCATED" if still else "TIMING_UNDER_REPAIR",
          "dropSurah": sorted(names), "declarations": decls}
    if not named:                  # الشكلُ ب: سجلُّ `declarations` وحدَه يحمل بقيّةَ إعلان السورة المستردّة
        tr["op"] = f"drop_surah:{STILL}"
        tr["dropSurah"] = [STILL]
    return {"riwaya": "hafs", "reciterId": "kyat", "ayahCount": 6236, "refineVersion": "r1",
            "entries": _entries(skip_surahs=still, skip_ids=skip_ids, dup=dup),
            "missing": {"count": len(miss_ids), "byReason": {"source_truncated": len(miss_ids)} if miss_ids else {},
                        "ids": miss_ids},
            "transform": tr}


def parent_index():
    """المنشورُ الحيّ قبل الاسترجاع: س21 وس56 كلتاهما محجوبتان كاملتين."""
    ids = [f"{s}:{a}" for s in (RESTORED, STILL) for a in range(1, C[s - 1] + 1)]
    p = restored_index()
    p["entries"] = _entries(skip_surahs=(RESTORED, STILL))
    p["missing"] = {"count": len(ids), "byReason": {"source_truncated": len(ids)}, "ids": ids}
    p["transform"]["declarations"][str(RESTORED)] = {**OLD_STILL, "reasonUser": OLD_STILL["reasonUser"]}
    return p


def ev(s, ayahs, heard=True):
    out = {}
    for a in ayahs:
        r = {"method": "whisper", "detail": f"شاهد Whisper: لا أثر للآية {s}:{a}"}
        if heard:
            r["heard"] = {"witness": "whisper-large", "runId": 12345, "text": "نصٌّ مسموع"}
        out[f"{s}:{a}"] = r
    return out


def drop(idx, ayahs=None, code="TIMING_UNDER_REPAIR", **kw):
    ayahs = ayahs or {RESTORED: [82]}
    evd = kw.pop("ev", None)
    if evd is None:
        evd = {}
        for s, a in ayahs.items():
            evd.update(ev(s, a, heard=(code == "TIMING_UNDER_REPAIR")))
    return drop_ayahs.drop_ayahs(idx, ayahs, evd, reason="قياس Whisper", reason_user=NEW_USER, reason_code=code,
                                 from_sha=LIVE_SHA, from_key=LIVE, **kw)


OLD_MSG = "لها في الأصل سجلُّ إعلانٍ"
NAMED_MSG = "ولا تورّث هذه الأداةُ ذلك الإعلان"


class RestoredSurahAccepted(unittest.TestCase):
    def setUp(self):
        self.idx = restored_index()
        self.out = drop(copy.deepcopy(self.idx))
        self.tr = self.out["transform"]

    def test_record_replaced_by_new_gap_record(self):
        self.assertEqual(self.tr["declarations"][str(RESTORED)],
                         {"op": "declare_gap", "reasonCode": "TIMING_UNDER_REPAIR", "reasonUser": NEW_USER,
                          "reason": "قياس Whisper"})
        self.assertEqual(self.tr["truncatedGaps"][str(RESTORED)]["absent"], [82])

    def test_other_surah_record_and_drop_surah_untouched_verbatim(self):
        self.assertEqual(self.tr["declarations"][str(STILL)], OLD_STILL)
        self.assertEqual(self.tr["dropSurah"], [STILL])
        self.assertEqual((self.tr["reasonCode"], self.tr["reasonUser"]),
                         (self.idx["transform"]["reasonCode"], self.idx["transform"]["reasonUser"]))
        self.assertEqual(set(self.tr["declarations"]), {str(RESTORED), str(STILL)})

    def test_only_named_ayah_removed(self):
        before = {e["ayahId"]: e for e in self.idx["entries"]}
        after = {e["ayahId"]: e for e in self.out["entries"]}
        self.assertEqual(set(before) - set(after), {f"{RESTORED}:82"})
        for k, v in after.items():
            self.assertEqual(v, before[k])

    def test_input_not_mutated(self):
        self.assertEqual(self.idx, restored_index())

    def test_declared_truncated_gaps_accepts(self):
        ok, why = promote.declared_truncated_gaps(self.out, RESTORED)
        self.assertTrue(ok, why)

    def test_inherited_drops_accepts_without_relaxing(self):
        self.assertEqual(promote.inherited_drops(self.out, parent_index(), LIVE_SHA), ({str(STILL)}, None))

    def test_index_gate_accepts(self):
        self.assertIsNone(promote.index_gate(self.out, parent=parent_index(), parent_sha=LIVE_SHA))

    def test_only_restored_surah_in_header(self):
        """ليس في الترويسة غيرُ س21: لا يبقى dropSurah، والناتجُ يجتاز الحرّاس بلا أصلٍ يورّث إعلاناً."""
        idx = restored_index(only_restored=True)
        out = drop(copy.deepcopy(idx))
        self.assertNotIn("dropSurah", out["transform"])
        self.assertTrue(promote.declared_truncated_gaps(out, RESTORED)[0])
        self.assertIsNone(promote.index_gate(out, parent=None, parent_sha=None))

    def test_source_truncated_code_also(self):
        out = drop(copy.deepcopy(self.idx), code="SOURCE_TRUNCATED")
        self.assertEqual(out["transform"]["declarations"][str(RESTORED)]["reasonCode"], "SOURCE_TRUNCATED")
        self.assertTrue(promote.declared_truncated_gaps(out, RESTORED)[0])

    def test_stale_name_absent_from_op_header_also_works(self):
        """بقيّةُ إعلانٍ في `declarations` وحدها (‏op/dropSurah لا يسمّيان السورة) تُعالَج كذلك."""
        out = drop(restored_index(named=False))
        self.assertEqual(out["transform"]["dropSurah"], [STILL])
        self.assertEqual(out["transform"]["declarations"][str(STILL)], OLD_STILL)


class RefusalsStayVerbatim(unittest.TestCase):
    """كلُّ ما عدا الحالة الضيّقة يبقى ردُّه القديمَ حرفاً."""

    def refused(self, idx, needle, **kw):
        with self.assertRaises(SystemExit) as cm:
            drop(copy.deepcopy(idx), **kw)
        self.assertIn(needle, str(cm.exception))

    def test_one_missing_ayah_keeps_refusal(self):
        self.refused(restored_index(skip_ids=[f"{RESTORED}:50"], named=False), OLD_MSG)
        self.refused(restored_index(skip_ids=[f"{RESTORED}:50"]), NAMED_MSG)

    def test_duplicate_entry_keeps_refusal(self):
        self.refused(restored_index(dup=[f"{RESTORED}:50"], named=False), OLD_MSG)
        self.refused(restored_index(dup=[f"{RESTORED}:50"]), NAMED_MSG)

    def test_record_op_not_drop_surah_keeps_refusal(self):
        rec = {"op": "declare_gap", "reasonCode": "SOURCE_TRUNCATED", "reasonUser": "x", "reason": "y"}
        self.refused(restored_index(record=rec, named=False), OLD_MSG)

    def test_surah_actually_dropped_keeps_refusal(self):
        """آيةٌ من سورةٍ محجوبةٍ فعلاً (‏بلا مداخل) ⇒ الردُّ القديم."""
        self.refused(restored_index(), NAMED_MSG, ayahs={STILL: [5]}, code="SOURCE_TRUNCATED")

    def test_dropped_surah_together_with_restored_refused(self):
        self.refused(restored_index(), NAMED_MSG, ayahs={RESTORED: [82], STILL: [5]})

    def test_other_requested_surah_with_prior_record_keeps_refusal(self):
        """ما يُستثنى هو السورةُ المستردّةُ وحدَها: سورةٌ أخرى مطلوبةٌ لها سجلُّ إعلانٍ تُردّ ولو حُجبت المستردّةُ معها."""
        idx = restored_index(named=False)
        idx["transform"]["declarations"]["13"] = {"op": "declare_gap", "reasonCode": "SOURCE_TRUNCATED", "reasonUser": "x"}
        self.refused(idx, OLD_MSG, ayahs={RESTORED: [82], 13: [27]}, code="SOURCE_TRUNCATED")

    def test_first_ayah_still_refused(self):
        self.refused(restored_index(), "لا يُحجب أولُ السورة", ayahs={RESTORED: [1]})

    def test_missing_evidence_still_refused(self):
        self.refused(restored_index(), "لا دليلَ قياسٍ", ev={})

    def test_tur_without_heard_still_refused(self):
        self.refused(restored_index(), "لا دليلَ سماعٍ", ev=ev(RESTORED, [82], heard=False))

    def test_stale_missing_ids_still_refused(self):
        """وسمُ الاكتمال يعدّ آياتٍ حاضرةً غائبةً ⇒ الأصلُ غيرُ متّسق ويُردّ."""
        idx = restored_index()
        idx["missing"] = {"count": 1, "byReason": {"source_truncated": 1}, "ids": [f"{RESTORED}:82"]}
        idx["entries"] = [e for e in idx["entries"]]
        self.refused(idx, "وسمُ الاكتمال يعدّ آياتٍ حاضرةً غائبة")


class HelpersNarrow(unittest.TestCase):
    def test_restored_set(self):
        idx = restored_index()
        self.assertEqual(drop_ayahs.restored_dropped_surahs(idx, {RESTORED: [82]}, C), {RESTORED})
        self.assertEqual(drop_ayahs.restored_dropped_surahs(idx, {STILL: [5]}, C), set())
        self.assertEqual(drop_ayahs.restored_dropped_surahs(idx, {13: [27]}, C), set())

    def test_strip_leaves_other_surahs_and_input_alone(self):
        idx = restored_index()
        snap = copy.deepcopy(idx)
        h = drop_ayahs.without_stale_drop(idx, {RESTORED})
        self.assertEqual(idx, snap)
        self.assertEqual(h["transform"]["dropSurah"], [STILL])
        self.assertEqual(h["transform"]["op"], f"drop_surah:{STILL}")
        self.assertEqual(h["transform"]["declarations"], {str(STILL): OLD_STILL})


if __name__ == "__main__":
    unittest.main()
