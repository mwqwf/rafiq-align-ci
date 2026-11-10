#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختباراتُ توريث `drop_ayahs` لإعلان الإسقاط في الأصل (‏أمر القائد 2026-11-10 · الكردي س4 فوق إعلان س55)،
واختباراتُ المستعملين الثلاثة للوحدة المشتركة `declarations.py` (‏drop_surah · pin_heard · drop_ayahs).

الشكلُ الحقيقيّ: المنشورُ `timings/hafs/kurdi.jz` (‏b7fe6778) ترويستُه `op=drop_surah:4,55` برمز OTHER، ومرشّحُ
`ctc_splice mode=heard` يبني س4 فوقه فيحمل `dropSurah=[55]` ومنشأه المنشور، ثمّ `drop_ayahs --already-absent 4:127`
برمز SOURCE_TRUNCATED. وكانت الخطوةُ الثانية تُردّ حتماً بعد #100 («ولا تورّث هذه الأداةُ ذلك الإعلان»).

    python -m unittest tools/index_qa/test_drop_ayahs_inherit.py -v
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
import drop_surah                                                # noqa: E402
import pin_heard                                                 # noqa: E402
import promote                                                   # noqa: E402

LIVE = "timings/hafs/kurdi.jz"
LIVE_SHA = "b7fe6778" + "1" * 56
STAGE = "timings-staging/hafs/kurdi.0a1b2c3d.jz"
STAGE_SHA = "0a1b2c3d" + "2" * 56
S, ABSENT, DROP = 4, [127], 55
OLD_USER = "تسجيل سورة الرحمن عند مصدره تغيّر فحُجبت مؤقّتاً حتى يُعاد ضبط توقيتها."
NEW_USER = "تسجيل سورة النساء عند الناشر ناقص فالآية 127 غير متاحة بصوت هذا القارئ."
EV = {f"{S}:127": {"method": "whisper", "detail": "شاهد Whisper 42734080787: 4:125 ثمّ 4:126 ثمّ 4:128 بلا كلمة من 4:127"}}
C = promote._AYAH_COUNTS


def _entries(skip_surahs=(), skip_ayahs=()):
    out = []
    for s in range(1, 115):
        if s in skip_surahs:
            continue
        for a in range(1, C[s - 1] + 1):
            if f"{s}:{a}" in skip_ayahs:
                continue
            out.append({"ayahId": f"{s}:{a}", "startMs": a * 1000, "endMs": a * 1000 + 900,
                        "fileRef": f"{s:03d}.mp3", "confBand": "HIGH"})
    return out


def _with_missing(idx, ids, by):
    idx["missing"] = {"count": len(ids), "byReason": by, "ids": ids}
    return idx


def published(code="OTHER", drops=(S, DROP)):
    """المنشور كما هو حيّاً (‏b7fe6778): `op=drop_surah:4,55` وس4 وس55 بلا مداخل.
    و`drops=(55,)` منشورٌ س4 فيه تامّة (‏لاختبار الحجب بحذف مداخلَ منشورة)."""
    ids = [f"{d}:{a}" for d in drops for a in range(1, C[d - 1] + 1)]
    idx = {"riwaya": "hafs", "reciterId": "kurdi", "ayahCount": 6236, "refineVersion": "r1",
           "entries": _entries(skip_surahs=drops),
           "transform": {"op": "drop_surah:" + ",".join(str(d) for d in drops), "fromSha256": "9" * 64,
                         "fromKey": LIVE, "reason": "س55: الملفّ تبدّل عند الناشر", "reasonUser": OLD_USER,
                         "reasonCode": code}}
    return _with_missing(idx, ids, {"other": len(ids)})


def staged():
    """مرشّحُ ctc_splice mode=heard: س4 مبنيّةٌ من المسموع بلا 4:127، ويرث إعلانَ س55 حرفاً ومنشؤه المنشور."""
    p = published()
    ids = [f"{DROP}:{a}" for a in range(1, C[DROP - 1] + 1)] + [f"{S}:127"]
    idx = {"riwaya": "hafs", "reciterId": "kurdi", "ayahCount": 6236, "refineVersion": "r1",
           "entries": _entries(skip_surahs=(DROP,), skip_ayahs=(f"{S}:127",)),
           "transform": {"op": f"ctc_heardmap_splice:{S}", "dropSurah": [DROP], "fromKey": LIVE,
                         "fromSha256": LIVE_SHA, "reasonCode": p["transform"]["reasonCode"],
                         "reasonUser": OLD_USER}}
    return _with_missing(idx, ids, {"other": C[DROP - 1], "source_truncated": 1})


def run(idx, key, sha, **kw):
    args = dict(reason="4:127 غير منطوقة في 004.mp3", reason_user=NEW_USER, reason_code="SOURCE_TRUNCATED",
                from_sha=sha, from_key=key)
    args.update(kw)
    return drop_ayahs.drop_ayahs(idx, {S: list(ABSENT)}, copy.deepcopy(EV), **args)


class InheritFromStaged(unittest.TestCase):
    """الحالةُ الحقيقيّة: --already-absent على مرشّح ctc_splice المرحليّ."""

    def setUp(self):
        self.out = run(staged(), STAGE, STAGE_SHA, already_absent=True)
        self.tr = self.out["transform"]

    def test_declaration_carried_verbatim(self):
        self.assertEqual(self.tr["dropSurah"], [DROP])
        self.assertEqual(self.tr["reasonCode"], "OTHER")
        self.assertEqual(self.tr["reasonUser"], OLD_USER)

    def test_origin_is_the_published_key_with_full_sha(self):
        self.assertEqual((self.tr["fromKey"], self.tr["fromSha256"]), (LIVE, LIVE_SHA))
        self.assertEqual((self.tr["stagedFromKey"], self.tr["stagedFromSha256"]), (STAGE, STAGE_SHA))

    def test_per_surah_records(self):
        d = self.tr["declarations"]
        self.assertEqual(d[str(DROP)]["op"], "drop_surah")
        self.assertEqual(d[str(DROP)]["reasonCode"], "OTHER")
        self.assertEqual(d[str(DROP)]["reasonUser"], OLD_USER)
        self.assertEqual(d[str(S)], {"op": "declare_gap", "reasonCode": "SOURCE_TRUNCATED",
                                     "reasonUser": NEW_USER, "reason": "4:127 غير منطوقة في 004.mp3"})

    def test_op_is_not_a_new_drop(self):
        """op لا يبدأ بـdrop_surah ⇒ يمرّ index_gate بتحقّق inherited_drops من المنشور لا يتخطّاه."""
        self.assertEqual(self.tr["op"], f"declare_gap:{S}")

    def test_promote_gates_accept(self):
        ok, why = promote.declared_truncated_gaps(self.out, S)
        self.assertTrue(ok, why)
        self.assertIsNone(promote.index_gate(self.out, parent=published(), parent_sha=LIVE_SHA,
                                             owner_approved=frozenset({str(DROP)})))

    def test_entries_untouched(self):
        self.assertEqual(self.out["entries"], staged()["entries"])
        self.assertEqual(self.out["missing"], staged()["missing"])

    def test_next_tool_reads_the_same_records(self):
        """#102 فوق المخرَج: prior_declarations يقرأ السجلَّين حرفاً."""
        self.assertEqual(declarations.prior_declarations(self.out), self.tr["declarations"])


def published_live_form(code="SOURCE_TRUNCATED"):
    """منشورٌ حيٌّ بشكل المرشّح (‏س4 بلا 4:127 و`dropSurah=[55]`) — أصلٌ مباشرٌ بمفتاح المنشور لا المرحليّ."""
    p = staged()
    p["transform"].update(op="ctc_heardmap_splice:4", reasonCode=code, fromKey=LIVE, fromSha256="9" * 64)
    return p


class InheritFromPublished(unittest.TestCase):
    def test_published_key_parent(self):
        p = published_live_form()
        out = run(p, LIVE, LIVE_SHA, already_absent=True)
        tr = out["transform"]
        self.assertEqual((tr["fromKey"], tr["fromSha256"]), (LIVE, LIVE_SHA))
        self.assertNotIn("stagedFromKey", tr)
        self.assertEqual(tr["dropSurah"], [DROP])
        self.assertEqual(tr["reasonCode"], "SOURCE_TRUNCATED")
        self.assertTrue(promote.declared_truncated_gaps(out, S)[0])
        self.assertIsNone(promote.index_gate(out, parent=p, parent_sha=LIVE_SHA))

    def test_parent_declarations_field_carried_verbatim(self):
        p = staged()
        rec = {"op": "drop_surah", "reasonCode": "OTHER", "reasonUser": OLD_USER, "reason": "س55", "extra": [1, 2]}
        p["transform"]["declarations"] = {str(DROP): rec}
        out = run(p, STAGE, STAGE_SHA, already_absent=True)
        self.assertEqual(out["transform"]["declarations"][str(DROP)], rec)

    def test_removing_published_entries_refused_early(self):
        """⛔ التوريثُ لا يفتح بابَ حذفِ مداخلَ منشورةٍ تحت إعلانٍ موروث: حارسُ `inherited_drops` الذي لم يُمسّ
        يردّه في الترقية («مع فقد مداخل منشورة»)، فيُردّ في الأداة قبل أن تُنفق عليه البوّابات."""
        p = published(code="SOURCE_TRUNCATED", drops=(DROP,))
        with self.assertRaises(SystemExit) as cm:
            run(p, LIVE, LIVE_SHA)
        self.assertIn("--already-absent", str(cm.exception))
        self.assertIn("pin_heard", str(cm.exception))
        # والحارسُ في الترقية يردّه فعلاً لو بُني (‏يُبنى هنا يدويّاً بنقل الحقول الموروثة إلى مخرَجٍ بلا إعلان).
        q = copy.deepcopy(p)
        q["transform"] = {"op": "refine"}
        o = run(q, LIVE, LIVE_SHA)
        o["transform"].update(declarations.inherit_declaration(p, LIVE, LIVE_SHA))
        self.assertEqual(promote.index_gate(o, parent=p, parent_sha=LIVE_SHA),
                         "إعلان الغياب الموروث مع فقد مداخل منشورة")


class Refusals(unittest.TestCase):
    """تحوّرٌ لكلّ شرط: كلُّ واحدٍ يُردّ بنصّه."""

    def test_condition1_requested_surah_is_itself_declared(self):
        """الردُّ القديم حرفاً لأصلٍ يُطلب فيه آياتٌ من سورةٍ معلَنةٍ هي نفسها."""
        p = published()
        with self.assertRaises(SystemExit) as cm:
            run(p, LIVE, LIVE_SHA, already_absent=True)
        self.assertIn("ولا تورّث هذه الأداةُ ذلك الإعلان", str(cm.exception))
        p = staged()
        p["transform"]["dropSurah"] = [S, DROP]
        with self.assertRaises(SystemExit) as cm:
            run(p, STAGE, STAGE_SHA, already_absent=True)
        self.assertIn("ولا تورّث هذه الأداةُ ذلك الإعلان", str(cm.exception))

    def test_condition1b_prior_record_on_requested_surah(self):
        p = staged()
        p["transform"]["declarations"] = {str(S): {"op": "declare_gap", "reasonCode": "SOURCE_TRUNCATED",
                                                   "reasonUser": "x"}}
        with self.assertRaises(SystemExit) as cm:
            run(p, STAGE, STAGE_SHA, already_absent=True)
        self.assertIn("سجلُّ إعلانٍ", str(cm.exception))

    def test_condition2_staged_origin_unknown(self):
        for bad in ({"fromKey": STAGE}, {"fromSha256": "b7fe6778"}, {"fromKey": "timings/hafs/other.jz"}):
            p = staged()
            p["transform"].update(bad)
            with self.assertRaises(SystemExit) as cm:
                run(p, STAGE, STAGE_SHA, already_absent=True)
            self.assertIn("مجهولُ المنشأ", str(cm.exception))

    def test_condition3_declaration_without_reason_shown(self):
        for k in ("reasonCode", "reasonUser"):
            p = staged()
            del p["transform"][k]
            with self.assertRaises(SystemExit) as cm:
                run(p, STAGE, STAGE_SHA, already_absent=True)
            self.assertIn("بلا reasonCode وreasonUser", str(cm.exception))

    def test_condition3_declared_surah_has_entries(self):
        p = staged()
        p["transform"]["dropSurah"] = [DROP, 56]
        with self.assertRaises(SystemExit) as cm:
            run(p, STAGE, STAGE_SHA, already_absent=True)
        self.assertIn("يسمّي سوراً لها مداخل", str(cm.exception))

    def test_string_transform_refused(self):
        p = published(drops=(DROP,))
        p["transform"] = f"drop_surah:{DROP}"
        with self.assertRaises(SystemExit) as cm:
            run(p, LIVE, LIVE_SHA)
        self.assertIn("ولا تورّث هذه الأداةُ ذلك الإعلان", str(cm.exception))


class OutputMutationsCaughtByPromote(unittest.TestCase):
    """لو عُبث بالمخرَج لردّته حرّاسُ الترقية التي لم تُمسّ."""

    def setUp(self):
        self.out = run(staged(), STAGE, STAGE_SHA, already_absent=True)
        self.gate = lambda o: promote.index_gate(o, parent=published(), parent_sha=LIVE_SHA,
                                                 owner_approved=frozenset({str(DROP)}))

    def test_top_reason_changed(self):
        o = copy.deepcopy(self.out)
        o["transform"]["reasonCode"] = "SOURCE_TRUNCATED"
        self.assertIn("تبدل", self.gate(o) or "")

    def test_drop_list_lost(self):
        o = copy.deepcopy(self.out)
        del o["transform"]["dropSurah"]
        self.assertIn("سورٌ غائبةٌ كلّياً", self.gate(o) or "")

    def test_origin_changed(self):
        o = copy.deepcopy(self.out)
        o["transform"]["fromSha256"] = STAGE_SHA
        self.assertIn("بلا أصل منشور", self.gate(o) or "")

    def test_gap_record_code_changed(self):
        o = copy.deepcopy(self.out)
        o["transform"]["declarations"][str(S)]["reasonCode"] = "OTHER"
        self.assertFalse(promote.declared_truncated_gaps(o, S)[0])

    def test_gap_record_missing_falls_back_to_nothing(self):
        o = copy.deepcopy(self.out)
        del o["transform"]["declarations"][str(S)]
        self.assertFalse(promote.declared_truncated_gaps(o, S)[0])

    def test_without_approval_other_is_refused(self):
        self.assertIn("تبدل", promote.index_gate(self.out, parent=published(), parent_sha=LIVE_SHA) or "")


class NoDeclarationUnchanged(unittest.TestCase):
    def test_parent_without_drop_keeps_original_header(self):
        p = published(drops=(DROP,))
        p["entries"] = _entries()
        p["transform"] = {"op": "refine", "reasonCode": "OTHER", "reasonUser": OLD_USER}
        p = _with_missing(p, [], {})
        out = run(p, LIVE, LIVE_SHA)
        tr = out["transform"]
        self.assertNotIn("declarations", tr)
        self.assertNotIn("dropSurah", tr)
        self.assertEqual((tr["reasonCode"], tr["reasonUser"], tr["fromKey"]), ("SOURCE_TRUNCATED", NEW_USER, LIVE))


class SharedModuleUsers(unittest.TestCase):
    """المستعملون الثلاثة بالدالّة نفسها لا بنسخة."""

    def test_same_function_objects(self):
        self.assertIs(pin_heard.inherit_declaration, declarations.inherit_declaration)
        self.assertIs(pin_heard.declared_absent, declarations.declared_absent)
        self.assertIs(drop_surah.prior_declarations, declarations.prior_declarations)
        self.assertIs(drop_surah.merged_op, declarations.merged_op)

    def test_drop_ayahs_calls_the_shared_inherit(self):
        calls = []
        orig = declarations.inherit_declaration

        def spy(*a, **k):
            calls.append(a[1:])
            return orig(*a, **k)
        declarations.inherit_declaration = spy
        try:
            run(staged(), STAGE, STAGE_SHA, already_absent=True)
        finally:
            declarations.inherit_declaration = orig
        self.assertEqual(calls, [(STAGE, STAGE_SHA)])

    def test_pin_heard_and_drop_ayahs_agree(self):
        """ما يورّثه pin_heard من الأصل نفسه هو ما يورّثه drop_ayahs (‏الحقولُ العليا حرفاً)."""
        inh = pin_heard.inherit_declaration(staged(), STAGE, STAGE_SHA)
        tr = run(staged(), STAGE, STAGE_SHA, already_absent=True)["transform"]
        self.assertEqual({k: tr[k] for k in inh}, inh)

    def test_drop_surah_merged_op_over_output(self):
        out = run(staged(), STAGE, STAGE_SHA, already_absent=True)
        self.assertEqual(drop_surah.merged_op(drop_surah.prior_declarations(out)), f"drop_surah:{DROP}|declare_gap:{S}")


if __name__ == "__main__":
    unittest.main()
