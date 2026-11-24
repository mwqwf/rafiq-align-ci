"""الوراثةُ عن وراثةٍ مأذونةٍ في كلّ حلقة (إذن المالك 2026-11-24 t14u).

الحالةُ الحيّة: qurashi eb8dc8c6 (op=heard_pin:46 · OTHER · dropSurah=[10]) ورث س10 عن 150b6e29 (op=drop_surah:10)
بصفّ موافقةٍ لمفتاحه؛ فإعادةُ محاذاة س22 فوقه كانت تُردّ لأنّ الأصل ليس drop_surah. واختباراتُ الطفرات تُثبت بقاء كلّ شرطٍ آخر.
"""
import copy
import unittest
from tools.index_qa.promote import inherited_drops

NOTE = "توقيت هذه السورة لهذا القارئ قيد الإصلاح"


class InheritedApprovedChainTest(unittest.TestCase):
    def setUp(self):
        self.sha = "e" * 64
        self.parent = {"riwaya": "hafs", "reciterId": "reader", "entries": [{"ayahId": "1:1"}, {"ayahId": "22:1"}],
                       "transform": {"op": "heard_pin:46", "reasonCode": "OTHER", "reasonUser": NOTE,
                                     "dropSurah": [10]}}
        self.idx = copy.deepcopy(self.parent)
        self.idx["transform"].update(op="realign_surah:22", fromKey="timings/hafs/reader.jz", fromSha256=self.sha)

    def run_(self, own=frozenset({10}), par=frozenset({10})):
        return inherited_drops(self.idx, self.parent, self.sha, own, parent_approved=par)

    def test_chain_with_both_rows_inherits(self):
        self.assertEqual(self.run_(), ({"10"}, None))

    def test_without_parent_row_refuses_as_before(self):
        self.assertIsNotNone(self.run_(par=frozenset())[1])
        self.assertIsNotNone(self.run_(par=frozenset({22}))[1])

    def test_without_candidate_row_refuses(self):
        self.assertIsNotNone(self.run_(own=frozenset())[1])

    def test_changed_notice_or_code_refuses(self):
        self.idx["transform"]["reasonUser"] = "نصّ آخر"
        self.assertIsNotNone(self.run_()[1])
        self.idx["transform"]["reasonUser"] = NOTE
        self.idx["transform"]["reasonCode"] = "TIMING_UNDER_REPAIR"
        self.assertIsNotNone(self.run_()[1])

    def test_new_drop_refuses(self):
        self.idx["transform"]["dropSurah"] = [10, 22]
        self.idx["entries"] = [{"ayahId": "1:1"}]
        self.assertIsNotNone(self.run_(own=frozenset({10, 22}), par=frozenset({10, 22}))[1])

    def test_lost_entries_refuse(self):
        self.idx["entries"] = [{"ayahId": "22:1"}]
        self.assertIsNotNone(self.run_()[1])

    def test_wrong_parent_sha_refuses(self):
        self.assertIsNotNone(inherited_drops(self.idx, self.parent, "f" * 64, frozenset({10}),
                                             parent_approved=frozenset({10}))[1])

    def test_unknown_code_refuses(self):
        self.parent["transform"]["reasonCode"] = "X"
        self.idx["transform"]["reasonCode"] = "X"
        self.assertIsNotNone(self.run_()[1])


if __name__ == "__main__":
    unittest.main()
