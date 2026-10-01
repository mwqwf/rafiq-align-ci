"""Independent, narrowly scoped witness for the fixed spoken opener طه.

Unknown Tiny output is preserved. Two different pinned CTC models must both
find the canonical spoken letters and their following anchor in original PCM.
This is not a general waiver for unknown census rows.
"""
import math
import pathlib

from dual_ctc_model import GENERIC_ID, GENERIC_REVISION, GENERIC_WEIGHTS
from quran_ctc_model import MODEL_ID, REVISION, WEIGHTS_SHA256

# Sealed v1 producer used by independently successful CI run 36927909295.
# Preserve its real provenance; all current semantic checks still apply.
SEALED_CI_TOOL_SHAS = frozenset({
    '09e91fc19680e4de41210a3d38f3cca101c9f6c5a4952c35e75183a6af867fbd',
})


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
        hi = proof['range'][1]
        if proof['range'][0] != 1 or type(hi) is not int or hi not in (3, 4, 5):
            raise ValueError('wrong bounded canonical prefix')
        if hi > 3:
            ev = idx['alignmentWindowEvidenceBySurah']['20']
            if ev['range'][0] != 1 or not hi <= ev['range'][1] <= 5 or ev['windowMs'][0] != 0:
                raise ValueError('context outside candidate measured prefix')
        refs = load_text(idx['riwaya'])[begin:begin + hi]
        canonical_input = ['بسم الله الرحمن الرحيم'] + [
            alignment_text(20, i, refs[i - 1]) for i in range(1, hi + 1)]
        prefix_end = next(e['endMs'] for e in idx['entries'] if e['ayahId'] == f'20:{hi}')
        context = proof['context']
        prefix_start = 0
        if context == 'targeted-joined':
            prefix_start = max(0, row['startMs'] - 1000)
            canonical_input = canonical_input[1:]
            canonical_input[0] = canonical_input[0].replace(' ', '')
        elif context != 'full-prefix':
            raise ValueError('unknown physical context')
        if (proof['windowMs'] != [prefix_start, prefix_end]
                or proof['runtime'] != {'precision': 'float32', 'threads': 2}):
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
            if (len(entries) != hi or [e['ayahIdx'] for e in entries] != list(range(hi))
                    or entries[0]['conf'] < .7 or entries[1]['conf'] < .5
                    or any(not math.isfinite(e['conf']) or e['conf'] < .45 or e['conf'] > 1
                           for e in entries)):
                raise ValueError('insufficient independent target or anchor confidence')
            previous = prefix_start
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
                or provenance.get('tool_sha') not in SEALED_CI_TOOL_SHAS | {
                    hashlib.sha256(tool.read_bytes()).hexdigest()}):
            return 'Spoken witness lacks reviewed CI tool provenance'
        error = witness_error(proof, idx)
        if error:
            return error
    return None
