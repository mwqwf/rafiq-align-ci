"""Two measured canonical witnesses for the known Warsh 85:22 source.

Preserves inconclusive Tiny evidence. This does not clear other targets,
adverse verdicts, changed sources, weak anchors, or mismatched boundaries.
"""
import hashlib
import math
import pathlib
import statistics

from dual_ctc_model import ENGINE, GENERIC_ID, GENERIC_REVISION, GENERIC_WEIGHTS
from quran_ctc_model import MODEL_ID, REVISION, WEIGHTS_SHA256

SOURCE_URL = 'https://archive.org/download/chinguit_01/60.ogg'
SOURCE_SHA = '3379207275de071c5a1c32fd04e30e23498bf4eeebc2034f20235c41f7d01ddc'
CONTEXT_IDS = ['85:21', '85:22', '86:basmala']


def canonical_input(idx):
    from common import load_index, load_text, surah_slice
    from spoken_letters import alignment_text
    begin, _, _ = surah_slice(load_index(), 85)
    refs = load_text(idx['riwaya'])[begin:begin + 22]
    return [alignment_text(85, i, refs[i - 1]) for i in (21, 22)] + ['بسم الله الرحمن الرحيم']


def witness_error(proof, idx):
    try:
        rows = [e for e in idx['entries'] if e['ayahId'].startswith('85:')]
        if (idx['reciterId'] != 'laghdaf_shinqiti' or idx['riwaya'] != 'warsh'
                or idx['engineBySurah']['85'] != ENGINE
                or idx['audioSha256'][84] != SOURCE_SHA
                or idx['sourceBySurah']['85'] != SOURCE_URL
                or len(rows) != 22 or {e['fileRef'] for e in rows} != {SOURCE_URL}
                or proof['target'] != '85:22' or proof['sourceSha256'] != SOURCE_SHA
                or proof['canonicalTextChanged'] is not False
                or proof['contextAyahIds'] != CONTEXT_IDS
                or proof['runtime'] != {'precision': 'float32', 'threads': 2}):
            raise ValueError('wrong fixed target, source, context, engine or runtime')
        previous_row = next(e for e in rows if e['ayahId'] == '85:21')
        target = next(e for e in rows if e['ayahId'] == '85:22')
        start, end = previous_row['startMs'], target['endMs'] + 6000
        total = idx['dualAlignmentEvidenceBySurah']['85']['totalMs']
        if proof['windowMs'] != [start, end] or not 0 <= start < end <= total:
            raise ValueError('wrong fixed complete context window')
        from common import load_index, load_text, norm, surah_slice
        begin, stop, _ = surah_slice(load_index(), 85)
        refs = load_text('warsh')[begin:stop]
        chars = [len(norm(t).replace(' ', '')) for t in refs]
        base = idx['dualAlignmentEvidenceBySurah']['85']['baseMeasurements']
        median = statistics.median((e['endMs'] - e['startMs']) / chars[i]
                                   for i, e in enumerate(base) if e['conf'] >= .5)
        input_text = canonical_input(idx)
        sizes = [len(norm(t).replace(' ', '')) for t in input_text]
        measured = []
        for name, ident, revision, weights in [
                ('generic', GENERIC_ID, GENERIC_REVISION, GENERIC_WEIGHTS),
                ('quran', MODEL_ID, REVISION, WEIGHTS_SHA256)]:
            result = proof['models'][name]
            model = result['alignmentModel']
            if (model['id'], model['revision'], model['weightsSha256'], model['license']) != (
                    ident, revision, weights, 'Apache-2.0'):
                raise ValueError('unpinned independent model')
            entries = result['entries']
            if (result['alignmentInput'] != input_text or len(entries) != 3
                    or [e['ayahId'] for e in entries] != CONTEXT_IDS
                    or entries[1]['conf'] < .7 or entries[0]['conf'] < .5
                    or entries[2]['conf'] < .5
                    or any(not math.isfinite(e['conf']) or not .45 <= e['conf'] <= 1
                           for e in entries)):
                raise ValueError('incomplete canonical input or weak target or anchor')
            last = start
            for e, count in zip(entries, sizes):
                if (not last <= e['startMs'] < e['endMs'] <= end
                        or not .5 * median * count <= e['endMs'] - e['startMs'] <= 2 * median * count):
                    raise ValueError('invalid context interval or duration')
                last = e['endMs']
            for actual, indexed in [(entries[0], previous_row), (entries[1], target)]:
                if (abs(actual['startMs'] - indexed['startMs']) > 300
                        or abs(actual['endMs'] - indexed['endMs']) > 500):
                    raise ValueError('witness differs from candidate boundary')
            if entries[1]['endMs'] != entries[2]['startMs']:
                raise ValueError('next basmala does not anchor target end')
            measured.append(entries[1])
        if (abs(measured[0]['startMs'] - measured[1]['startMs']) > 300
                or abs(measured[0]['endMs'] - measured[1]['endMs']) > 500):
            raise ValueError('independent models disagree')
    except (KeyError, ValueError, TypeError, IndexError, StopIteration) as exc:
        return 'Canonical tail witness rejected: ' + str(exc)
    return None


def report_error(report, idx):
    for row in report.get('sample', {}).get('rows', []):
        proof = row.get('independentCanonicalTailCtc')
        if proof is None:
            continue
        original = row.get('originalTinyRow') or {}
        if (row.get('aid') != '85:22' or row.get('kind') != 'بريء'
                or original.get('aid') != row['aid'] or original.get('kind') != 'غير حاسم'):
            return 'Canonical tail witness cannot override another target or adverse verdict'
        provenance = proof.get('provenance') or {}
        tool = pathlib.Path(__file__).parents[1] / 'index_qa' / 'ci_tail_census.py'
        if (provenance.get('kind') != 'audio' or provenance.get('source') != 'ci'
                or not str(provenance.get('run_id') or '').isdigit()
                or provenance.get('tool') != 'tools/index_qa/ci_tail_census.py'
                or provenance.get('tool_sha') != hashlib.sha256(tool.read_bytes()).hexdigest()):
            return 'Canonical tail witness lacks reviewed CI producer provenance'
        error = witness_error(proof, idx)
        if error:
            return error
    return None
