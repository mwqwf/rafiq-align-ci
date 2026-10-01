import unittest

from tools.ci_fleet.source_registry import registered_source


class SourceRegistryTest(unittest.TestCase):
    def setUp(self):
        self.row = {"riwaya": "qalun", "reciter": "akri_qalun", "surah": 107,
                    "base": "https://example.test/", "url": "https://example.test/106.mp3",
                    "audio_sha256": "a" * 64, "evidence": "محتوى الماعون في الملف 106"}

    def resolve(self, rows=None, **scope):
        return registered_source(scope.get("riwaya", "qalun"),
                                 scope.get("reciter", "akri_qalun"),
                                 scope.get("surah", 107), [self.row] if rows is None else rows)

    def test_content_mapping_is_not_replaced_by_numbered_filename(self):
        self.assertEqual(self.resolve()["url"], "https://example.test/106.mp3")

    def test_numbered_legacy_source_still_resolves(self):
        row = dict(self.row); row.pop("url"); row.pop("audio_sha256")
        self.assertEqual(self.resolve([row])["url"], "https://example.test/107.mp3")

    def test_wrong_scope_and_ambiguous_registry_are_rejected(self):
        for scope in [{"riwaya": "hafs"}, {"reciter": "other"}, {"surah": 108}]:
            with self.assertRaises(ValueError): self.resolve(**scope)
        with self.assertRaises(ValueError): self.resolve([self.row, self.row])

    def test_explicit_source_without_measured_hash_or_evidence_is_rejected(self):
        for field in ["audio_sha256", "evidence"]:
            row = dict(self.row); row.pop(field)
            with self.assertRaises(ValueError): self.resolve([row])

    def test_non_https_and_template_urls_are_rejected(self):
        for url in ["http://example.test/106.mp3", "https://example.test/{s:03d}.mp3",
                    "https://user:password@example.test/106.mp3", "https://example.test/106.mp3#x"]:
            with self.assertRaises(ValueError): self.resolve([dict(self.row, url=url)])
