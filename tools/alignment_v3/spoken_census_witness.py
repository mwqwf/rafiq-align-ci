"""Independent, narrowly scoped witness for the fixed spoken opener طه.

Unknown Tiny output is preserved. Two different pinned CTC models must both
find the canonical spoken letters and their following anchor in original PCM.
This is not a general waiver for unknown census rows.
"""
import math
import pathlib

from dual_ctc_model import GENERIC_ID, GENERIC_REVISION, GENERIC_WEIGHTS
from quran_ctc_model import MODEL_ID, REVISION, WEIGHTS_SHA256


def witness_error(proof, idx):
    try:
        if (proof['target'] != '20:1' or proof['canonicalTextChanged'] is not False
                or (idx.get('engineBySurah') or {}).get('20') != 'ctc-spoken-1'
                or proof['sourceSha256'] != idx['audioSha256'][19]):
            raise ValueError('wrong target, engine, source or canonical text')
        row = next(e for e in idx['entries'] if e['ayahId'] == '20:1')
        from common import load_index, load_text, surah_slice
        from spoken_letters import alignment_text
        begin, _, _ = surah_slice(load_index(), 20)
        refs = load_text(idx['riwaya'])[begin:begin + 3]
        canonical_input = ['بسم الله الرحمن الرحيم'] + [
            alignment_text(20, i, refs[i - 1]) for i in range(1, 4)]
        prefix_end = next(e['endMs'] for e in idx['entries'] if e['ayahId'] == '20:3')
        if proof['range'] != [1, 3] or proof['windowMs'] != [0, prefix_end]:
            raise ValueError('wrong fixed canonical context window')
        expected = [('generic', GENERIC_ID, GENERIC_REVISION, GENERIC_WEIGHTS),
                    ('quran', MODEL_ID, REVISION, WEIGHTS_SHA256)]
        measured = []
        for name, ident, revision, weights in expected:
            result = proof['models'][name]
            model = result['alignmentModel']
            if (model['id'], model['revision'], model['weightsSha256'], model['license']) != (
                    ident, revision, weights, 'Apache-2.0'):
                raise ValueError('unpinned independent model')
            if result['alignmentInput'] != canonical_input:
                raise ValueError('wrong spoken reference')
            entries = result['entries']
            if (len(entries) != 3 or [e['ayahIdx'] for e in entries] != [0, 1, 2]
                    or entries[0]['conf'] < .7 or entries[1]['conf'] < .5
                    or any(not math.isfinite(e['conf']) or e['conf'] < .45 or e['conf'] > 1
                           for e in entries)):
                raise ValueError('insufficient independent target or anchor confidence')
            previous = 0
            for e in entries:
                if not previous <= e['startMs'] < e['endMs'] <= prefix_end:
                    raise ValueError('invalid independent context interval')
                previous = e['endMs']
            first = entries[0]
            if not (0 <= first['startMs'] < first['endMs'] <= entries[1]['startMs']):
                raise ValueError('invalid target interval')
            if (abs(first['startMs'] - row['startMs']) > 300
                    or abs(first['endMs'] - row['endMs']) > 500):
                raise ValueError('witness does not match candidate boundary')
            measured.append(first)
        if (abs(measured[0]['startMs'] - measured[1]['startMs']) > 300
                or abs(measured[0]['endMs'] - measured[1]['endMs']) > 500):
            raise ValueError('independent models disagree')
    except (KeyError, ValueError, TypeError, IndexError, StopIteration) as exc:
        return 'Spoken census witness rejected: ' + str(exc)
    return None


def report_error(report, idx):
    for row in report.get('sample', {}).get('rows', []):
        proof = row.get('independentSpokenCtc')
        if proof is None:
            continue
        if row.get('aid') != '20:1' or row.get('kind') != 'بريء':
            return 'Spoken witness cannot clear another ayah or override an adverse verdict'
        original = row.get('originalTinyRow') or {}
        if original.get('kind') != 'غير حاسم' or original.get('aid') != row['aid']:
            return 'Original inconclusive Tiny evidence must be preserved'
        provenance = proof.get('provenance') or {}
        tool = pathlib.Path(__file__).parents[1] / 'index_qa' / 'ci_spoken_census.py'
        import hashlib
        if (provenance.get('kind') != 'audio' or provenance.get('source') != 'ci'
                or not str(provenance.get('run_id') or '').isdigit()
                or provenance.get('tool') != 'tools/index_qa/ci_spoken_census.py'
                or provenance.get('tool_sha') != hashlib.sha256(tool.read_bytes()).hexdigest()):
            return 'Spoken witness lacks current CI tool provenance'
        error = witness_error(proof, idx)
        if error:
            return error
    return None
