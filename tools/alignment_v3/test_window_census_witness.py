# -*- coding: utf-8 -*-
"""اختباراتُ شاهد النوافذ غير الحاسمة: يقبل القياسَ المطابق، ويردّ النافذةَ المنزاحةَ بآية
(‏المرشّحُ المكبوس 9643cf98)، والثقةَ الضعيفة، وخلافَ النموذجين، وأيَّ حكمٍ معاكس."""
import copy
import hashlib
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import window_census_witness as X
import dual_ctc_model as D
import quran_ctc_model as Q
from common import load_index, load_text, norm, surah_slice

RATE = 110          # م.ث/حرف — معدّلٌ موحَّدٌ للفهرس الاصطناعيّ
GAP = 400           # صمتٌ بين الآيات
SHA = 'c' * 64


def synthetic_index():
    begin, stop, _ = surah_slice(load_index(), 38)
    refs = load_text('hafs')[begin:stop]
    entries, t = [], 6375
    for i, text in enumerate(refs):
        dur = RATE * len(norm(text).replace(' ', ''))
        entries.append({'ayahId': f'38:{i + 1}', 'startMs': t, 'endMs': t + dur, 'conf': .7,
                        'fileRef': 'https://archive.org/download/asim-al-lahidan/038.mp3'})
        t += dur + GAP
    shas = ['a' * 64] * 114; shas[37] = SHA
    return {'reciterId': 'asim', 'riwaya': 'hafs', 'audioSha256': shas,
            'engineBySurah': {'38': 'ctc-heardmap-1'}, 'entries': entries}, t + 2000


def exact_proof(idx, total, aid, jitter=0):
    """شاهدٌ يقيس الآياتِ حيث يقول الفهرسُ تماماً (‏مع ارتجافٍ اختياريّ)."""
    ids, window, texts = X.plan(idx, aid, total)
    proof = {'target': aid, 'sourceSha256': SHA, 'canonicalTextChanged': False, 'contextAyahIds': ids,
             'windowMs': window, 'totalMs': total, 'runtime': {'precision': 'float32', 'threads': 2}, 'models': {}}
    for name, ident, revision, weights in X.MODELS:
        entries, last = [], window[0]
        for i, cid in enumerate(ids):
            if cid.endswith(':basmala'):
                st, en = window[0] + 1000, X._entry(idx, aid)['startMs'] - 200
            else:
                e = X._entry(idx, cid); st, en = e['startMs'] + jitter, e['endMs'] + jitter
            st = max(st, last); en = min(en, window[1])
            entries.append({'ayahId': cid, 'startMs': st, 'endMs': en, 'conf': .8 if cid == aid else .6})
            last = en
        for i in range(len(entries) - 1):
            entries[i]['endMs'] = entries[i + 1]['startMs']
        proof['models'][name] = {'alignmentModel': {'id': ident, 'revision': revision, 'weightsSha256': weights,
                                                    'license': 'Apache-2.0'},
                                 'alignmentInput': list(texts), 'entries': entries}
    return proof


class WindowWitnessTest(unittest.TestCase):
    def setUp(self):
        self.idx, self.total = synthetic_index()
        self.proof = exact_proof(self.idx, self.total, '38:40')

    def test_measured_target_inside_candidate_window_is_accepted(self):
        self.assertIsNone(X.witness_error(self.proof, self.idx, '38:40'))
        self.assertIsNone(X.witness_error(exact_proof(self.idx, self.total, '38:40', jitter=300), self.idx, '38:40'))

    def test_opener_and_tail_windows_use_basmala_and_file_bounds(self):
        ids, window, texts = X.plan(self.idx, '38:1', self.total)
        self.assertEqual(ids, ['38:basmala', '38:1', '38:2'])
        self.assertEqual(window[0], 0)
        self.assertEqual(texts[0], X.BASMALA)
        self.assertTrue(texts[1].startswith('صاد '))      # الحرفُ المقطّع يُنطق باسمه
        self.assertIsNone(X.witness_error(exact_proof(self.idx, self.total, '38:1'), self.idx, '38:1'))
        ids, window, _ = X.plan(self.idx, '38:88', self.total)
        self.assertEqual(ids, ['38:87', '38:88'])
        self.assertEqual(window[1], min(self.total, X._entry(self.idx, '38:88')['endMs'] + X.TAIL_PAD_MS))
        self.assertIsNone(X.witness_error(exact_proof(self.idx, self.total, '38:88'), self.idx, '38:88'))

    def test_window_shifted_by_one_ayah_is_rejected(self):
        """المرشّحُ المكبوس: يزعم أنّ 38:40 في موضعٍ، والصوتُ هناك آيةٌ أخرى؛ فالقياسُ الصادق
        يضع نصَّ الآية في غير حدود المرشّح (‏أو يتعذّر بثقةٍ ضعيفة) ⇒ لا براءة."""
        e40, e41 = X._entry(self.idx, '38:40'), X._entry(self.idx, '38:41')
        shift = e41['startMs'] - e40['startMs']
        compressed = copy.deepcopy(self.idx)
        # الفهرسُ المكبوس: كلُّ آيةٍ من 38:30 فصاعداً منزاحةٌ آيةً إلى الوراء (تحمل حدودَ سابقتها)
        for k in range(88, 30, -1):
            prev = X._entry(self.idx, f'38:{k - 1}')
            X._entry(compressed, f'38:{k}').update(startMs=prev['startMs'], endMs=prev['endMs'])
        proof = exact_proof(compressed, self.total, '38:40')
        # القياسُ الصادق داخل تلك النافذة يجد نصَّ 38:40 حيث هو فعلاً (‏بعد زعم المرشّح بآية)
        for name in ('generic', 'quran'):
            for e in proof['models'][name]['entries']:
                e['startMs'] += shift; e['endMs'] += shift
            proof['models'][name]['entries'][-1]['endMs'] = proof['windowMs'][1]
        self.assertGreater(shift, X.START_TOL)
        self.assertIsNotNone(X.witness_error(proof, compressed, '38:40'))
        # والنافذةُ نفسُها لا تُقبل لآيةٍ غيرِ المعنيّة ولو طابقت حدودَها
        self.assertIsNotNone(X.witness_error(self.proof, self.idx, '38:41'))
        p = copy.deepcopy(self.proof); p['windowMs'][1] += 1000
        self.assertIsNotNone(X.witness_error(p, self.idx, '38:40'))

    def test_weak_target_or_anchor_or_disagreeing_models_are_rejected(self):
        for name, pos, conf in [('generic', 1, .599), ('quran', 1, .599), ('generic', 0, .449),
                                ('quran', 2, .449), ('generic', 1, float('nan'))]:
            p = copy.deepcopy(self.proof); p['models'][name]['entries'][pos]['conf'] = conf
            self.assertIsNotNone(X.witness_error(p, self.idx, '38:40'), (name, pos, conf))
        p = exact_proof(self.idx, self.total, '38:40')
        t = p['models']['quran']['entries'][1]; t['startMs'] += 450; p['models']['quran']['entries'][0]['endMs'] += 450
        p['models']['generic']['entries'][1]['startMs'] -= 450; p['models']['generic']['entries'][0]['endMs'] -= 450
        self.assertIsNotNone(X.witness_error(p, self.idx, '38:40'))   # 900 بين النموذجين

    def test_duration_source_model_and_runtime_are_guarded(self):
        for mutation in [lambda p, i: p.update(sourceSha256='f' * 64),
                         lambda p, i: i['audioSha256'].__setitem__(37, 'f' * 64),
                         lambda p, i: p.update(canonicalTextChanged=True),
                         lambda p, i: p.update(runtime={'precision': 'int8', 'threads': 2}),
                         lambda p, i: p['models']['quran']['alignmentModel'].update(weightsSha256='0' * 64),
                         lambda p, i: p['models']['generic']['alignmentInput'].__setitem__(1, 'غير النص'),
                         lambda p, i: p['models']['generic']['entries'].pop(),
                         lambda p, i: p.update(contextAyahIds=['38:39', '38:40'])]:
            p, i = copy.deepcopy(self.proof), copy.deepcopy(self.idx); mutation(p, i)
            self.assertIsNotNone(X.witness_error(p, i, '38:40'))
        # مدّةٌ خارج الحدود: المرشّحُ يزعم آيةً بثُلث مدّتها المتوقَّعة والشاهدُ يطابقه
        i = copy.deepcopy(self.idx); e = X._entry(i, '38:40'); e['endMs'] = e['startMs'] + (e['endMs'] - e['startMs']) // 3
        X._entry(i, '38:41')['startMs'] = e['endMs'] + GAP
        self.assertIsNotNone(X.witness_error(exact_proof(i, self.total, '38:40'), i, '38:40'))

    def test_report_never_overrides_adverse_rows_and_requires_ci_provenance(self):
        tool = pathlib.Path(X.__file__).parents[1] / 'index_qa' / 'ci_window_census.py'
        self.proof['provenance'] = {'kind': 'audio', 'source': 'ci', 'run_id': '12345',
                                    'tool': 'tools/index_qa/ci_window_census.py',
                                    'tool_sha': hashlib.sha256(tool.read_bytes()).hexdigest()}
        row = {'aid': '38:40', 'kind': 'بريء', 'verdict': 'بريء',
               'originalTinyRow': {'aid': '38:40', 'kind': 'غير حاسم'}, X.FIELD: self.proof}
        report = {'sample': {'rows': [{'aid': '38:39', 'kind': 'غير حاسم'}, row, {'aid': '38:41', 'kind': 'جسيم'}]}}
        self.assertIsNone(X.report_error(report, self.idx))
        for original_kind in ('جسيم', 'طفيف', 'تعذّر'):
            row['originalTinyRow']['kind'] = original_kind
            self.assertIsNotNone(X.report_error(report, self.idx))
        row['originalTinyRow']['kind'] = 'غير حاسم'
        del row['originalTinyRow']; self.assertIsNotNone(X.report_error(report, self.idx))
        row['originalTinyRow'] = {'aid': '38:40', 'kind': 'غير حاسم'}
        row['kind'] = 'جسيم'; self.assertIsNotNone(X.report_error(report, self.idx)); row['kind'] = 'بريء'
        self.proof['provenance']['tool_sha'] = 'f' * 64
        self.assertIsNotNone(X.report_error(report, self.idx))
        self.assertIsNone(X.report_error({'sample': {'rows': [{'aid': '38:40', 'kind': 'غير حاسم'}]}}, {}))

    def test_wiring_promote_hook_workflow_and_allowed_list(self):
        root = pathlib.Path(X.__file__).parents[2]
        promote = (root / 'tools' / 'index_qa' / 'promote.py').read_text(encoding='utf-8')
        self.assertIn('from window_census_witness import report_error as window_report_error', promote)
        self.assertLess(promote.index('window_report_error(rep, idx)'), promote.index('inc * 2 > want'))
        self.assertIn('if inc * 2 > want:', promote)              # الحارسُ كما هو
        self.assertIn('"window_census.yml"', (root / 'tools' / 'ci_fleet' / 'agent_cmd.py').read_text(encoding='utf-8'))
        wf = (root / '.github' / 'workflows' / 'window_census.yml').read_text(encoding='utf-8')
        self.assertIn("CTC_INT8: '0'", wf); self.assertIn("CTC_THREADS: '2'", wf)
        self.assertIn('tools/index_qa/ci_window_census.py --key "$KEY" --surah "$SURAH"', wf)


if __name__ == '__main__':
    unittest.main()
