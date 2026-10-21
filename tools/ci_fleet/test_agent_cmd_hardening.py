#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يختبر تحصينَ `agent_cmd` (2026-10-21): رفضُ وسائط secure/r2_credentials/`..`، وحجبُ السرّ من الجواب.

    python tools/ci_fleet/test_agent_cmd_hardening.py
"""
import json
import tempfile
import unittest
from pathlib import Path

from tools.ci_fleet import agent_cmd as A


class HardeningTest(unittest.TestCase):
    def test_rejects_sensitive_args(self):
        for bad in ("secure/r2_credentials.json", "--creds=secure/x", "./secure", "a/../b",
                    "--key=../../etc/passwd", "R2_Credentials.json", "/etc/passwd",
                    "--out=/root/.ssh/id", "secure\\\\x"):
            r = A.guard_tool("index_qa/run.py", [bad])
            self.assertIsNotNone(r, bad)
            self.assertEqual(r[0], 2)

    def test_accepts_legit_args(self):
        for ok in ("--struct-only", "timings/hafs/x.jz", "--key=catalog/reciters.json",
                   "تصحيح53:39..62 و91:14..15", "3/8", "douri/husary_douri", "--reason=a/b..c"):
            self.assertIsNone(A.guard_tool("index_qa/run.py", [ok]), ok)

    def test_redact(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "r2_credentials.json"
            f.write_text(json.dumps({"access_key_id": "AKIAEXAMPLE1234", "n": {"secret": "s3cr3t-VALUE-xyz"},
                                     "short": "ab"}), encoding="utf-8")
            old = A.SECRET_FILE
            A.SECRET_FILE = f
            try:
                out = A.redact("k=AKIAEXAMPLE1234 s=s3cr3t-VALUE-xyz ab")
            finally:
                A.SECRET_FILE = old
        self.assertEqual(out, "k=*** s=*** ab")

    def test_redact_without_file(self):
        old = A.SECRET_FILE
        A.SECRET_FILE = Path("/nonexistent/x.json")
        try:
            self.assertEqual(A.redact("abc"), "abc")
        finally:
            A.SECRET_FILE = old


if __name__ == "__main__":
    unittest.main()
