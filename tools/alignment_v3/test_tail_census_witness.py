import copy
import hashlib
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import tail_census_witness as T
import dual_ctc_model as D
import quran_ctc_model as Q


class CanonicalTailTest(unittest.TestCase):
    def setUp(self):
        pairs = [(138112,142465),(142465,144086),(144086,149920),(149920,152792),
                 (152792,155674),(155674,158065),(158065,166691),(166691,178639),
                 (178639,189667),(189667,206978),(206978,225040),(225040,229633),
                 (229633,233506),(233506,236057),(236057,239770),(239770,244003),
                 (244003,247275),(247275,250707),(250707,254890),(254890,263416),
                 (263416,267338),(267338,272702)]
        base = [{'ayahIdx': i, 'startMs': a, 'endMs': b, 'conf': .74} for i,(a,b) in enumerate(pairs)]
        self.idx = {'reciterId': 'laghdaf_shinqiti', 'riwaya': 'warsh',
                    'audioSha256': ['a'*64]*84+[T.SOURCE_SHA]+['a'*64]*29,
                    'sourceBySurah': {'85': T.SOURCE_URL}, 'engineBySurah': {'85': D.ENGINE},
                    'dualAlignmentEvidenceBySurah': {'85': {'totalMs': 1823138, 'baseMeasurements': base}},
                    'entries': [dict(e, ayahId=f'85:{i+1}', fileRef=T.SOURCE_URL) for i,e in enumerate(base)]}
        self.proof = {'target': '85:22', 'sourceSha256': T.SOURCE_SHA, 'canonicalTextChanged': False,
                      'contextAyahIds': T.CONTEXT_IDS.copy(), 'windowMs': [263416,278702],
                      'runtime': {'precision': 'float32', 'threads': 2}, 'models': {}}
        for name, ident, revision, weights, values in [
                ('generic', D.GENERIC_ID, D.GENERIC_REVISION, D.GENERIC_WEIGHTS,
                 [(263616,267297,.652),(267297,272699,.85),(272699,276891,.696)]),
                ('quran', Q.MODEL_ID, Q.REVISION, Q.WEIGHTS_SHA256,
                 [(263646,267337,.662),(267337,272699,.818),(272699,276871,.679)])]:
            self.proof['models'][name] = {'alignmentModel': {'id': ident, 'revision': revision,
                    'weightsSha256': weights, 'license': 'Apache-2.0'},
                    'alignmentInput': T.canonical_input(self.idx),
                    'entries': [{'ayahId': aid, 'startMs': a, 'endMs': b, 'conf': c}
                                for aid,(a,b,c) in zip(T.CONTEXT_IDS,values)]}

    def test_measured_original_canonical_target_and_both_anchors_match(self):
        self.assertIsNone(T.witness_error(self.proof,self.idx))

    def test_other_target_reciter_riwaya_engine_or_source_never_eligible(self):
        for mutation in [lambda p,i:p.update(target='85:21'), lambda p,i:i.update(reciterId='other'),
                         lambda p,i:i.update(riwaya='hafs'), lambda p,i:i['engineBySurah'].update({'85':'ctc-spoken-1'}),
                         lambda p,i:i['audioSha256'].__setitem__(84,'f'*64),
                         lambda p,i:i['entries'][0].update(fileRef='https://other.example/60.ogg')]:
            with self.subTest(mutation=mutation):
                p,i=copy.deepcopy(self.proof),copy.deepcopy(self.idx);mutation(p,i)
                self.assertIsNotNone(T.witness_error(p,i))

    def test_uncertain_target_or_either_weak_anchor_remains_rejected(self):
        for position,confidence in [(1,.699),(0,.499),(2,.499),(1,float('nan'))]:
            p=copy.deepcopy(self.proof);p['models']['generic']['entries'][position]['conf']=confidence
            self.assertIsNotNone(T.witness_error(p,self.idx))

    def test_no_context_dropping_rewritten_text_or_changed_weights(self):
        for mutation in [lambda p:p['models']['quran']['entries'].pop(),
                         lambda p:p['models']['generic']['alignmentInput'].__setitem__(1,'غير النص'),
                         lambda p:p['models']['quran']['alignmentModel'].update(weightsSha256='0'*64),
                         lambda p:p.update(canonicalTextChanged=True),
                         lambda p:p.update(runtime={'precision':'int8','threads':2})]:
            p=copy.deepcopy(self.proof);mutation(p);self.assertIsNotNone(T.witness_error(p,self.idx))

    def test_wrong_fixed_window_early_boundary_and_duration_are_rejected(self):
        for mutation in [lambda p:p['windowMs'].__setitem__(1,279702),
                         lambda p:p['models']['generic']['entries'][1].update(startMs=264000),
                         lambda p:p['models']['generic']['entries'][1].update(endMs=278700),
                         lambda p:p['models']['generic']['entries'][2].update(endMs=272800)]:
            p=copy.deepcopy(self.proof);mutation(p);self.assertIsNotNone(T.witness_error(p,self.idx))

    def test_report_preserves_unknown_and_requires_actual_reviewed_ci_producer(self):
        tool=pathlib.Path(T.__file__).parents[1]/'index_qa'/'ci_tail_census.py'
        self.proof['provenance']={'kind':'audio','source':'ci','run_id':'12345',
              'tool':'tools/index_qa/ci_tail_census.py','tool_sha':hashlib.sha256(tool.read_bytes()).hexdigest()}
        row={'aid':'85:22','kind':'بريء','originalTinyRow':{'aid':'85:22','kind':'غير حاسم'},
             'independentCanonicalTailCtc':self.proof};report={'sample':{'rows':[row]}}
        self.assertIsNone(T.report_error(report,self.idx))
        row['originalTinyRow']['kind']='جسيم';self.assertIsNotNone(T.report_error(report,self.idx))
        row['originalTinyRow']['kind']='غير حاسم';self.proof['provenance']['tool_sha']='f'*64
        self.assertIsNotNone(T.report_error(report,self.idx))

    def test_existing_reports_without_tail_witness_are_unchanged(self):
        self.assertIsNone(T.report_error({'sample':{'rows':[{'aid':'20:1','kind':'غير حاسم'}]}},{}))


if __name__=='__main__':
    unittest.main()
