#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.packages.approved_candidate import verify_approved


def _write(root: Path, name: str, doc: dict) -> Path:
    path = root / name
    path.write_text(json.dumps(doc, sort_keys=True), encoding="utf-8")
    return path


class ApprovedCandidateTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.approved = _write(self.root, "approved.json", {
            "generatedAt": 100, "packages": [
                {"id": "timings.hafs.a", "kind": "timing_index",
                 "files": [{"sha256": "a" * 64}]},
                {"id": "model.x", "kind": "model"},
            ], "failures": [], "certifiedGate": {"timingCertified": 1},
        })
        self.fresh = _write(self.root, "fresh.json", {
            "generatedAt": 200, "packages": [
                {"id": "timings.hafs.a", "kind": "timing_index",
                 "files": [{"sha256": "a" * 64}]},
                {"id": "model.x", "kind": "model"},
            ], "failures": [], "certifiedGate": {"timingCertified": 1},
        })
        self.before = _write(self.root, "before.json", {"packages": []})
        self.snapshot = _write(self.root, "snapshot.json", {
            "catalogSha256": "c" * 64, "indexes": {"hafs/a": {}}
        })

    def tearDown(self):
        self.temp.cleanup()

    def _verify(self):
        return verify_approved(
            self.approved, self.fresh, self.before, self.snapshot,
            hashlib.sha256(self.approved.read_bytes()).hexdigest(),
            hashlib.sha256(self.before.read_bytes()).hexdigest(), "c" * 64)

    def test_only_generated_at_may_differ(self):
        result = self._verify()
        self.assertEqual(result["timingPackages"], 1)
        self.assertEqual(result["semanticMatchIgnoring"], ["generatedAt"])

    def test_package_or_file_change_is_blocked(self):
        doc = json.loads(self.fresh.read_text())
        doc["packages"][0]["files"][0]["sha256"] = "b" * 64
        self.fresh.write_text(json.dumps(doc, sort_keys=True))
        with self.assertRaisesRegex(ValueError, "beyond generatedAt"):
            self._verify()

    def test_wrong_candidate_before_or_certificate_sha_is_blocked(self):
        good_candidate = hashlib.sha256(self.approved.read_bytes()).hexdigest()
        good_before = hashlib.sha256(self.before.read_bytes()).hexdigest()
        cases = [
            ("0" * 64, good_before, "c" * 64, "candidate"),
            (good_candidate, "0" * 64, "c" * 64, "package catalog"),
            (good_candidate, good_before, "d" * 64, "reciters catalog"),
        ]
        for candidate, before, reciters, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                verify_approved(self.approved, self.fresh, self.before, self.snapshot,
                                candidate, before, reciters)

    def test_bool_or_missing_generated_at_is_blocked(self):
        for value in (True, None, 0, -1):
            doc = json.loads(self.fresh.read_text())
            if value is None:
                doc.pop("generatedAt", None)
            else:
                doc["generatedAt"] = value
            self.fresh.write_text(json.dumps(doc, sort_keys=True))
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "generatedAt"):
                self._verify()
            self.fresh = _write(self.root, "fresh.json", {
                "generatedAt": 200, "packages": [
                    {"id": "timings.hafs.a", "kind": "timing_index",
                     "files": [{"sha256": "a" * 64}]},
                    {"id": "model.x", "kind": "model"},
                ], "failures": [], "certifiedGate": {"timingCertified": 1},
            })


if __name__ == "__main__":
    unittest.main()
