import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from openers_scan import opener_audio_url


class OpenerAudioSourceTest(unittest.TestCase):
    def test_audio_content_mapping_takes_precedence_over_surah_number(self):
        url = "https://server16.mp3quran.net/m_akri/Rewayat-Qalon-A-n-Nafi/106.mp3"
        self.assertEqual(opener_audio_url({"fileRef": url}, 107,
                         "https://example.test/{surah:03d}.mp3"), url)

    def test_legacy_filename_and_catalog_table_still_work(self):
        self.assertEqual(opener_audio_url({}, 107, "https://example.test/{surah:03d}.mp3"),
                         "https://example.test/107.mp3")
        self.assertEqual(opener_audio_url({}, 107, names={107: "a b.mp3"}, base="https://example.test/"),
                         "https://example.test/a%20b.mp3")

    def test_missing_or_malformed_source_fails(self):
        with self.assertRaises(ValueError): opener_audio_url({}, 107)
        with self.assertRaises(ValueError):
            opener_audio_url({"fileRef": "https://user:secret@example.test/a.mp3"}, 107)
