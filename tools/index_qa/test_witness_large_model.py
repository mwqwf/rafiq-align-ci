#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""large-v3 شاهدٌ مقبول بالحرّاس نفسها (‏أمر القائد 2026-11-11)، وما سواه مردود كما كان.

    python -m unittest tools/index_qa/test_witness_large_model.py
"""
import re
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pin_heard as P  # noqa: E402


class LargeModel(unittest.TestCase):
    def test_models_exact(self):
        self.assertEqual(P.W_MODELS, ("small", "medium", "large-v3"))

    def test_other_models_and_int8_still_refused(self):
        for model, ct in (("tiny", "float32"), ("large", "float32"), ("large-v2", "float32"), ("large-v3", "int8")):
            self.assertFalse(model in P.W_MODELS and ct == "float32", (model, ct))

    def test_thresholds_unchanged(self):
        self.assertEqual((P.W_K, P.W_AGREE_MS, P.W_MIN_WORD_P, P.W_MEAN_WORD_P), (3, 300, 0.5, 0.7))

    def test_workflow_and_tool_offer_same_models(self):
        root = HERE.parent.parent
        yml = (root / ".github/workflows/whisper_witness.yml").read_text(encoding="utf-8")
        self.assertIn("options: [small, medium, large-v3]", yml)
        src = (HERE / "whisper_witness.py").read_text(encoding="utf-8")
        self.assertTrue(re.search(r'choices=\("small", "medium", "large-v3"\)', src))


if __name__ == "__main__":
    unittest.main()
