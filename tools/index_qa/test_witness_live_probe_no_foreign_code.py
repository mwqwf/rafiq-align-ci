# -*- coding: utf-8 -*-
"""حارس: أداةُ سبر الشاهد تعمل في مشغّلٍ يحمل أسرار الدلو، فلا تجلب شيفرةً من خارج main ولا تنفّذها.

وُلد من إيداع 4c7c24f6c5 (2026-11-10) الذي أضاف `--timing-repair-sha` لجلب timing_repair.py من إيداعٍ غير مدموج.
"""
import ast
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parent / "witness_live_probe.py"


class NoForeignCode(unittest.TestCase):
    def setUp(self):
        self.text = SRC.read_text(encoding="utf-8")
        self.tree = ast.parse(self.text)

    def test_no_sha_option(self):
        self.assertNotIn("--timing-repair-sha", self.text)
        self.assertNotIn("timing_repair_sha", self.text)

    def test_no_fetch_or_exec_modules(self):
        banned = {"subprocess", "tempfile", "importlib", "urllib", "requests", "base64"}
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                names = {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                names = {(node.module or "").split(".")[0]}
            else:
                continue
            self.assertFalse(names & banned, f"استيرادٌ ممنوع: {names & banned}")

    def test_no_exec_eval_or_api_ref(self):
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, {"exec", "eval", "compile", "__import__"})
        self.assertNotIn("?ref=", self.text)
        self.assertNotIn("gh api", self.text)

    def test_sys_path_only_own_dir(self):
        inserts = [l.strip() for l in self.text.splitlines() if "sys.path.insert" in l]
        self.assertEqual(inserts, ['sys.path.insert(0, str(Path(__file__).resolve().parent))'])


if __name__ == "__main__":
    unittest.main()
