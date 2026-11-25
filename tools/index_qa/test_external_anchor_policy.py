#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""عقدُ مصدر المراسي المساندة voltarostudio: لا ترقية بلا شاهدَي Whisper ضمن 300م.ث.

لا شبكة ولا نموذج: الأرقام مصنوعة. لا يُستدعى Whisper مدفوع.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from tools.index_qa import external_anchor_policy as P
from tools.index_qa.promote import index_gate
from tools.index_qa import pin_heard


def rec(**kw):
    base = {
        "source": P.SOURCE_ID,
        "ayahId": "16:1",
        "startMs": 6920,
        "witnesses": [
            {"model": "whisper-medium", "startMs": 6900},
            {"model": "whisper-large-v3", "startMs": 6950},
        ],
    }
    base.update(kw)
    return base


class ExternalAnchorPolicyTest(unittest.TestCase):
    def test_agree_ms_matches_pin_heard(self):
        self.assertEqual(P.W_AGREE_MS, 300)
        self.assertEqual(P.W_AGREE_MS, pin_heard.W_AGREE_MS)

    def test_license_and_attribution_are_declared(self):
        self.assertEqual(P.LICENSE, "CC-BY 4.0")
        self.assertIn("Voltaro Studio", P.ATTRIBUTION)
        self.assertIn("CC-BY 4.0", P.ATTRIBUTION)
        self.assertIn("mp3quran.net", P.ATTRIBUTION)

    def test_registry_row_names_source_license_credit_and_gate(self):
        text = (Path(__file__).resolve().parents[2]
                / "docs" / "DATA_LICENSE_REGISTRY.md").read_text(encoding="utf-8")
        self.assertIn("voltarostudio/quran-word-timings-mp3quran", text)
        self.assertIn("CC-BY 4.0", text)
        self.assertIn(P.ATTRIBUTION, text)
        self.assertIn("300", text)
        self.assertIn("مراسٍ مساندة", text)
        self.assertIn("لا تُرقّى", text)
        self.assertIn("شاهدَي Whisper", text)

    def test_unknown_or_absent_source_does_not_block(self):
        self.assertIsNone(P.bound_block_reason({"source": "mp3quran", "startMs": 1}))
        self.assertIsNone(P.promotion_block_reason({}))
        self.assertIsNone(P.promotion_block_reason({"externalAnchors": []}))

    def test_ok_when_two_whisper_agree_within_300ms(self):
        self.assertIsNone(P.bound_block_reason(rec()))
        self.assertIsNone(P.promotion_block_reason({"externalAnchors": [rec()]}))

    def test_blocks_without_two_whisper_witnesses(self):
        why = P.bound_block_reason(rec(witnesses=[]))
        self.assertIn("شاهدَي Whisper", why)
        why = P.bound_block_reason(rec(witnesses=[{"model": "whisper-medium", "startMs": 6920}]))
        self.assertIn("وُجد 1", why)
        why = P.bound_block_reason(rec(witnesses=[
            {"model": "ctc", "startMs": 6920},
            {"model": "mms-fa", "startMs": 6920},
        ]))
        self.assertIn("وُجد 0", why)

    def test_blocks_when_a_witness_is_301ms_off(self):
        why = P.bound_block_reason(rec(witnesses=[
            {"model": "whisper-medium", "startMs": 6920},
            {"model": "whisper-large-v3", "startMs": 6920 + 301},
        ]))
        self.assertIn("7221", why or "")
        self.assertIn("لا يُرقّى", why)
        self.assertIn("300", why)

    def test_blocks_when_witnesses_disagree_with_each_other(self):
        # كلاهما ضمن 300 من الحدّ 1000 (700 و 1290) لكن الفرق بينهما 590.
        why = P.bound_block_reason(rec(startMs=1000, witnesses=[
            {"model": "whisper-medium", "startMs": 700},
            {"model": "whisper-large-v3", "startMs": 1290},
        ]))
        self.assertIn("يختلفان", why)

    def test_end_bound_also_requires_300ms(self):
        ok = rec(endMs=8000, witnesses=[
            {"model": "whisper-medium", "startMs": 6920, "endMs": 8010},
            {"model": "whisper-large-v3", "startMs": 6930, "endMs": 7990},
        ])
        self.assertIsNone(P.bound_block_reason(ok))
        bad = rec(endMs=8000, witnesses=[
            {"model": "whisper-medium", "startMs": 6920, "endMs": 8010},
            {"model": "whisper-large-v3", "startMs": 6930, "endMs": 8400},
        ])
        self.assertIn("نهاية", P.bound_block_reason(bad))

    def test_index_gate_blocks_unwitnessed_and_passes_silent_when_absent(self):
        why = index_gate({"externalAnchors": [rec(witnesses=[])]})
        self.assertIn("شاهدَي Whisper", why)
        # بلا الحقل: الحارس لا يتدخّل؛ باقي أبواب index_gate تردّ نقص الترويسة.
        why2 = index_gate({})
        self.assertNotIn("voltarostudio", why2 or "")
        self.assertIn("صقل", why2)

    def test_index_gate_allows_witnessed_anchor_to_reach_other_gates(self):
        why = index_gate({"externalAnchors": [rec()]})
        self.assertIsNotNone(why)
        self.assertNotIn("voltarostudio", why)
        self.assertNotIn("شاهدَي Whisper", why)


if __name__ == "__main__":
    unittest.main()
