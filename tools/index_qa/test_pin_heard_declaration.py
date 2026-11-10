#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`pin_heard` يحمل إعلانَ الغياب الموروث حرفاً (‏2026-11-10 · الكردي س55) كما يحمله `splice_surah`.

  ① الإعلانُ يُورَّث: `dropSurah` نفسُها و`reasonCode`/`reasonUser` بنصّهما حرفاً.
  ② لا تُضاف سورةٌ محجوبةٌ جديدة، ولا يُثبَّت ما هو معلَنُ الغياب، ولا إعلانٌ يسمّي سورةً حاضرة.
  ③ التثبيتُ يمسّ حدودَ السورة المثبَّتة وحدَها (‏ومداخلُ الأصل كلُّها باقية).
  ④ الأصلُ المرحليّ: المنشأُ هو المنشورُ الذي صدر عنه الإعلان، والمباشرُ في `stagedFromKey`؛ ومنشأٌ مجهولٌ يُردّ.
  ⑤ بلا إعلانٍ: التحويلُ كما كان حرفاً.
  ⑥ وما يُنتج يجتاز `promote.inherited_drops` بلا مساسٍ به.

    python -m unittest tools/index_qa/test_pin_heard_declaration.py
"""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from pin_heard import declared_absent, inherit_declaration, pin  # noqa: E402
from test_pin_heard import HMAP, _idx                             # noqa: E402

LIVE = "timings/hafs/r.jz"
LIVE_SHA = "1" * 64
STAGE = "timings-staging/hafs/r.22222222.jz"
STAGE_SHA = "2" * 64
CODE, USER = "SOURCE_TRUNCATED", "تسجيل هذه السورة عند الناشر ناقص، فبعض آياتها غير متاح بصوت هذا القارئ."


def _declared(op="drop_surah:4", drop=None, staged=False):
    i = _idx()
    i.update(riwaya="hafs", reciterId="r")
    tr = {"op": op, "reasonCode": CODE, "reasonUser": USER}
    if drop is not None:
        tr["dropSurah"] = drop
    if staged:
        tr.update(fromKey=LIVE, fromSha256=LIVE_SHA)
    i["transform"] = tr
    return i


class Declaration(unittest.TestCase):
    def test_inherited_verbatim_from_live(self):
        i = _declared()
        got = inherit_declaration(i, LIVE, LIVE_SHA)
        self.assertEqual(got["dropSurah"], [4])
        self.assertEqual((got["reasonCode"], got["reasonUser"]), (CODE, USER))
        self.assertEqual((got["fromKey"], got["fromSha256"]), (LIVE, LIVE_SHA))
        self.assertNotIn("stagedFromKey", got)

    def test_staged_parent_keeps_published_origin(self):
        i = _declared(op="ctc_heardmap_splice:55", drop=[4], staged=True)
        got = inherit_declaration(i, STAGE, STAGE_SHA)
        self.assertEqual(got["dropSurah"], [4])
        self.assertEqual((got["fromKey"], got["fromSha256"]), (LIVE, LIVE_SHA))
        self.assertEqual((got["stagedFromKey"], got["stagedFromSha256"]), (STAGE, STAGE_SHA))

    def test_staged_parent_unknown_origin_refused(self):
        for tr in ({"fromKey": "timings-staging/hafs/r.33333333.jz", "fromSha256": "3" * 64},
                   {"fromKey": "timings/hafs/other.jz", "fromSha256": "3" * 64},
                   {"fromKey": LIVE, "fromSha256": "abc"}):
            i = _declared(op="ctc_heardmap_splice:55", drop=[4])
            i["transform"].update(tr)
            with self.assertRaises(SystemExit, msg=str(tr)):
                inherit_declaration(i, STAGE, STAGE_SHA)

    def test_no_new_drop_and_union_of_both_forms(self):
        i = _declared(op="drop_surah:4,9", drop=[5])
        self.assertEqual(declared_absent(i), [4, 5, 9])
        self.assertEqual(inherit_declaration(i, LIVE, LIVE_SHA)["dropSurah"], [4, 5, 9])

    def test_declared_surah_present_refused(self):
        i = _declared(op="drop_surah:78")                      # 78 لها مدخلٌ في الأصل
        with self.assertRaises(SystemExit):
            declared_absent(i)

    def test_pin_declared_surah_refused(self):
        i = _declared(op="drop_surah:77")
        i["entries"] = [e for e in i["entries"] if not e["ayahId"].startswith("77:")]
        with self.assertRaises(SystemExit):
            declared_absent(i, 77)

    def test_without_reason_refused(self):
        for k in ("reasonCode", "reasonUser"):
            i = _declared()
            i["transform"].pop(k)
            with self.assertRaises(SystemExit, msg=k):
                inherit_declaration(i, LIVE, LIVE_SHA)

    def test_no_declaration_unchanged(self):
        i = _idx()
        self.assertEqual(inherit_declaration(i, LIVE, LIVE_SHA), {"fromSha256": LIVE_SHA, "fromKey": LIVE})

    def test_pin_on_declared_parent_touches_pinned_surah_only(self):
        i = _declared()
        out, _report, changed = pin(i, 77, copy.deepcopy(HMAP), {2: 30000, 3: 40000, 4: 50000}, {1: 10000})
        before = {e["ayahId"]: e for e in i["entries"]}
        after = {e["ayahId"]: e for e in out["entries"]}
        self.assertEqual(set(before), set(after))               # لا مدخلَ يضيع ولا يُضاف
        self.assertEqual(after["78:1"], before["78:1"])          # سورةٌ أخرى كما هي حرفاً
        touched = {a for a in after if after[a] != before[a]}
        self.assertTrue(touched and all(a.startswith("77:") for a in touched))
        self.assertEqual(out["transform"], i["transform"])       # pin() لا يمسّ التحويل؛ يكتبه main بالموروث

    def test_result_passes_promote_inherited_drops(self):
        try:
            import promote
        except Exception as ex:                                   # noqa: BLE001
            self.skipTest(f"promote غير متاح: {ex}")
        parent = _declared()
        parent["entries"] = [e for e in parent["entries"]]
        cand = copy.deepcopy(parent)
        cand["transform"] = {"op": "heard_pin:77", **inherit_declaration(parent, LIVE, LIVE_SHA)}
        got, why = promote.inherited_drops(cand, parent, LIVE_SHA)
        self.assertIsNone(why)
        self.assertEqual(got, {"4"})
        bad = copy.deepcopy(cand); bad["transform"]["reasonUser"] = "نصٌّ آخر"
        self.assertIsNotNone(promote.inherited_drops(bad, parent, LIVE_SHA)[1])


if __name__ == "__main__":
    unittest.main()
