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
        self.idx = {'riwaya': 'hafs', 'audioSha256': ['a' * 64] * 114,
                    'engineBySurah': {'20': 'ctc-spoken-1'},
                    'entries': [{'ayahId': '20:1', 'startMs': 4000, 'endMs': 5500}, {'ayahId': '20:3', 'endMs': 15000}]}
        self.proof = {'target': '20:1', 'sourceSha256': 'a' * 64,
                      'canonicalTextChanged': False, 'models': {}, 'range': [1, 3], 'windowMs': [0, 15000], 'context': 'full-prefix', 'runtime': {'precision': 'float32', 'threads': 2}}
        for name, ident, revision, weights in [
                ('generic', D.GENERIC_ID, D.GENERIC_REVISION, D.GENERIC_WEIGHTS),
                ('quran', Q.MODEL_ID, Q.REVISION, Q.WEIGHTS_SHA256)]:
            self.proof['models'][name] = {
                'alignmentModel': {'id': ident, 'revision': revision,
                                   'weightsSha256': weights, 'license': 'Apache-2.0'},
                'alignmentInput': ['بسم الله الرحمن الرحيم', 'طا ها', 'ما انزلنا عليك القران لتشقي', 'الا تذكره لمن يخشي'],
                'entries': [{'ayahIdx': 0, 'startMs': 4000, 'endMs': 5500, 'conf': .8},
                            {'ayahIdx': 1, 'startMs': 5500, 'endMs': 11000, 'conf': .7},
                            {'ayahIdx': 2, 'startMs': 11000, 'endMs': 15000, 'conf': .6}]}

    def test_two_independent_pinned_measurements_match_target_and_anchor(self):
        self.assertIsNone(S.witness_error(self.proof, self.idx))

    def test_complete_four_ayah_context_requires_measured_prefix_and_every_anchor(self):
        from common import load_index, load_text, surah_slice
        from spoken_letters import alignment_text
        begin, _, _ = surah_slice(load_index(), 20)
        fourth = alignment_text(20, 4, load_text('hafs')[begin + 3])
        self.idx['entries'].append({'ayahId': '20:4', 'endMs': 20000})
        self.idx['alignmentWindowEvidenceBySurah'] = {'20': {'range': [1, 4], 'windowMs': [0, 20000]}}
        self.proof.update(range=[1, 4], windowMs=[0, 20000])
        for model in self.proof['models'].values():
            model['alignmentInput'].append(fourth)
            model['entries'].append({'ayahIdx': 3, 'startMs': 15000, 'endMs': 20000, 'conf': .6})
        self.assertIsNone(S.witness_error(self.proof, self.idx))
        self.proof['models']['generic']['entries'][3]['conf'] = .44
        self.assertIsNotNone(S.witness_error(self.proof, self.idx))
        self.proof['models']['generic']['entries'][3]['conf'] = .6
        self.idx['alignmentWindowEvidenceBySurah']['20']['range'] = [1, 3]
        self.assertIsNotNone(S.witness_error(self.proof, self.idx))

    def test_sealed_actual_ci_version_keeps_provenance_but_unknown_hash_is_rejected(self):
        self.proof['provenance'] = {
            'kind': 'audio', 'source': 'ci', 'run_id': '36927909295',
            'tool': 'tools/index_qa/ci_spoken_census.py',
            'tool_sha': next(iter(S.SEALED_CI_TOOL_SHAS))}
        row = {'aid': '20:1', 'kind': 'بريء', 'independentSpokenCtc': self.proof,
               'originalTinyRow': {'aid': '20:1', 'kind': 'غير حاسم'}}
        report = {'sample': {'rows': [row]}}
        self.assertIsNone(S.report_error(report, self.idx))
        self.proof['provenance']['tool_sha'] = 'f' * 64
        self.assertIsNotNone(S.report_error(report, self.idx))

    def test_cannot_clear_arbitrary_unknown_rows_or_weak_disagreeing_evidence(self):
        mutations = [lambda p: p.update(context='arbitrary-window'),
                     lambda p: p.update(runtime={'precision':'int8','threads':2}),
                     lambda p: p.update(range=[1, 4]),
                     lambda p: p.update(windowMs=[0, 15001]),
                     lambda p: p['models']['quran']['alignmentInput'].__setitem__(2, 'invented text'),
                     lambda p: p['models']['quran']['entries'][2].update(startMs=10000),
                     lambda p: p.update(target='20:2'),
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

    def test_targeted_joined_names_require_exact_preroll_and_original_neighbours(self):
        proof=copy.deepcopy(self.proof)
        proof.update(context='targeted-joined',windowMs=[3000,15000])
        for m in proof['models'].values():
            m['alignmentInput']=m['alignmentInput'][1:]
            m['alignmentInput'][0]='طاها'
        self.assertIsNone(S.witness_error(proof,self.idx))
        proof['windowMs'][0]=3100
        self.assertIsNotNone(S.witness_error(proof,self.idx))

    def test_census_cannot_claim_confirmation_without_original_row_or_ci_tool_provenance(self):
        row = {'aid': '20:1', 'kind': 'بريء', 'independentSpokenCtc': self.proof}
        self.assertIsNotNone(S.report_error({'sample': {'rows': [row]}}, self.idx))
        row['originalTinyRow'] = {'aid': '20:1', 'kind': 'غير حاسم'}
        self.assertIsNotNone(S.report_error({'sample': {'rows': [row]}}, self.idx))
        self.assertIsNone(S.report_error({'sample': {'rows': []}}, self.idx))


if __name__ == '__main__':
    unittest.main()
