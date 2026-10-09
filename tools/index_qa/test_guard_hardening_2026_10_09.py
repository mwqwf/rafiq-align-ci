"""(صيد 2026-10-09) اختباراتُ تقوية الحُرّاس: بلا شبكة وبلا دلو."""
import unittest

from tools.ci_fleet.agent_cmd import _forbidden_promote_args
from tools.index_qa import promote as P
from tools.index_qa import run as R


def _rep(salt, m, n, verdict=P.ACCEPTED, fatal=False):
    return {"source": "ci", "engine": "e1", "verdict": verdict, "fatal": fatal, "ts": 1,
            "sample": {"seed": hash(salt) % 10**6, "seedSalt": salt,
                       "severe": [m, n, [m / n, 0.0, 0.9]]}}


class PooledBlockedVerdicts(unittest.TestCase):
    def test_clean_pair_pools(self):
        self.assertIsNotNone(P.pooled_samples([_rep("a", 1, 200), _rep("b", 1, 400)]))

    def test_structural_reject_with_zero_rate_blocks(self):
        bad = _rep("b", 0, 400, verdict="مرفوض (خلل بنيوي)")
        self.assertIsNone(P.pooled_samples([_rep("a", 1, 200), bad]))

    def test_hold_verdict_blocks(self):
        bad = _rep("b", 0, 400, verdict="موقوف — قرارُ منتَجٍ مطلوب: x")
        self.assertIsNone(P.pooled_samples([_rep("a", 1, 200), bad]))

    def test_fatal_blocks(self):
        self.assertIsNone(P.pooled_samples([_rep("a", 1, 200), _rep("b", 0, 400, fatal=True)]))


class ForbiddenPromoteArgs(unittest.TestCase):
    T = "index_qa/promote.py"

    def test_forms(self):
        for a in (["--override", "x"], ["--override=x"], ["--allow-shrink", "k"],
                  ["--allow-shrink=k"], ["--over", "x"], ["--allow-s=k"]):
            self.assertIsNotNone(_forbidden_promote_args(self.T, a), a)

    def test_allowed(self):
        for a in (["--unfreeze", "k", "--reason", "r"], ["--only", "k", "--yes"],
                  ["--allow-truncated", "سبب"], ["--allow-truncated=سبب"]):
            self.assertIsNone(_forbidden_promote_args(self.T, a), a)

    def test_other_tool_unaffected_and_path_variants(self):
        self.assertIsNone(_forbidden_promote_args("index_qa/run.py", ["--override"]))
        self.assertIsNotNone(_forbidden_promote_args("./index_qa/./promote.py", ["--override"]))


class MissingKeyCode(unittest.TestCase):
    class _E(Exception):
        def __init__(self, code, msg=""):
            super().__init__(msg)
            self.response = {"Error": {"Code": code}}

    def test_code_not_text(self):
        self.assertTrue(P._is_missing(self._E("NoSuchKey")))
        self.assertFalse(P._is_missing(self._E("AccessDenied", "key timings/404/x")))
        self.assertFalse(P._is_missing(Exception("HTTP 404 in text only")))

    def test_manifest_read_error_does_not_write(self):
        class Cl:
            put = 0

            def get_object(self, **k):
                raise MissingKeyCode._E("AccessDenied")

            def put_object(self, **k):
                Cl.put += 1
        with self.assertRaises(SystemExit):
            P.write_manifest(Cl(), "b", "", {"riwaya": "h", "reciterId": "x", "updatedTs": 1})
        self.assertEqual(Cl.put, 0)


class T95(unittest.TestCase):
    def test_values(self):
        self.assertEqual(R.t95(2), 12.71)
        self.assertEqual(R.t95(11), 2.228)
        self.assertEqual(R.t95(31), 2.042)
        self.assertEqual(R.t95(41), 2.021)
        self.assertEqual(R.t95(50), 2.021)
        self.assertEqual(R.t95(100), 2.0)

    def test_monotone_and_conservative(self):
        prev = 99
        for k in range(2, 200):
            self.assertLessEqual(R.t95(k), prev)
            self.assertGreater(R.t95(k), 1.96)
            prev = R.t95(k)


if __name__ == "__main__":
    unittest.main()
