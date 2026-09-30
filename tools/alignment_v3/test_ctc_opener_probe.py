#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""قاعدةُ التأكيد في `ctc_opener_probe.confirm` — بأرقامٍ مقيسةٍ 2026-09-29/30 لا مفترَضة."""
import ast
import unittest
from pathlib import Path

SRC = (Path(__file__).resolve().parent / "ctc_opener_probe.py").read_text(encoding="utf-8")
_ns = {}
for node in ast.parse(SRC).body:              # الدالّةُ وثوابتُها وحدها — بلا torch ولا شبكة
    if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") in ("CONFIRM_MS", "MIN_CONF"):
        exec(compile(ast.Module([node], []), "c", "exec"), _ns)
    if isinstance(node, ast.FunctionDef) and node.name == "confirm":
        exec(compile(ast.Module([node], []), "c", "exec"), _ns)
confirm = _ns["confirm"]


class Confirm(unittest.TestCase):
    def test_nufais_83_confirmed(self):          # الفهرس 440 · CTC 3192 ثقة 0.696
        self.assertTrue(confirm(440, 3192, 0.696))

    def test_harthi_89_confirmed(self):          # الفهرس 0 · CTC 4743 ثقة 0.74
        self.assertTrue(confirm(0, 4743, 0.74))

    def test_nufais_4_false_positive_dropped(self):   # الفهرس 8000 · CTC 7545
        self.assertFalse(confirm(8000, 7545, 0.621))

    def test_fixed_97_dropped(self):             # بعد الإصلاح: 3012 · CTC 3443
        self.assertFalse(confirm(3012, 3443, 0.74))

    def test_rabbani_55_confirmed_at_calibrated_conf(self):   # الفهرس 0 · فرق 2594 ثقة 0.438
        self.assertTrue(confirm(0, 2594, 0.438))

    def test_negative_diff_never_confirmed(self):   # ryan 99: −552 بثقة 0.707
        self.assertFalse(confirm(3000, 2448, 0.707))

    def test_low_conf_not_confirmed(self):       # zaml 111: ثقة 0.0
        self.assertFalse(confirm(0, 3151, 0.0))

    def test_none_not_confirmed(self):
        self.assertFalse(confirm(0, None, None))


if __name__ == "__main__":
    unittest.main()
