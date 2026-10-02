import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from alignment_input_variants import alignment_variant
from common import norm


class InputSpellingTests(unittest.TestCase):
    def test_canonical_input_is_exact_and_never_mutated(self):
        raw = 'وَمَن يَرْغَبُ عَن مِّلَّةِ إِبْرَٰهِۦمَ'
        self.assertEqual(alignment_variant(raw), raw)
        self.assertEqual(alignment_variant(raw, 'common.norm'), norm(raw))
        self.assertEqual(raw, 'وَمَن يَرْغَبُ عَن مِّلَّةِ إِبْرَٰهِۦمَ')

    def test_pronounced_small_letters_and_maqsura(self):
        self.assertEqual(alignment_variant('إِبْرَٰهِۦمَ لَهُۥ مُوسَىٰ', 'spoken-small-letters'),
                         'إِبْرَاهِيمَ لَهُو مُوسَى')
        self.assertEqual(alignment_variant('إِبْرَٰهِۦمَ', 'spoken-small-letters+common.norm'), 'ابراهيم')

    def test_meaningful_long_vowel_is_preserved(self):
        self.assertNotEqual(alignment_variant('مَٰلِكِ', 'spoken-small-letters'),
                            alignment_variant('مَلِكِ', 'spoken-small-letters'))

    def test_arbitrary_rewrite_cannot_be_requested(self):
        with self.assertRaises(ValueError): alignment_variant('نص', 'remove-word')


if __name__ == '__main__': unittest.main()
