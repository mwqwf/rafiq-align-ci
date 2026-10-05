#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختبارات قياس التكلفة: الصفحات والفشل لا ينتجان شهادة مجانية كاذبة."""
from __future__ import annotations

import json
import io
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tools.ci_fleet import free_compute_audit as audit


class FreeComputeAuditTest(unittest.TestCase):
    @staticmethod
    def artifact(identity, *, expired=False, size=10):
        return {"id": identity, "name": f"artifact-{identity}", "expired": expired,
                "size_in_bytes": size}

    def test_all_pages_count_only_unexpired_artifact_bytes(self):
        get = Mock(side_effect=[
            {"total_count": 101, "artifacts": [self.artifact(i) for i in range(100)]},
            {"total_count": 101, "artifacts": [self.artifact(100, expired=True, size=999)]},
        ])
        summary = audit.artifact_summary(audit.pages(get, "repos/example/actions/artifacts", "artifacts"))
        self.assertTrue(summary["readComplete"])
        self.assertEqual(summary["pagesRead"], 2)
        self.assertEqual(summary["observedActiveBytes"], 1000)
        self.assertEqual(summary["observedActiveCount"], 100)
        self.assertEqual(summary["observedExpiredCount"], 1)
        self.assertTrue(get.call_args_list[0].args[0].endswith("per_page=100&page=1"))
        self.assertTrue(get.call_args_list[1].args[0].endswith("per_page=100&page=2"))

    def test_page_failure_preserves_partial_evidence_without_completeness(self):
        get = Mock(side_effect=[
            {"total_count": 2, "artifacts": [self.artifact(1)]},
            audit.ReadError("رُفضت قراءة GitHub (HTTP 403)"),
        ])
        summary = audit.artifact_summary(audit.pages(get, "fixed", "artifacts"))
        self.assertFalse(summary["readComplete"])
        self.assertEqual(summary["observedActiveBytes"], 10)
        self.assertEqual(summary["reportedTotal"], 2)
        self.assertIn("403", summary["errors"][0])

    def test_duplicate_page_never_double_counts_artifact(self):
        get = Mock(side_effect=[
            {"total_count": 2, "artifacts": [self.artifact(1)]},
            {"total_count": 2, "artifacts": [self.artifact(1)]},
        ])
        summary = audit.artifact_summary(audit.pages(get, "fixed", "artifacts"))
        self.assertFalse(summary["readComplete"])
        self.assertEqual(summary["observedActiveBytes"], 10)

    def test_changing_total_or_page_cap_prevents_complete_snapshot(self):
        for second, limit in (({"total_count": 3, "artifacts": [self.artifact(2)]}, 200),
                              ({"total_count": 2, "artifacts": [self.artifact(2)]}, 1)):
            with self.subTest(limit=limit):
                get = Mock(side_effect=[{"total_count": 2, "artifacts": [self.artifact(1)]}, second])
                result = audit.pages(get, "fixed", "artifacts", max_pages=limit)
                self.assertFalse(result["readComplete"])
                self.assertTrue(result["errors"])

    def test_missing_expired_flag_is_an_error_not_an_expired_artifact(self):
        summary = audit.artifact_summary({"items": [{"id": 1, "size_in_bytes": 999}],
            "readComplete": True, "errors": [], "pagesRead": 1, "reportedTotal": 1})
        self.assertFalse(summary["readComplete"])
        self.assertEqual(summary["invalidCount"], 1)

    def test_public_repo_and_empty_storage_never_prove_account_quota(self):
        def get(endpoint):
            if endpoint == audit.PREFIX:
                return {"full_name": audit.REPO, "private": False, "visibility": "public"}
            if endpoint.endswith("actions/cache/usage"):
                return {"active_caches_count": 0, "active_caches_size_in_bytes": 0}
            if "/actions/artifacts?" in endpoint:
                return {"total_count": 0, "artifacts": []}
            if "/actions/runners?" in endpoint:
                raise audit.ReadError("رُفضت قراءة GitHub (HTTP 403)")
            self.fail(endpoint)
        report = audit.audit(get, workflows=())
        self.assertTrue(report["artifacts"]["readComplete"])
        self.assertFalse(report["selfHostedRunners"]["readComplete"])
        self.assertFalse(report["costDecision"]["freeExecutionVerified"])
        self.assertFalse(report["costDecision"]["accountArtifactQuotaKnown"])

    def test_cache_read_failure_is_recorded(self):
        result = audit.read_section(Mock(side_effect=audit.ReadError("تعذّرت القراءة")),
                                    "fixed", ("active_caches_size_in_bytes",))
        self.assertFalse(result["readComplete"])
        self.assertIn("error", result)

    def test_api_is_get_on_fixed_host_and_repository(self):
        completed = SimpleNamespace(returncode=0, stdout=json.dumps({"ok": True}), stderr="")
        with patch.object(subprocess, "run", return_value=completed) as run:
            self.assertEqual(audit.gh_get(audit.PREFIX), {"ok": True})
            command = run.call_args.args[0]
            self.assertEqual(command[:7], ["gh", "api", "--hostname", "github.com", "--method", "GET", "-H"])
            with self.assertRaises(audit.ReadError):
                audit.gh_get("repos/mwqwf/QuranRafiq")
            self.assertEqual(run.call_count, 1)

    def test_api_failure_omits_raw_stderr_and_stdout(self):
        completed = SimpleNamespace(returncode=1, stdout="private response", stderr="token-value (HTTP 403)")
        with patch.object(subprocess, "run", return_value=completed):
            with self.assertRaises(audit.ReadError) as caught:
                audit.gh_get(audit.PREFIX)
        self.assertIn("403", str(caught.exception))
        self.assertNotIn("token-value", str(caught.exception))
        self.assertNotIn("private response", str(caught.exception))

    def stored_report(self):
        return {"schema": 1, "repository": audit.REPO, "generatedAt": "2026-10-05T17:00:00Z",
                "repositoryMetadata": {"readComplete": True, "private": False, "visibility": "public"},
                "cacheUsage": {"readComplete": True, "active_caches_count": 2,
                               "active_caches_size_in_bytes": 2332228990},
                "artifacts": {"readComplete": False, "pagesRead": 50, "reportedTotal": 5001,
                    "errors": ["فشل آخر صفحة"], "observedActiveBytes": 500000,
                    "observedActiveCount": 5000, "observedExpiredCount": 0, "invalidCount": 0,
                    "activeArtifacts": [self.artifact(i, size=100) for i in range(5000)]},
                "costDecision": {"freeExecutionVerified": False, "accountArtifactQuotaKnown": False},
                "workflows": [{"path": ".github/workflows/heard_batch.yml",
                    "configuration": {"readComplete": True, "resources": [{"line": 1, "text": "runs-on: ubuntu-latest"}]},
                    "jobs": {"readComplete": True, "errors": [], "items": [
                        {"id": i, "runner_group_name": "GitHub Actions", "labels": ["ubuntu-latest"]}
                        for i in range(100)]}}]}

    def test_local_summary_keeps_counts_errors_resources_and_original_timestamp(self):
        report = self.stored_report()
        original = json.dumps(report)
        summary = audit.summarize_existing(report)
        self.assertEqual(summary["generatedAt"], report["generatedAt"])
        self.assertEqual(summary["cacheUsage"], report["cacheUsage"])
        self.assertEqual(summary["costDecision"], report["costDecision"])
        self.assertEqual(summary["artifacts"]["observedActiveBytes"], 500000)
        self.assertEqual(summary["artifacts"]["observedActiveCount"], 5000)
        self.assertFalse(summary["artifacts"]["readComplete"])
        self.assertEqual(summary["artifacts"]["errors"], ["فشل آخر صفحة"])
        self.assertNotIn("activeArtifacts", summary["artifacts"])
        self.assertEqual(summary["workflows"][0]["configuration"], report["workflows"][0]["configuration"])
        self.assertEqual(summary["workflows"][0]["jobs"]["runnerGroups"][0]["jobsObserved"], 100)
        self.assertNotIn("items", summary["workflows"][0]["jobs"])
        self.assertLess(len(json.dumps(summary)), 5000)
        self.assertEqual(json.dumps(report), original)

    def test_summarize_cli_never_calls_api_or_changes_full_report(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(audit, "ROOT", Path(temp)), \
                patch.dict(os.environ, {"GITHUB_REPOSITORY": audit.REPO}), \
                patch.object(audit, "audit", side_effect=AssertionError("ممنوع استدعاء API")), \
                patch.object(subprocess, "run", side_effect=AssertionError("ممنوع تشغيل gh")):
            source = Path(temp) / "ops/out/measured.json"
            source.parent.mkdir(parents=True)
            original = json.dumps(self.stored_report()).encode("utf-8")
            source.write_bytes(original)
            with redirect_stdout(io.StringIO()) as output:
                rc = audit.main(["--out", "ops/out/measured.json", "--summarize-existing"])
            self.assertEqual(rc, 1)  # فشل القراءة الأصلي يبقى معلناً في الملخص.
            self.assertEqual(source.read_bytes(), original)
            target = source.with_name("measured.summary.json")
            summary = json.loads(target.read_text())
            self.assertEqual(summary["sourceReport"], "ops/out/measured.json")
            self.assertIn('"observedActiveBytes": 500000', output.getvalue())
            self.assertNotIn("activeArtifacts", output.getvalue())

    def test_report_paths_reject_escape_subdirectory_and_symbolic_links(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(audit, "ROOT", Path(temp)):
            allowed = Path(temp) / "ops/out"
            allowed.mkdir(parents=True)
            outside = Path(temp) / "elsewhere.json"
            outside.write_text("{}")
            (allowed / "linked.json").symlink_to(outside)
            for path in ("elsewhere.json", "ops/out/../escape.json", "ops/out/sub/child.json",
                         "ops/out/not-json.txt", "ops/out/linked.json"):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    audit.report_path(path)

    def test_summary_output_link_is_rejected_and_hardlink_cannot_overwrite_source(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(audit, "ROOT", Path(temp)):
            source = Path(temp) / "ops/out/measured.json"
            source.parent.mkdir(parents=True)
            original = json.dumps(self.stored_report()).encode("utf-8")
            source.write_bytes(original)
            target = source.with_name("measured.summary.json")
            target.symlink_to(source)
            with self.assertRaises(ValueError):
                audit.save_existing_summary(source)
            self.assertEqual(source.read_bytes(), original)
            target.unlink()
            target.hardlink_to(source)
            audit.save_existing_summary(source)
            self.assertEqual(source.read_bytes(), original)
            self.assertNotIn("activeArtifacts", json.loads(target.read_text())["artifacts"])

    def test_foreign_repository_report_is_rejected(self):
        report = self.stored_report()
        report["repository"] = "mwqwf/QuranRafiq"
        with self.assertRaises(ValueError):
            audit.summarize_existing(report)


if __name__ == "__main__":
    unittest.main()
