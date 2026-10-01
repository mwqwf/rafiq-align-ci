import contextlib
import gzip
import io
import json
import unittest
from unittest.mock import patch

from tools.index_qa import promote_verified_transform as m


class VerifiedPromotionTest(unittest.TestCase):
    def setUp(self):
        self.key = "timings-staging/hafs/reader.aaaaaaaa.jz"
        self.target = "timings/hafs/reader.jz"
        self.old, self.new = "b" * 64, "a" * 64
        self.current, self.frozen = self.old, {self.target: self.old}
        self.idx = {"riwaya": "hafs", "reciterId": "reader", "entries": [{"ayahId": "1:1"}],
                    "transform": {"fromKey": self.target, "fromSha256": self.old}}
        self.cl = type("Client", (), {"get_object": lambda _cl, **_kw: {
            "Body": io.BytesIO(json.dumps({"indexes": [{"riwaya": "hafs", "reciterId": "reader",
                                                      "sha256": self.current}]}).encode())}})()
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(m.p, "s3", return_value=(self.cl, "bucket")))
        def obj(_cl, _bucket, key):
            sha = self.new if key == self.key else self.current
            return sha, 1, gzip.compress(json.dumps(self.idx).encode())
        self.stack.enter_context(patch.object(m.p, "object_sha", side_effect=obj))
        self.stack.enter_context(patch.object(m.p, "load_frozen", side_effect=lambda *_: (dict(self.frozen), "", None)))
        self.stack.enter_context(patch.object(m.p, "bucket_reports", return_value=[]))
        self.unfreeze = self.stack.enter_context(patch.object(m.p, "unfreeze", side_effect=lambda *_: self.frozen.pop(self.target)))
        def freeze(_cl, _bucket, key, sha, _reason):
            self.frozen[key] = sha
        self.freeze = self.stack.enter_context(patch.object(m.p, "freeze", side_effect=freeze))

    def invoke(self, key, yes=False):
        if not yes:
            print(f"✅ جاهز: {key} → {self.target}")
        else:
            self.current = self.new

    def adopt(self):
        with contextlib.redirect_stdout(io.StringIO()):
            m.adopt(self.key, self.new, self.old, "إصلاح مقيس")

    def test_rejection_preserves_original_freeze_without_writes(self):
        with patch.object(m, "invoke", return_value=None), self.assertRaisesRegex(ValueError, "ردت الحراس"):
            self.adopt()
        self.unfreeze.assert_not_called()
        self.freeze.assert_not_called()

    def test_exception_after_unfreeze_refreezes_actual_old_sha(self):
        def fail(key, yes=False):
            if yes:
                raise RuntimeError("network failed")
            self.invoke(key)
        with patch.object(m, "invoke", side_effect=fail), self.assertRaises(RuntimeError):
            self.adopt()
        self.assertEqual(self.frozen[self.target], self.old)

    def test_exception_after_copy_refreezes_actual_new_sha(self):
        def fail(key, yes=False):
            self.invoke(key, yes)
            if yes:
                raise RuntimeError("manifest failed")
        with patch.object(m, "invoke", side_effect=fail), self.assertRaises(RuntimeError):
            self.adopt()
        self.assertEqual(self.frozen[self.target], self.new)

    def test_success_verifies_manifest_and_restores_module_state(self):
        saved = (m.p.STATE_PREFIXES, m.p.REPORTS_CACHE, m.p.load_frozen)
        with patch.object(m, "invoke", side_effect=self.invoke):
            self.adopt()
        self.assertEqual(self.frozen[self.target], self.new)
        self.assertEqual(saved, (m.p.STATE_PREFIXES, m.p.REPORTS_CACHE, m.p.load_frozen))

    def test_changed_parent_refuses_before_unfreeze(self):
        self.current = "c" * 64
        with self.assertRaisesRegex(ValueError, "تغير المنشور"):
            self.adopt()
        self.unfreeze.assert_not_called()

    def test_failed_windows_refuse_before_preview_and_unfreeze(self):
        reports = [("state/reader.audio-rs1.json", {"sha256": self.new, "sample": {"errors": 30}})]
        with patch.object(m.p, "bucket_reports", return_value=reports), patch.object(m, "invoke") as invoke:
            with self.assertRaisesRegex(ValueError, "نوافذ تعذرت"):
                self.adopt()
        invoke.assert_not_called()
        self.unfreeze.assert_not_called()
        self.freeze.assert_not_called()

    def test_short_sha_and_bad_lineage_refuse_before_unfreeze(self):
        with self.assertRaises(ValueError):
            m.adopt(self.key, self.new[:8], self.old, "إصلاح")
        self.idx["transform"]["fromSha256"] = "c" * 64
        with self.assertRaisesRegex(ValueError, "سلسلة نسب"):
            self.adopt()
        self.unfreeze.assert_not_called()


if __name__ == "__main__":
    unittest.main()
