import copy
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools.index_qa import heard_gate as H
from tools.index_qa import local_candidate as L


class LocalCandidateHeardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.parent = {
            "riwaya": "qalun", "reciterId": "reader",
            "entries": [{"ayahId": "38:1", "startMs": 1000, "endMs": 2000,
                         "fileRef": "https://audio.example/038.mp3"}],
            "audioSha256": [f"{s:064x}" for s in range(1, 115)],
        }
        self.parent_blob = gzip.compress(json.dumps(self.parent).encode())
        self.parent_sha = hashlib.sha256(self.parent_blob).hexdigest()
        self.parent_path = self.root / "parent.jz"
        self.parent_path.write_bytes(self.parent_blob)
        self.candidate = copy.deepcopy(self.parent)
        self.candidate["entries"][0]["startMs"] = 1100
        self.candidate["transform"] = {
            "fromKey": "timings/qalun/reader.jz", "fromSha256": self.parent_sha,
        }
        self.candidate_sha = "a" * 64

    def tearDown(self):
        self.tmp.cleanup()

    def test_parent_binding_rejects_changed_bytes_identity_and_key(self):
        got, sha = L.load_local_parent(self.parent_path, self.candidate)
        self.assertEqual(got, self.parent)
        self.assertEqual(sha, self.parent_sha)
        self.candidate["transform"]["fromSha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "بصمة الأصل"):
            L.load_local_parent(self.parent_path, self.candidate)
        self.candidate["transform"]["fromSha256"] = self.parent_sha
        self.candidate["transform"]["fromKey"] = "timings/qalun/other.jz"
        with self.assertRaisesRegex(ValueError, "مفتاح الأصل"):
            L.load_local_parent(self.parent_path, self.candidate)

    def test_heard_report_recomputes_real_gate_without_official_write(self):
        def collector(idx, parent, sha, directory):
            self.assertEqual(parent, self.parent)
            self.assertEqual(sha, self.candidate_sha)
            cmap = {"surah": 38, "sha256": idx["audioSha256"][37],
                    "fileRef": idx["entries"][0]["fileRef"],
                    "anchors": {"1": [[1100, 1900], .9, []]}}
            return {38: cmap}, {}

        report = L.local_heard_report(
            self.candidate, self.candidate_sha, self.parent_path,
            collector=collector,
            provenance={"run_id": "123", "commit": "b" * 40},
        )
        self.assertTrue(report["measurementComplete"])
        self.assertTrue(report["ok"])
        self.assertIsNone(H.gate_error(self.candidate, self.parent, self.candidate_sha, report))
        self.assertFalse(report["officialStateWritten"])
        self.assertTrue(report["unpublishedLocalCandidate"])

    def test_heard_report_preserves_incomplete_measurement_as_failure(self):
        report = L.local_heard_report(
            self.candidate, self.candidate_sha, self.parent_path,
            collector=lambda *_: ({}, {"38": "download failed"}),
            provenance={"run_id": "123", "commit": "b" * 40},
        )
        self.assertFalse(report["measurementComplete"])
        self.assertFalse(report["ok"])
        self.assertIn("38", report["measurementErrors"])
        self.assertFalse(report["officialStateWritten"])


if __name__ == "__main__":
    unittest.main()
