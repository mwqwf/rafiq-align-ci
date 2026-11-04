#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""حارسُ «لا ترقيةَ تُنقص المنشور» مع الحجب الوسطيّ المعلَن (أمر المالك 2026-11-03).

يُقبل الإنقاصُ **فقط** لآياتٍ اجتازت سورتُها `declared_truncated_gaps` على المرشّح نفسِه وكانت
ضمن `absent` المعلَن؛ وكلُّ نقصٍ آخر (‏آيةٌ زائدةٌ مفقودة · دليلٌ ناقص · بلا فهرس) يبقى مردوداً.

    python -m unittest tools/index_qa/test_shrink_declared_gaps.py
"""
from __future__ import annotations

import copy
import gzip
import io
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "alignment_v3"))

import promote                                                   # noqa: E402
import test_drop_ayahs as T                                      # noqa: E402

TARGET = "timings/hafs/x.jz"
NOFILE = str(HERE / "__لا_ملف_اعتماد__.json")


class _Cl:
    def __init__(self, idx):
        self.body = gzip.compress(json.dumps(idx).encode())

    def get_object(self, **_kw):
        return {"Body": io.BytesIO(self.body)}


def _refusal(cand, idx=True):
    return promote.shrink_refusal(
        _Cl(T._idx()), "b", TARGET, len(cand["entries"]),
        new_ids=[e["ayahId"] for e in cand["entries"]], key="timings-staging/hafs/x.abcd1234.jz",
        approvals_path=NOFILE, idx=cand if idx else None)


class ShrinkDeclaredGaps(unittest.TestCase):
    def setUp(self):
        self.cand = T._make()          # 79:15,17,18 محجوبةٌ بدليل

    def test_declared_gaps_accepted(self):
        self.assertEqual(len(self.cand["entries"]), T.N - 3)
        self.assertIsNone(_refusal(self.cand))

    def test_without_index_still_refused(self):
        self.assertIn("أقلُّ مداخلَ", _refusal(self.cand, idx=False))

    def test_missing_evidence_refused(self):
        c = copy.deepcopy(self.cand)
        c["transform"]["truncatedGaps"][str(T.S)]["evidence"].pop(f"{T.S}:17")
        self.assertIsNotNone(_refusal(c))

    def test_extra_undeclared_loss_refused(self):
        c = copy.deepcopy(self.cand)
        c["entries"] = [e for e in c["entries"] if e["ayahId"] != f"{T.S}:30"]
        self.assertIsNotNone(_refusal(c))

    def test_other_surah_loss_refused(self):
        c = copy.deepcopy(self.cand)
        c["entries"] = [e for e in c["entries"] if e["ayahId"] != f"{T.S}:1"]
        self.assertIsNotNone(_refusal(c))

    def test_declared_but_without_user_reason_refused(self):
        c = copy.deepcopy(self.cand)
        c["transform"].pop("reasonUser", None)
        self.assertIsNotNone(_refusal(c))


if __name__ == "__main__":
    unittest.main()
