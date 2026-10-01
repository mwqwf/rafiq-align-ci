import copy
import pathlib
import sys
import unittest
import subprocess
import json

sys.path.insert(0, str(pathlib.Path(__file__).parent))
sys.path.insert(0, str(pathlib.Path(__file__).parents[1] / 'alignment'))
import dual_ctc_model as D
import quran_ctc_model as Q
from common import load_index, load_text, norm, surah_slice
from spoken_letters import alignment_text


class DualEvidenceTest(unittest.TestCase):
    def setUp(self):
        lo, hi, _ = surah_slice(load_index(), 112)
        refs = load_text('hafs')[lo:hi]
        self.rows = []
        start = 1000
        for i, text in enumerate(refs):
            duration = len(norm(text).replace(' ', '')) * 200
            self.rows.append({'ayahIdx': i, 'startMs': start, 'endMs': start + duration,
                              'conf': .7, 'snapped': False})
            start += duration
        models = {'quran': {'id': Q.MODEL_ID, 'revision': Q.REVISION,
                           'weightsSha256': Q.WEIGHTS_SHA256, 'license': 'Apache-2.0'},
                  'generic': {'id': D.GENERIC_ID, 'revision': D.GENERIC_REVISION,
                              'weightsSha256': D.GENERIC_WEIGHTS, 'license': 'Apache-2.0'}}
        self.proof = {'surah': 112, 'riwaya': 'hafs', 'sourceSha256': 'a' * 64,
                      'canonicalTextChanged': False, 'models': models, 'totalMs': start + 1000,
                      'baseMeasurements': copy.deepcopy(self.rows),
                      'measurements': [dict(e, model='generic' if i in (1, 2) else 'quran')
                                       for i, e in enumerate(self.rows)],
                      'windows': [{'sourceSha256': 'a' * 64, 'canonicalTextChanged': False,
                                   'range': [2, 3], 'accepted': True, 'durationBad': [], 'issues': [],
                                   'alignmentInput': [alignment_text(112, i, refs[i - 1]) for i in (2, 3)],
                                   'entries': copy.deepcopy(self.rows[1:3])}]}

    def check(self, proof):
        return D.evidence_error(proof, 'a' * 64, self.rows)

    def test_valid_pinned_models_and_measured_window(self):
        self.assertIsNone(self.check(self.proof))

    def test_validator_imports_reference_in_fresh_tool_process(self):
        code = "import sys,json,contextlib,io;sys.path.insert(0,sys.argv[1]);import dual_ctc_model as d;p=json.load(sys.stdin)\nwith contextlib.redirect_stdout(io.StringIO()):\n assert d.evidence_error(p,'a'*64,p['measurements']) is None"
        result = subprocess.run([sys.executable, '-c', code, str(pathlib.Path(__file__).parent)],
                                input=json.dumps(self.proof), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_rejects_each_misleading_or_incomplete_provenance(self):
        for field, value in [('revision', 'main'), ('weightsSha256', '0' * 64),
                             ('license', 'CC-BY-NC'), ('id', 'unreviewed/model')]:
            for model in ('quran', 'generic'):
                with self.subTest(model=model, field=field):
                    bad = copy.deepcopy(self.proof)
                    bad['models'][model][field] = value
                    self.assertIsNotNone(self.check(bad))
        for mutate in [lambda p: p.update(sourceSha256='b' * 64),
                       lambda p: p.update(canonicalTextChanged=True),
                       lambda p: p['windows'][0].update(accepted=False),
                       lambda p: p['windows'][0].update(durationBad=[2]),
                       lambda p: p['windows'][0].update(issues=['bad boundary']),
                       lambda p: p['windows'][0].update(alignmentInput=['invented text']),
                       lambda p: p['windows'][0]['entries'][0].update(conf=.9),
                       lambda p: p['measurements'][0].update(model='unknown'),
                       lambda p: p['measurements'][0].update(conf=.9),
                       lambda p: p['measurements'].pop(),
                       lambda p: p['windows'].clear()]:
            bad = copy.deepcopy(self.proof)
            mutate(bad)
            self.assertIsNotNone(self.check(bad))

    def test_cannot_waive_duration_guard_by_declaring_empty_bad_list(self):
        bad = copy.deepcopy(self.proof)
        for e in bad['baseMeasurements']:
            e['endMs'] = e['startMs'] + (e['endMs'] - e['startMs']) // 10
        self.assertIsNotNone(self.check(bad))

    def test_context_is_preserved_without_accepting_weak_unselected_measurements(self):
        proof = copy.deepcopy(self.proof)
        begin, end, _ = surah_slice(load_index(), 112)
        refs = load_text('hafs')[begin:end]
        window = proof['windows'][0]
        context = copy.deepcopy(self.rows)
        context[0]['conf'] = context[-1]['conf'] = .1
        window.update(contextRange=[1, 4], contextEntries=context,
                      windowMs=[1000, self.proof['totalMs']],
                      alignmentInput=[alignment_text(112, i, refs[i - 1]) for i in range(1, 5)])
        self.assertIsNone(self.check(proof))
        for change in [lambda w: w.update(contextRange=[3, 4]),
                       lambda w: w['contextEntries'][1].update(conf=.9),
                       lambda w: w['contextEntries'][0].update(startMs=0),
                       lambda w: w['contextEntries'][0].update(conf=float('nan')),
                       lambda w: w['alignmentInput'].__setitem__(0, 'invented context'),
                       lambda w: w['contextEntries'].pop(),
                       lambda w: w.update(range=[1, 3])]:
            bad = copy.deepcopy(proof)
            change(bad['windows'][0])
            self.assertIsNotNone(self.check(bad))

    def test_existing_shared_stage_and_promote_validator_rejects_missing_dual_proof(self):
        self.assertIsNotNone(Q.records_error({'engineBySurah': {'112': D.ENGINE}}))


if __name__ == '__main__':
    unittest.main()
