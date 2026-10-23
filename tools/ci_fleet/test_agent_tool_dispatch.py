import json
import unittest
from unittest import mock
from pathlib import Path
import tempfile

from tools.ci_fleet import agent_cmd as A


class ToolDelegationTest(unittest.TestCase):
    def test_forbidden_tool_refused_with_answer(self):
        rc, out = A.do_tool({"tool": "evil/x.py", "args": [], "_name": "n1"})
        self.assertEqual(rc, 2)
        self.assertIn("غيرُ مسموحة", out)

    def test_override_refused(self):
        rc, out = A.do_tool({"tool": "index_qa/promote.py", "args": ["--over"], "_name": "n1"})
        self.assertEqual(rc, 2)

    def test_bad_name_refused(self):
        rc, _ = A.do_tool({"tool": "index_qa/run.py", "args": [], "_name": "../x"})
        self.assertEqual(rc, 3)

    def test_allowed_tool_dispatches_workflow_and_defers(self):
        with mock.patch.object(A, "run", return_value=(0, "ok")) as r:
            rc, out = A.do_tool({"tool": "index_qa/run.py",
                                 "args": ["--struct-only", "k"], "_name": "n_1"})
        self.assertIsNone(rc)
        a = r.call_args[0][0]
        self.assertEqual(a[:4], ["gh", "workflow", "run", "agent_tool.yml"])
        self.assertIn("name=n_1", a)
        self.assertIn("tool=index_qa/run.py", a)
        self.assertEqual(json.loads(a[a.index("-f", a.index("tool=index_qa/run.py") + 1) + 1][5:]),
                         ["--struct-only", "k"])

    def test_dispatch_failure_writes_answer(self):
        with mock.patch.object(A, "run", return_value=(1, "boom")):
            rc, out = A.do_tool({"tool": "index_qa/run.py", "args": [], "_name": "n"})
        self.assertEqual(rc, 1)

    def test_tool_main_writes_same_format_and_pushes(self):
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(A, "OUT_DIR", Path(d)), \
                mock.patch.object(A, "run", return_value=(0, "hello")), \
                mock.patch.object(A, "_push_answer") as push, \
                mock.patch.dict("os.environ", {"NAME": "nm", "TOOL": "index_qa/run.py", "ARGS": "[\"x\"]"}):
            A.tool_main()
            self.assertEqual((Path(d) / "nm.txt").read_text(encoding="utf-8"), "# rc=0\nhello")
            push.assert_called_once_with("nm", api_paths=["ops/out/nm.txt"])   # (2026-10-23) الواجهة احتياطٌ لخسارة سباق الدفع

    def test_tool_main_rechecks_guard(self):
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(A, "OUT_DIR", Path(d)), \
                mock.patch.object(A, "_push_answer"), \
                mock.patch.dict("os.environ", {"NAME": "nm", "TOOL": "evil.py", "ARGS": "[]"}):
            A.tool_main()
            self.assertTrue((Path(d) / "nm.txt").read_text(encoding="utf-8").startswith("# rc=2\n"))


if __name__ == "__main__":
    unittest.main()
