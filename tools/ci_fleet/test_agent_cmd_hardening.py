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

    def test_redact_patterns(self):
        old = A.SECRET_FILE
        A.SECRET_FILE = Path("/nonexistent/x.json")
        try:
            cases = {
                "https://b.r2.dev/x.mp3?X-Amz-Algorithm=A&X-Amz-Credential=AKIAABCDEFGHIJKLMNOP%2F2026&X-Amz-Signature=deadbeef01&X-Amz-Security-Token=tok123 ok":
                    "https://b.r2.dev/x.mp3?X-Amz-Algorithm=A&X-Amz-Credential=***&X-Amz-Signature=***&X-Amz-Security-Token=*** ok",
                "t=ghs_" + "a" * 36: "t=***",
                "t=ghp_" + "B" * 36: "t=***",
                "t=gho_" + "c" * 30: "t=***",
                "t=github_pat_" + "D1_" * 10: "t=***",
                "id AKIAABCDEFGHIJKLMNOP end": "id *** end",
                "k=sk-ant-api03-abcDEF_123-xyz": "k=***",
                "Authorization: Bearer abc.def-123_XYZ==": "Authorization: Bearer ***",
            }
            for src, want in cases.items():
                self.assertEqual(A.redact(src), want, src)
            for plain in ("الآية غائبة عند القارئ — تعذّر التنزيل", "timings/hafs/husary_douri.jz",
                          "https://x.dev/a.mp3?v=1&n=2", "ghs_short", "Bearer x"):
                self.assertEqual(A.redact(plain), plain)
        finally:
            A.SECRET_FILE = old

    def test_redact_stdin_tool(self):
        import subprocess, sys
        r = subprocess.run([sys.executable, str(Path(A.__file__)), "--redact-stdin"],
                           input="Bearer abcdefgh12345 عربي", capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.stdout, "Bearer *** عربي")

    def test_redact_without_file(self):
        old = A.SECRET_FILE
        A.SECRET_FILE = Path("/nonexistent/x.json")
        try:
            self.assertEqual(A.redact("abc"), "abc")
        finally:
            A.SECRET_FILE = old


if __name__ == "__main__":
    unittest.main()
