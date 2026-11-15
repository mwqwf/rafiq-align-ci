#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""إعلانُ الذيل المبتور المحفوظ في `priorOp` وحده لا يُمحى صامتاً (2026-11-15 · akri_qalun.e243c200).

    python -m unittest tools.index_qa.test_carry_tail_prior_op

العطبُ المقيس: ctc_splice كتب `op=ctc_heardmap_splice:4,10` وحفظ `declare_gap:24` في `priorOp`،
فأسقط drop_ayahs بعده `truncatedTail` لس24 بلا خبر، وردّ حارسُ البتر الترقية.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import drop_surah                                                # noqa: E402
from test_drop_surah_carry_tail import _parent                   # noqa: E402

REC = {"op": "declare_gap", "reasonCode": "SOURCE_TRUNCATED", "reasonUser": "النور ناقصة."}


def _idx(decl=REC, prior="drop_surah:4|declare_gap:24"):
    b = _parent(op="ctc_heardmap_splice:4,10")
    b["transform"]["priorOp"] = prior
    if decl is not None:
        b["transform"]["declarations"] = {"24": dict(decl)}
    return b


class CarryTailPriorOp(unittest.TestCase):
    def test_prior_op_tail_carried_with_its_record(self):
        b = _idx()
        # كما يناديها drop_ayahs: رمزٌ جديدٌ آخر، والسجلّاتُ الموروثة في prior.
        tails, names = drop_surah.carried_declared_tails(b, b["entries"], [4], "TIMING_UNDER_REPAIR", "x",
                                                         prior={"24": dict(REC)})
        self.assertEqual(names, [24])
        self.assertEqual(tails["24"]["published"], 30)

    def test_prior_op_tail_carried_by_source_truncated_drop(self):
        b = _idx()
        self.assertEqual(drop_surah.carried_declared_tails(b, b["entries"], [4], "SOURCE_TRUNCATED", "x")[1], [24])

    def test_prior_op_tail_without_record_refused(self):
        b = _idx(decl=None)
        with self.assertRaises(SystemExit):
            drop_surah.carried_declared_tails(b, b["entries"], [4], "SOURCE_TRUNCATED", "x")

    def test_prior_op_tail_with_wrong_code_refused(self):
        b = _idx(decl={**REC, "reasonCode": "OTHER"})
        with self.assertRaises(SystemExit):
            drop_surah.carried_declared_tails(b, b["entries"], [4], "SOURCE_TRUNCATED", "x")

    def test_prior_op_tail_without_user_text_refused(self):
        b = _idx(decl={**REC, "reasonUser": "  "})
        with self.assertRaises(SystemExit):
            drop_surah.carried_declared_tails(b, b["entries"], [4], "SOURCE_TRUNCATED", "x")

    def test_prior_op_tail_prefix_mismatch_refused(self):
        b = _idx()
        kept = [e for e in b["entries"] if e["ayahId"] != "24:7"]
        with self.assertRaises(SystemExit):
            drop_surah.carried_declared_tails(b, kept, [4], "SOURCE_TRUNCATED", "x")

    def test_prior_op_without_declare_gap_carries_nothing(self):
        b = _idx(prior="drop_surah:4")
        self.assertEqual(drop_surah.carried_declared_tails(b, b["entries"], [4], "SOURCE_TRUNCATED", "x"), ({}, []))


if __name__ == "__main__":
    unittest.main()
