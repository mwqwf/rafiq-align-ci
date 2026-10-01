import pathlib
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import quran_ctc_model as Q


class QuranCtcModelTest(unittest.TestCase):
    def test_input_keeps_letters_and_known_vowels_without_mutating_original(self):
        raw='فَٱدْخُلِي فِي عِبَٰدِي ۩'
        with patch.object(Q,'_VOCAB', {ch:i for i,ch in enumerate('فَٱدْخُلِي عِبٰ ۥۦ')}):
            result=Q.reference_text(raw)
        self.assertEqual(result,'فَٱدْخُلِي فِي عِبَٰدِي ')
        self.assertTrue(raw.endswith('۩'))

    def test_unsupported_letter_cannot_be_silently_dropped(self):
        with patch.object(Q,'_VOCAB',{'ا':0,'ل':1,' ':2}):
            with self.assertRaises(ValueError): Q.reference_text('الله')

    def test_model_requires_correct_revision_weights_license_and_unmodified_canonical_text(self):
        ev={'id':Q.MODEL_ID,'revision':Q.REVISION,'weightsSha256':Q.WEIGHTS_SHA256,
            'license':'Apache-2.0','canonicalTextChanged':False}
        idx={'engineBySurah':{'55':'ctc-quran-surah-1'},'alignmentModelBySurah':{'55':ev}}
        self.assertIsNone(Q.records_error(idx))
        for field,bad in [('revision','moving-main'),('weightsSha256','0'*64),('license','CC-BY-NC'),('canonicalTextChanged',True)]:
            with self.subTest(field=field):
                broken=dict(idx,alignmentModelBySurah={'55':dict(ev,**{field:bad})})
                self.assertIsNotNone(Q.records_error(broken))
        self.assertIsNotNone(Q.records_error({'engineBySurah':{'55':Q.ENGINE}}))

    def test_other_engines_keep_their_existing_contract(self):
        self.assertIsNone(Q.records_error({'engineBySurah':{'55':'ctc-gapsplit-1'}}))

    def test_loaded_specialized_model_cannot_be_claimed_as_default_engine(self):
        import ctc_seg as C
        with patch.object(C,'_M',{'alignmentModelId':Q.MODEL_ID}):
            with self.assertRaises(ValueError):
                C.run_surah('not-used.mp3',55,'hafs')


if __name__=='__main__': unittest.main()
