"""اختباراتُ حارس البادئة والتجربة الجافّة لأداة r2_tmp_purge (بلا شبكة)."""
import importlib.util
import pathlib
import unittest

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("r2_tmp_purge", HERE / "r2_tmp_purge.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class FakeS3:
    def __init__(self, keys):
        self.keys = dict(keys)
        self.deleted = []

    def list_objects_v2(self, Bucket, Prefix, MaxKeys, ContinuationToken=None):
        return {"Contents": [{"Key": k, "Size": v} for k, v in self.keys.items() if k.startswith(Prefix)], "IsTruncated": False}

    def delete_objects(self, Bucket, Delete):
        ks = [o["Key"] for o in Delete["Objects"]]
        for k in ks:
            self.keys.pop(k, None)
        self.deleted.extend(ks)
        return {"Deleted": [{"Key": k} for k in ks], "Errors": []}


class PrefixGuard(unittest.TestCase):
    def test_allowed(self):
        self.assertIsNone(mod.check_prefix("tmp/ui_walk/"))
        self.assertIsNone(mod.check_prefix("tmp/ui_walk/apk/"))

    def test_refused(self):
        for p in ("", "tmp/", "timings/", "tmp/ui_walk", "/tmp/ui_walk/", "tmp/ui_walk/../timings/", "tmp\\ui_walk\\", "catalog/"):
            self.assertIsNotNone(mod.check_prefix(p), p)


class DryRunAndPurge(unittest.TestCase):
    KEYS = {"tmp/ui_walk/apk/app-debug.apk": 10, "tmp/ui_walk/1/build.log": 5, "timings/hafs/x.jz": 7}

    def test_dry_run_deletes_nothing(self):
        s3 = FakeS3(self.KEYS)
        rc = mod.main(["--prefix", "tmp/ui_walk/"], s3_factory=lambda: (s3, "b"))
        self.assertEqual(rc, 0)
        self.assertEqual(s3.deleted, [])

    def test_yes_deletes_only_prefix(self):
        s3 = FakeS3(self.KEYS)
        rc = mod.main(["--prefix", "tmp/ui_walk/", "--yes"], s3_factory=lambda: (s3, "b"))
        self.assertEqual(rc, 0)
        self.assertEqual(sorted(s3.deleted), ["tmp/ui_walk/1/build.log", "tmp/ui_walk/apk/app-debug.apk"])
        self.assertIn("timings/hafs/x.jz", s3.keys)

    def test_bad_prefix_never_touches_s3(self):
        def boom():
            raise AssertionError("لا يجوز الاتّصال بالدلو ببادئةٍ مرفوضة")
        self.assertEqual(mod.main(["--prefix", "timings/", "--yes"], s3_factory=boom), 2)


if __name__ == "__main__":
    unittest.main()
