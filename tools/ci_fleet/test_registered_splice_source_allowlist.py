import tempfile
import unittest
from pathlib import Path

from tools.ci_fleet.source_registry import assert_audio_sha, registered_splice_source

SHA = "a" * 64


def row(url, sha=SHA):
    return {"riwaya": "douri", "reciter": "husary_douri", "surah": 39, "url": url,
            "audio_sha256": sha, "evidence": "نفس الأداء كاملاً"}


def get(url, sha=SHA):
    return registered_splice_source("douri", "husary_douri", 39, [row(url, sha)])


class AllowlistTest(unittest.TestCase):
    def test_both_listed_hosts_accepted(self):
        for u in ["https://archive.org/download/item/039.mp3",
                  "https://download.quranicaudio.com/quran/x_doori/039.mp3"]:
            self.assertEqual(get(u)["url"], u)

    def test_unlisted_host_rejected(self):
        for u in ["https://example.test/download/039.mp3", "https://cdn.mp3quran.net/audio/x/039.mp3",
                  "https://evil.archive.org/download/039.mp3", "https://archive.org.evil.test/download/039.mp3",
                  "https://download.quranicaudio.com.evil.test/quran/039.mp3",
                  "https://quranicaudio.com/quran/039.mp3", "https://archive.org/details/item",
                  "https://download.quranicaudio.com/other/039.mp3",
                  "https://download.quranicaudio.com:8443/quran/039.mp3"]:
            with self.assertRaises(ValueError, msg=u): get(u)

    def test_http_link_rejected(self):
        for u in ["http://archive.org/download/item/039.mp3",
                  "http://download.quranicaudio.com/quran/x/039.mp3"]:
            with self.assertRaises(ValueError, msg=u): get(u)

    def test_missing_or_short_fingerprint_rejected(self):
        for sha in [None, "", "a" * 63, "A" * 64, "g" * 64]:
            with self.assertRaises(ValueError, msg=str(sha)):
                get("https://download.quranicaudio.com/quran/x/039.mp3", sha)

    def test_fingerprint_mismatch_rejected(self):
        import hashlib
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "a.mp3"; f.write_bytes(b"audio-bytes")
            ok = hashlib.sha256(b"audio-bytes").hexdigest()
            self.assertEqual(assert_audio_sha(f, ok), ok)
            with self.assertRaises(ValueError): assert_audio_sha(f, "b" * 64)

    def test_real_registry_entry_resolves(self):
        r = registered_splice_source("douri", "husary_douri", 39)
        self.assertTrue(r["url"].startswith("https://download.quranicaudio.com/quran/"))


if __name__ == "__main__":
    unittest.main()
