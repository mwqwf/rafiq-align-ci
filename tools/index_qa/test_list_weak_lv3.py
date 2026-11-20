#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختباراتُ جرد الآيات المقبولة بشاهد large-v3 (‏`list_weak_lv3.py`) — بلا دلو."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import heard_gate as H  # noqa: E402
import list_weak_lv3 as L  # noqa: E402

A, B = "a" * 64, "b" * 64


def state(src, sha, weak, run="1"):
    return {"src": src, "sha256": sha, "run": run, "weak": weak}


class Inventory(unittest.TestCase):
    def test_key_matches_gate(self):
        self.assertEqual(L.LV3_KEY, H.LV3_KEY)
        self.assertEqual(L.PREFIX, H.STATE_PREFIX)

    def test_published_key(self):
        self.assertEqual(L.published_key("timings-staging/hafs/kyat.1a2b3c4d.jz"), "timings/hafs/kyat.jz")
        self.assertIsNone(L.published_key("timings/hafs/kyat.jz"))
        self.assertIsNone(L.published_key(None))

    def test_lists_every_accepted_ayah_and_live_flag(self):
        live = {"timings/hafs/kyat.jz": A, "timings/warsh/basit_warsh.jz": "c" * 64}
        sts = [
            ("state-heard/x1.json", state("timings-staging/hafs/kyat.aaaaaaaa.jz", A,
                                          {"49": {H.LV3_KEY: [9, 11], "largeV3": {"detail": {"9": "whisper 1"}}},
                                           "24": {"weak": [3], "missing": [3]}})),
            ("state-heard/x2.json", state("timings-staging/warsh/basit_warsh.bbbbbbbb.jz", B,
                                          {"61": {H.LV3_KEY: [13]}})),
            ("state-heard/x3.json", state("timings-staging/hafs/new_reciter.cccccccc.jz", "c" * 64,
                                          {"2": {H.LV3_KEY: [5]}})),
            ("state-heard/x4.json", state("timings-staging/hafs/kyat.dddddddd.jz", A, {"49": {H.LV3_KEY: []}})),
        ]
        calls = []

        def live_sha(k):
            calls.append(k)
            if k not in live:
                raise KeyError(k)                    # منشورٌ غائب
            return live[k]
        rows = L.collect(sts, live_sha)
        got = [(r["published"], r["surah"], r["ayah"], r["live"]) for r in rows]
        self.assertEqual(got, [("timings/hafs/kyat.jz", 49, 9, True), ("timings/hafs/kyat.jz", 49, 11, True),
                               ("timings/warsh/basit_warsh.jz", 61, 13, False),
                               ("timings/hafs/new_reciter.jz", 2, 5, False)])
        self.assertEqual(rows[0]["detail"], "whisper 1")
        self.assertEqual(rows[0]["riwaya"], "hafs")
        self.assertEqual(len(calls), len(set(calls)))   # كلُّ منشورٍ يُقرأ مرّةً واحدة

    def test_old_states_without_field_are_silent(self):
        self.assertEqual(L.collect([("k", state("timings-staging/hafs/x.11111111.jz", A,
                                                {"4": {"weak": [1], "witnessed": [1]}})), ("bad", None)],
                                   lambda k: A), [])

    def test_tool_allowed_in_command_channel(self):
        sys.path.insert(0, os.path.join(HERE, "..", "ci_fleet"))
        import agent_cmd  # noqa: PLC0415
        self.assertIn("index_qa/list_weak_lv3.py", agent_cmd.ALLOWED_TOOLS)


if __name__ == "__main__":
    unittest.main()
