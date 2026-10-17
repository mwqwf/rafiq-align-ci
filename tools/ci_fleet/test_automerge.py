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
