"""منع تغيير الأصول أو تهجئة كلمات خارج مواضع الحروف المقطعة."""
import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import QURAN_ASSETS, load_index, load_text, norm
from spoken_letters import alignment_text


class SpokenLettersTest(unittest.TestCase):
    def test_all_riwayat_keep_canonical_assets_and_non_openers_untouched(self):
        index = load_index()
        for riwaya in ("hafs", "qalun", "warsh", "douri"):
            path = Path(QURAN_ASSETS) / f"text_{riwaya}.jz"
            before = hashlib.sha256(path.read_bytes()).hexdigest()
            texts = load_text(riwaya)
            for surah in index["surahs"]:
                start = surah["start"]
                for i in range(surah["ayahs"]):
                    original = texts[start + i]
                    result = alignment_text(surah["n"], i + 1, original)
                    if i > 0 and (surah["n"], i + 1) != (42, 2):
                        self.assertEqual(result, norm(original))
                    self.assertEqual(texts[start + i], original)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)

    def test_position_and_canonical_content_both_required(self):
        self.assertEqual(alignment_text(3, 1, "الٓمٓ"), "الف لام ميم")
        self.assertEqual(alignment_text(20, 1, "طٰهٰ"), "طا ها")
        self.assertEqual(alignment_text(38, 1, "صٓ وَٱلْقُرْءَانِ ذِي ٱلذِّكْرِ"),
                         "صاد والقران ذي الذكر")
        self.assertEqual(alignment_text(42, 2, "عٓسٓقٓ"), "عين سين قاف")
        self.assertEqual(alignment_text(3, 2, "الم"), "الم")
        with self.assertRaises(ValueError):
            alignment_text(3, 1, "طه")


if __name__ == "__main__":
    unittest.main()
