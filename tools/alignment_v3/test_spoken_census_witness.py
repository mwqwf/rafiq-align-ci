import copy
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import spoken_census_witness as S
import dual_ctc_model as D
import quran_ctc_model as Q


class SpokenWitnessTest(unittest.TestCase):
    def setUp(self):
        self.idx = {'audioSha256': ['a' * 64] * 114,
                    'engineBySurah': {'20': 'ctc-spoken-1'},
                    'entries': [{'ayahId': '20:1', 'startMs': 4000, 'endMs': 5500}]}
        self.proof = {'target': '20:1', 'sourceSha256': 'a' * 64,
                      'canonicalTextChanged': False, 'models': {}}
        for name, ident, revision, weights in [
                ('generic', D.GENERIC_ID, D.GENERIC_REVISION, D.GENERIC_WEIGHTS),
                ('quran', Q.MODEL_ID, Q.REVISION, Q.WEIGHTS_SHA256)]:
            self.proof['models'][name] = {
                'alignmentModel': {'id': ident, 'revision': revision,
                                   'weightsSha256': weights, 'license': 'Apache-2.0'},
                'alignmentInput': ['بسم الله الرحمن الرحيم', 'طا ها'],
                'entries': [{'ayahIdx': 0, 'startMs': 4000, 'endMs': 5500, 'conf': .8},
                            {'ayahIdx': 1, 'startMs': 5500, 'endMs': 11000, 'conf': .7},
                            {'ayahIdx': 2, 'startMs': 11000, 'endMs': 15000, 'conf': .6}]}

    def test_two_independent_pinned_measurements_match_target_and_anchor(self):
        self.assertIsNone(S.witness_error(self.proof, self.idx))

    def test_cannot_clear_arbitrary_unknown_rows_or_weak_disagreeing_evidence(self):
        mutations = [lambda p: p.update(target='20:2'),
                     lambda p: p.update(sourceSha256='b' * 64),
                     lambda p: p.update(canonicalTextChanged=True),
                     lambda p: p['models'].pop('quran'),
                     lambda p: p['models']['quran']['alignmentModel'].update(revision='main'),
                     lambda p: p['models']['quran']['alignmentModel'].update(weightsSha256='0' * 64),
                     lambda p: p['models']['quran']['alignmentModel'].update(license='CC-BY-NC'),
                     lambda p: p['models']['quran']['alignmentInput'].__setitem__(1, 'other text'),
                     lambda p: p['models']['quran']['entries'][0].update(conf=.69),
                     lambda p: p['models']['quran']['entries'][1].update(conf=.49),
                     lambda p: p['models']['quran']['entries'][2].update(conf=.44),
                     lambda p: p['models']['quran']['entries'][0].update(startMs=4400),
                     lambda p: p['models']['quran']['entries'][0].update(endMs=6100),
                     lambda p: p['models']['quran']['entries'][0].update(conf=float('nan'))]
        for change in mutations:
            proof = copy.deepcopy(self.proof)
            change(proof)
            self.assertIsNotNone(S.witness_error(proof, self.idx))
        broken = copy.deepcopy(self.idx)
        broken['engineBySurah']['20'] = 'unreviewed-engine'
        self.assertIsNotNone(S.witness_error(self.proof, broken))

    def test_census_cannot_claim_confirmation_without_original_row_or_ci_tool_provenance(self):
        row = {'aid': '20:1', 'kind': 'بريء', 'independentSpokenCtc': self.proof}
        self.assertIsNotNone(S.report_error({'sample': {'rows': [row]}}, self.idx))
        row['originalTinyRow'] = {'aid': '20:1', 'kind': 'غير حاسم'}
        self.assertIsNotNone(S.report_error({'sample': {'rows': [row]}}, self.idx))
        self.assertIsNone(S.report_error({'sample': {'rows': []}}, self.idx))


if __name__ == '__main__':
    unittest.main()
