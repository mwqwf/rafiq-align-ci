#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest

from tools.index_qa.registered_source_quality_plan import selected_checks


class Selection(unittest.TestCase):
    def test_default_preserves_full_matrix(self):
        self.assertEqual(selected_checks("", True),
                         ["openers", "census", "rs1", "rs2", "rs3", "rs4", "heard"])

    def test_default_without_parent_omits_heard(self):
        self.assertNotIn("heard", selected_checks("", False))

    def test_single_failed_check_can_be_remeasured(self):
        self.assertEqual(selected_checks("heard", True), ["heard"])

    def test_unknown_duplicate_and_unbound_heard_are_rejected(self):
        for raw, parent in (("heard,heard", True), ("weak", True), ("heard", False)):
            with self.subTest(raw=raw, parent=parent), self.assertRaises(ValueError):
                selected_checks(raw, parent)


if __name__ == "__main__":
    unittest.main()
