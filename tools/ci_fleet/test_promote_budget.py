"""مهلةُ جولة الترقية وسردُ الملوح مرّةً واحدة (2026-09-25)."""
import types
import unittest
from unittest import mock

from tools.ci_fleet import restore_loop as loop


class _Pag:
    def __init__(self, calls):
        self.calls = calls

    def paginate(self, **_kw):
        self.calls.append(1)
        return [{"Contents": [{"Key": "state/audio-a-timings-staging_hafs_x.1.json"},
                              {"Key": "state/audio-b-timings-staging_hafs_x.1.json"},
                              {"Key": "state/openers-timings-staging_hafs_x.1.json"},
                              {"Key": "state/audio-a-timings-staging_hafs_y.2.json"}]}]


class _S3:
    def __init__(self, calls):
        self.calls = calls

    def get_paginator(self, _n):
        return _Pag(self.calls)


def _cand(name, gain=1):
    return {"key": f"timings-staging/hafs/{name}.1.jz", "live": f"timings/hafs/{name}.jz",
            "gain": gain, "riwaya": "hafs", "reciter": name}


class SaltCountTests(unittest.TestCase):
    def setUp(self):
        loop._AUDIO_KEYS = None

    def tearDown(self):
        loop._AUDIO_KEYS = None

    def test_lists_state_once_and_counts_only_audio(self):
        calls = []
        with mock.patch.object(loop, "s3", return_value=(_S3(calls), "b")):
            self.assertEqual(loop._salt_count("timings-staging/hafs/x.1.jz"), 2)
            self.assertEqual(loop._salt_count("timings-staging/hafs/y.2.jz"), 1)
            self.assertEqual(loop._salt_count("timings-staging/hafs/z.3.jz"), 0)
        self.assertEqual(len(calls), 1)


class PromoteBudgetTests(unittest.TestCase):
    def _run(self, cands, clock, budget):
        ran = []

        def fake_run(cmd, **_kw):
            if "--only" in cmd:
                ran.append((cmd[cmd.index("--only") + 1], "--yes" in cmd))
            return types.SimpleNamespace(stdout="⛔ لم يمرّ", returncode=0)

        with mock.patch.object(loop, "_staged_improvements", return_value=cands), \
             mock.patch.object(loop, "_salt_count", return_value=4), \
             mock.patch.object(loop, "maybe_diagnose"), \
             mock.patch.object(loop.subprocess, "run", side_effect=fake_run), \
             mock.patch.object(loop.time, "monotonic", side_effect=clock), \
             mock.patch.object(loop, "PROMOTE_BUDGET_S", budget):
            loop.cmd_promote(types.SimpleNamespace())
        return ran

    def test_all_candidates_checked_within_budget(self):
        ran = self._run([_cand("a"), _cand("b")], iter([0, 1, 2]), 100)
        self.assertEqual([k for k, _ in ran],
                         ["timings-staging/hafs/a.1.jz", "timings-staging/hafs/b.1.jz"])

    def test_stops_starting_new_candidates_after_budget(self):
        ran = self._run([_cand("a"), _cand("b"), _cand("c")], iter([0, 1, 500]), 100)
        self.assertEqual([k for k, _ in ran], ["timings-staging/hafs/a.1.jz"])

    def test_deferred_candidate_is_never_promoted(self):
        ran = self._run([_cand("a")], iter([0, 500]), 100)
        self.assertEqual(ran, [])

    def test_under_four_salts_not_counted(self):
        with mock.patch.object(loop, "_staged_improvements", return_value=[_cand("a")]), \
             mock.patch.object(loop, "_salt_count", return_value=3), \
             mock.patch.object(loop.subprocess, "run") as run:
            loop.cmd_promote(types.SimpleNamespace())
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
