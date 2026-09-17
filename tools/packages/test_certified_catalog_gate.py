#!/usr/bin/env python3
from __future__ import annotations
import unittest
from tools.packages.certified_catalog_gate import certified_only
from tools.packages.certified_catalog_gate import id_diff

SHA = "a" * 64


def pkg(name="ok", certified=True, coverage=0.99, sha=SHA, sha8="aaaaaaaa"):
    return {"id": "timings.hafs." + name, "kind": "timing_index",
            "files": [{"key": "timings/hafs/" + name + ".jz", "sha256": sha}],
            "quality": {"ayahCertified": certified, "ayahCoverage": coverage,
                        "sha8": sha8}}


def snapshot(*names, coverage=0.99, sha=SHA, rejected=False):
    return {"schema": 1, "certifier": "certify_catalog-1.1",
            "catalogSha256": "c" * 64, "indexes": {
        "hafs/" + name: {"sha256": sha, "coverage": coverage,
                          "rejected": rejected} for name in names
    }}


class GateTest(unittest.TestCase):
    def test_keeps_only_certified_timing_and_preserves_extras(self):
        doc = {"packages": [pkg(), pkg("no", False),
                            {"id": "model.x", "kind": "model", "files": []}],
               "failures": [], "rejected": []}
        out, stat = certified_only(doc, 1, snapshot("ok"))
        self.assertEqual([p["id"] for p in out["packages"]],
                         ["timings.hafs.ok", "model.x"])
        self.assertEqual(stat["timingCertified"], 1)
        self.assertEqual(stat["timingDroppedUncertified"], 1)
        self.assertEqual(out["rejected"][-1]["reason"],
                         "NOT_IN_CERTIFICATE_SNAPSHOT")

    def test_transient_build_failure_blocks_whole_catalog(self):
        with self.assertRaisesRegex(ValueError, "فشلاً"):
            certified_only({"packages": [pkg()], "failures": [{"key": "x"}]},
                           certificate_snapshot=snapshot("ok"))

    def test_certified_sha_mismatch_is_tool_failure_not_quality_rejection(self):
        with self.assertRaisesRegex(ValueError, "sha8"):
            certified_only({"packages": [pkg(sha8="bbbbbbbb")], "failures": []},
                           certificate_snapshot=snapshot("ok"))

    def test_conservative_floor_blocks_regression(self):
        with self.assertRaisesRegex(ValueError, "الحد المحافظ"):
            certified_only({"packages": [pkg()], "failures": []}, 2, snapshot("ok"))

    def test_coverage_rejects_bool_nan_inf_and_out_of_range(self):
        for value in (True, False, float("nan"), float("inf"),
                      float("-inf"), 0.9799, 1.0001):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "تغطية"):
                certified_only({"packages": [pkg(coverage=value)], "failures": []},
                               certificate_snapshot=snapshot("ok", coverage=value))

    def test_full_sha_certificate_is_required(self):
        with self.assertRaisesRegex(ValueError, "SHA-256 الكاملة"):
            certified_only({"packages": [pkg()], "failures": []},
                           certificate_snapshot=snapshot("ok", sha="b" * 64))

    def test_snapshot_must_name_certifier_and_catalog_full_sha(self):
        bad = snapshot("ok")
        bad["catalogSha256"] = "c" * 8
        with self.assertRaisesRegex(ValueError, "بصمة كتالوج"):
            certified_only({"packages": [pkg()], "failures": []},
                           certificate_snapshot=bad)

    def test_rejected_certificate_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "rejected=false"):
            certified_only({"packages": [pkg()], "failures": []},
                           certificate_snapshot=snapshot("ok", rejected=True))

    def test_snapshot_member_missing_from_candidate_blocks_whole_catalog(self):
        with self.assertRaisesRegex(ValueError, "أسقط"):
            certified_only({"packages": [pkg()], "failures": []},
                           certificate_snapshot=snapshot("ok", "missing"))

    def test_id_diff_lists_ids_and_blocks_removal(self):
        before = {"packages": [pkg("old"), pkg("uncert", False)]}
        after = {"packages": [pkg("old"), pkg("new")]}
        report = id_diff(before, after)
        self.assertEqual(report["beforeCertified"], ["hafs/old"])
        self.assertEqual(report["afterCertified"], ["hafs/new", "hafs/old"])
        self.assertEqual(report["added"], ["hafs/new"])
        self.assertEqual(report["removed"], [])
        with self.assertRaisesRegex(ValueError, "أسقط قارئاً"):
            id_diff(before, {"packages": [pkg("new")]})


if __name__ == "__main__":
    unittest.main()
