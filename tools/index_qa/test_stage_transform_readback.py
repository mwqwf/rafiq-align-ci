"""مطابقة بايتات الرفع قبل إعلان نجاحه، بلا شبكة أو كتابة إلى دلو."""
import hashlib
import io
import unittest

from tools.index_qa.stage_transform import verified_stage_readback


class Reader:
    def __init__(self, data, length=None, error=None):
        self.data = data
        self.length = len(data) if length is None else length
        self.error = error
        self.reads = []

    def head_object(self, **kwargs):
        self.reads.append(("head", kwargs))
        return {"ContentLength": self.length}

    def get_object(self, **kwargs):
        self.reads.append(("get", kwargs))
        if self.error:
            raise self.error
        return {"Body": io.BytesIO(self.data)}


class StageReadbackTests(unittest.TestCase):
    def test_same_length_different_bytes_cannot_be_reported_as_success(self):
        with self.assertRaisesRegex(SystemExit, "غير مطابقة"):
            verified_stage_readback(Reader(b"changed!"), "bucket", "timings-staging/hafs/x.jz", b"original")

    def test_exact_bytes_produce_full_sha_and_only_read_the_requested_key(self):
        body = b"exact candidate bytes"
        reader = Reader(body)
        key = "timings-staging/hafs/peshawa.12345678.jz"
        result = verified_stage_readback(reader, "bucket", key, body)
        self.assertEqual(result, {"key": key, "sha256": hashlib.sha256(body).hexdigest(),
                                  "sizeBytes": len(body), "readBackVerified": True})
        self.assertEqual(len(result["sha256"]), 64)
        self.assertEqual(reader.reads, [(op, {"Bucket": "bucket", "Key": key}) for op in ("head", "get")])

    def test_inconsistent_head_fails_even_if_body_matches(self):
        with self.assertRaisesRegex(SystemExit, "حجم الترويسة"):
            verified_stage_readback(Reader(b"body", length=99), "bucket", "key", b"body")

    def test_read_failure_propagates_without_success_report(self):
        with self.assertRaisesRegex(OSError, "تعذرت القراءة"):
            verified_stage_readback(Reader(b"body", error=OSError("تعذرت القراءة")), "bucket", "key", b"body")


if __name__ == "__main__":
    unittest.main()
