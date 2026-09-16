#!/usr/bin/env python3
from __future__ import annotations
import unittest
from tools.packages.certified_catalog_gate import certified_only

SHA = "a" * 64


def pkg(name="ok", certified=True, coverage=0.99, sha=SHA, sha8="aaaaaaaa"):
    return {"id": "timings.hafs." + name, "kind": "timing_index",
            "files": [{"key": "timings/hafs/" + name + ".jz", "sha256": sha}],
            "quality": {"ayahCertified": certified, "ayahCoverage": coverage,
                        "sha8": sha8}}


class GateTest(unittest.TestCase):
    def test_keeps_only_certified_timing_and_preserves_extras(self):
        doc = {"packages": [pkg(), pkg("no", False),
                            {"id": "model.x", "kind": "model", "files": []}],
               "failures": [], "rejected": []}
        out, stat = certified_only(doc, 1)
        self.assertEqual([p["id"] for p in out["packages"]],
                         ["timings.hafs.ok", "model.x"])
        self.assertEqual(stat["timingCertified"], 1)
        self.assertEqual(stat["timingDroppedUncertified"], 1)
        self.assertEqual(out["rejected"][-1]["reason"], "NOT_CERTIFIED")

    def test_transient_build_failure_blocks_whole_catalog(self):
        with self.assertRaisesRegex(ValueError, "فشلاً"):
            certified_only({"packages": [pkg()], "failures": [{"key": "x"}]})

    def test_certified_sha_mismatch_is_tool_failure_not_quality_rejection(self):
        with self.assertRaisesRegex(ValueError, "sha8"):
            certified_only({"packages": [pkg(sha8="bbbbbbbb")], "failures": []})

    def test_conservative_floor_blocks_regression(self):
        with self.assertRaisesRegex(ValueError, "الحد المحافظ"):
            certified_only({"packages": [pkg()], "failures": []}, 2)


if __name__ == "__main__":
    unittest.main()
