import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))
import automerge as am  # noqa: E402

REPO = "mwqwf/QuranRafiq"
NOW = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
OLD = (NOW - timedelta(minutes=30)).isoformat()


def pr(**kw):
    d = {"head": {"ref": "claude/x", "repo": {"full_name": REPO}},
         "user": {"login": "mwqwf"}, "draft": False, "labels": [],
         "mergeable": True, "mergeable_state": "clean"}
    d.update(kw)
    return d


def run(p=None, files=(), checks=(), runs=(), status=None, date=OLD):
    return am.decide(p or pr(), list(files), list(checks), list(runs),
                     status or {"state": "pending", "statuses": []},
                     NOW, 5, REPO, date)


OKC = [{"name": "a", "status": "completed", "conclusion": "success"}]


class T(unittest.TestCase):
    def test_ok(self):
        self.assertTrue(run(checks=OKC)[0])

    def test_non_claude(self):
        p = pr(); p["head"]["ref"] = "feature/x"
        self.assertFalse(run(p)[0])

    def test_fork(self):
        p = pr(); p["head"]["repo"] = {"full_name": "evil/QuranRafiq"}
        self.assertFalse(run(p)[0])

    def test_draft(self):
        self.assertFalse(run(pr(draft=True))[0])

    def test_hold(self):
        self.assertFalse(run(pr(labels=[{"name": "hold"}]))[0])

    def test_failed_check(self):
        c = [{"name": "a", "status": "completed", "conclusion": "failure"}]
        self.assertFalse(run(checks=c)[0])

    def test_running_check(self):
        c = [{"name": "a", "status": "in_progress", "conclusion": None}]
        self.assertFalse(run(checks=c)[0])

    def test_running_run(self):
        self.assertFalse(run(runs=[{"name": "w", "status": "queued"}])[0])

    def test_recent_head(self):
        self.assertFalse(run(date=(NOW - timedelta(minutes=1)).isoformat())[0])

    def test_release_without_label(self):
        self.assertFalse(run(files=[{"filename": "store/release-request.json"}])[0])

    def test_release_with_label(self):
        p = pr(labels=[{"name": "release-approved"}])
        self.assertTrue(run(p, files=[{"filename": "store/release-request.json"}])[0])

    def test_mergeable_null(self):
        self.assertFalse(run(pr(mergeable=None))[0])

    def test_dirty(self):
        self.assertFalse(run(pr(mergeable_state="dirty"))[0])

    def test_failed_status(self):
        s = {"state": "failure", "statuses": [{"state": "failure"}]}
        self.assertFalse(run(status=s)[0])


if __name__ == "__main__":
    unittest.main()


class RollupFallbackTest(unittest.TestCase):
    """بديل check-runs عبر GraphQL حين يرفضه توكن fine-grained في المستودع الخاص."""

    def data(self, oid, nodes):
        return {"data": {"repository": {"pullRequest": {"commits": {"nodes": [
            {"commit": {"oid": oid, "statusCheckRollup": {"contexts": {"nodes": nodes}}}}]}}}}}

    def test_maps_and_lowercases(self):
        out = am.rollup_to_checks(self.data("abc", [
            {"__typename": "CheckRun", "name": "test", "status": "COMPLETED", "conclusion": "SUCCESS"},
            {"__typename": "CheckRun", "name": "emu", "status": "IN_PROGRESS", "conclusion": None},
            {"__typename": "StatusContext"}]), "abc")
        self.assertEqual(out, [{"name": "test", "status": "completed", "conclusion": "success"},
                               {"name": "emu", "status": "in_progress", "conclusion": None}])

    def test_pending_or_failed_blocks_merge(self):
        for st, co in (("IN_PROGRESS", None), ("COMPLETED", "FAILURE")):
            checks = am.rollup_to_checks(self.data("abc", [
                {"__typename": "CheckRun", "name": "t", "status": st, "conclusion": co}]), "abc")
            ok, _ = run(checks=checks)
            self.assertFalse(ok)

    def test_head_mismatch_raises(self):
        with self.assertRaises(ValueError):
            am.rollup_to_checks(self.data("old", []), "abc")


class RollupPartialTest(unittest.TestCase):
    """حين تُحجب بعض الفحوص عن التوكن يُحكم بالحالة الإجمالية وحدها."""

    def data(self, state):
        return {"data": {"repository": {"pullRequest": {"commits": {"nodes": [
            {"commit": {"oid": "abc", "statusCheckRollup": {"state": state, "contexts": None}}}]}}}}}

    def test_only_success_merges(self):
        for state, want in (("SUCCESS", True), ("PENDING", False), ("FAILURE", False),
                            ("ERROR", False), (None, False)):
            ok, _ = run(checks=am.rollup_to_checks(self.data(state), "abc", partial=True))
            self.assertEqual(ok, want, state)
