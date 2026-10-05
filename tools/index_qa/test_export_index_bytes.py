"""نسخة الأصل الخام تبقى حرفية؛ الفشل لا ينشر ملفًا ولا يكتب إلى الدلو."""
import base64
import gzip
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.index_qa import export_index_bytes as E


class ReadOnlyClient:
    def __init__(self, raw):
        self.raw = raw
        self.calls = []

    def get_object(self, **kwargs):
        self.calls.append(kwargs)
        return {"Body": io.BytesIO(self.raw)}


class ExportIndexBytesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.root_patch = patch.object(E, "ROOT", self.root)
        self.root_patch.start()
        self.out = self.root / "ops/out/parent.json"
        self.index = {"riwaya": "hafs", "reciterId": "peshawa",
                      "arbitraryHeader": {"future": "محفوظ"},
                      "entries": [{"ayahId": "63:1", "conf": 0.887,
                                   "futureField": [1, 2, 3]}]}
        self.raw = gzip.compress(json.dumps(self.index).encode(), mtime=12345)
        self.sha = hashlib.sha256(self.raw).hexdigest()

    def tearDown(self):
        self.root_patch.stop()
        self.tmp.cleanup()

    def run_export(self, raw=None, **kwargs):
        client = ReadOnlyClient(self.raw if raw is None else raw)
        summary = E.export(client, "private-bucket-name", kwargs.get("key", "timings/hafs/peshawa.jz"),
                           kwargs.get("sha", self.sha), kwargs.get("out", self.out))
        return client, summary

    def test_exact_compressed_bytes_and_unknown_fields_survive(self):
        client, summary = self.run_export()
        report = json.loads(self.out.read_text())
        restored = base64.b64decode(report["gzipBase64"], validate=True)
        self.assertEqual(restored, self.raw)
        self.assertEqual(json.loads(gzip.decompress(restored)), self.index)
        self.assertEqual(report["sha256"], hashlib.sha256(restored).hexdigest())
        self.assertEqual(client.calls, [{"Bucket": "private-bucket-name", "Key": "timings/hafs/peshawa.jz"}])
        self.assertNotIn("private-bucket-name", self.out.read_text())
        self.assertNotIn("gzipBase64", summary)
        self.assertFalse(summary["bucketWritten"])
        self.assertFalse(summary["qualityClaim"])

    def test_changed_parent_never_creates_export(self):
        with self.assertRaisesRegex(ValueError, "بصمة"):
            self.run_export(sha="0" * 64)
        self.assertFalse(self.out.exists())

    def test_invalid_key_path_or_sha_fails_before_get(self):
        for kwargs in ({"key": "timings-staging/hafs/peshawa.abcd.jz"},
                       {"key": "timings/hafs/../secret.jz"}, {"sha": "a"},
                       {"out": self.root / "other.json"}):
            client = ReadOnlyClient(self.raw)
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                E.export(client, "bucket", kwargs.get("key", "timings/hafs/peshawa.jz"),
                         kwargs.get("sha", self.sha), kwargs.get("out", self.out))
            self.assertEqual(client.calls, [])

    def test_symlink_and_existing_file_are_rejected(self):
        self.out.parent.mkdir(parents=True)
        outside = self.root / "outside.json"
        outside.write_text("preserved")
        self.out.symlink_to(outside)
        with self.assertRaises(ValueError):
            self.run_export()
        self.assertEqual(outside.read_text(), "preserved")
        self.out.unlink()
        self.out.write_text("existing")
        with self.assertRaises(ValueError):
            self.run_export()
        self.assertEqual(self.out.read_text(), "existing")

    def test_size_limits_reject_without_truncated_file(self):
        with patch.object(E, "MAX_BYTES", 10), self.assertRaisesRegex(ValueError, "سقف"):
            self.run_export()
        with patch.object(E, "MAX_UNCOMPRESSED", 10), self.assertRaisesRegex(ValueError, "سقف"):
            self.run_export()
        self.assertFalse(self.out.exists())

    def test_wrong_identity_is_rejected_even_with_matching_sha(self):
        raw = gzip.compress(json.dumps(dict(self.index, reciterId="other")).encode())
        with self.assertRaisesRegex(ValueError, "هوية"):
            self.run_export(raw, sha=hashlib.sha256(raw).hexdigest())
        self.assertFalse(self.out.exists())


if __name__ == "__main__":
    unittest.main()
