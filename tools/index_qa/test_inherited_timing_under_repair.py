"""وراثةُ الحجب المؤقّت برمز TIMING_UNDER_REPAIR بشروط OTHER نفسِها حرفاً (2026-11-14).

الحالةُ الحيّة: benkirane_warsh 7bafad18 (op=drop_surah:13,23 · TIMING_UNDER_REPAIR) وkyat 5e899ca6
(op=drop_surah:21,28) — مرشّحٌ يسترجع سورةً ويورّث الأخرى كان يُردّ بـ«بيان سبب الغياب الموروث مفقود أو تبدل»
لأنّ الوراثة لم تعرف إلا OTHER. واختباراتُ الطفرات أدناه تُثبت أنّ كلَّ شرطٍ آخر باقٍ.
"""
import copy
import unittest
from tools.index_qa.promote import inherited_drops

TUR = "TIMING_UNDER_REPAIR"


class InheritedTimingUnderRepairTest(unittest.TestCase):
    def setUp(self):
        self.sha = "b" * 64
        self.parent = {"riwaya": "warsh", "reciterId": "reader", "entries": [{"ayahId": "1:1"}],
                       "transform": {"op": "drop_surah:13,23", "reasonCode": TUR, "reasonUser": "قيد الإصلاح"}}
        self.idx = copy.deepcopy(self.parent)
        self.idx["entries"].append({"ayahId": "23:1"})
        self.idx["transform"].update(op="declare_gap:23", dropSurah=[13],
                                     fromKey="timings/warsh/reader.jz", fromSha256=self.sha)

    def run_(self, approved=frozenset({13})):
        return inherited_drops(self.idx, self.parent, self.sha, approved)

    def test_inherits_with_drop_surah_parent_and_owner_row(self):
        self.assertEqual(self.run_(), ({"13"}, None))

    def test_without_owner_approval_refuses(self):
        self.assertIsNotNone(self.run_(frozenset())[1])
        self.assertIsNotNone(self.run_(frozenset({23}))[1])

    def test_inheritance_of_inheritance_refuses(self):
        self.parent["transform"]["op"] = "declare_gap:23"
        self.assertIsNotNone(self.run_()[1])

    def test_changed_code_or_notice_refuses(self):
        self.idx["transform"]["reasonCode"] = "OTHER"
        self.assertIsNotNone(self.run_()[1])
        self.idx["transform"]["reasonCode"] = TUR
        self.idx["transform"]["reasonUser"] = "غيره"
        self.assertIsNotNone(self.run_()[1])
        self.idx["transform"]["reasonUser"] = ""
        self.parent["transform"]["reasonUser"] = ""
        self.assertIsNotNone(self.run_()[1])

    def test_other_codes_still_refused(self):
        for code in ("NO_PUBLISHED_RECORDING", "UNKNOWN", None):
            self.parent["transform"]["reasonCode"] = self.idx["transform"]["reasonCode"] = code
            self.assertIsNotNone(self.run_()[1], code)

    def test_new_or_present_surah_refuses(self):
        self.idx["transform"]["dropSurah"] = [13, 50]
        self.assertIsNotNone(self.run_(frozenset({13, 50}))[1])
        self.idx["transform"]["dropSurah"] = [13]
        self.idx["entries"].append({"ayahId": "13:1"})
        self.assertIsNotNone(self.run_()[1])

    def test_losing_published_entry_refuses(self):
        self.parent["entries"].append({"ayahId": "2:1"})
        self.assertIsNotNone(self.run_()[1])

    def test_wrong_parent_sha_refuses(self):
        self.assertIsNotNone(inherited_drops(self.idx, self.parent, "c" * 64, frozenset({13}))[1])


if __name__ == "__main__":
    unittest.main()
