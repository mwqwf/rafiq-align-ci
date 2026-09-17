import unittest

from tools.index_qa.promote import registered_source_remediation


class RegisteredSourceRemediationTest(unittest.TestCase):
    def setUp(self):
        self.base = "https://audio.example.test/hafs/"
        self.override = [{
            "riwaya": "hafs",
            "reciter": "reader",
            "surah": 9,
            "base": self.base,
            "evidence": "measured source ratio 1.04; same reciter and riwaya",
        }]
        self.entries = [
            {"ayahId": f"9:{ayah}", "fileRef": self.base + "009.mp3"}
            for ayah in range(1, 130)
        ]

    def check(self, entries=None, overrides=None, **scope):
        return registered_source_remediation(
            {"entries": self.entries if entries is None else entries},
            scope.get("riwaya", "hafs"),
            scope.get("reciter", "reader"),
            scope.get("surah", 9),
            self.override if overrides is None else overrides,
        )

    def test_exact_registered_full_surah_passes(self):
        ok, detail = self.check()
        self.assertTrue(ok, detail)
        self.assertIn("9:129", detail)

    def test_incomplete_surah_is_rejected(self):
        ok, detail = self.check(entries=self.entries[:-1])
        self.assertFalse(ok)
        self.assertIn("128/129", detail)

    def test_wrong_file_reference_is_rejected(self):
        entries = [dict(row) for row in self.entries]
        entries[40]["fileRef"] = "https://wrong.example/009.mp3"
        ok, detail = self.check(entries=entries)
        self.assertFalse(ok)
        self.assertIn("1 مدخلاً", detail)

    def test_wrong_reciter_or_surah_is_rejected(self):
        self.assertFalse(self.check(reciter="other")[0])
        self.assertFalse(self.check(surah=10)[0])

    def test_duplicate_override_is_rejected(self):
        ok, detail = self.check(overrides=self.override + self.override)
        self.assertFalse(ok)
        self.assertIn("(2)", detail)

    def test_override_requires_https_and_evidence(self):
        no_evidence = [dict(self.override[0], evidence="")]
        self.assertFalse(self.check(overrides=no_evidence)[0])
        http_only = [dict(self.override[0], base="http://audio.example.test/hafs/")]
        self.assertFalse(self.check(overrides=http_only)[0])


if __name__ == "__main__":
    unittest.main()
