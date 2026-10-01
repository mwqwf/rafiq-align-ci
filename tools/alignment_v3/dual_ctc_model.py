"""Honest provenance for pinned Quran CTC plus measured generic CTC windows.

This engine changes no acceptance threshold. Every window must pass the same
confidence, neighbour and duration checks before the existing audio gates run.
"""
import math
import statistics
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parents[1] / 'alignment'))

ENGINE = 'ctc-dual-window-1'
GENERIC_ID = 'jonatasgrosman/wav2vec2-large-xlsr-53-arabic'
GENERIC_REVISION = 'af46c2d8531b8dcbb5e23b952f739b372c2e5d2d'
GENERIC_WEIGHTS = 'a0b26f6d9d3edfde1784aef863c192a8cc1e438a23b45910ab648531ebe1857b'


def evidence_error(evidence, source_sha, rows):
    from quran_ctc_model import MODEL_ID, REVISION, WEIGHTS_SHA256
    try:
        if evidence['canonicalTextChanged'] is not False or evidence['sourceSha256'] != source_sha:
            raise ValueError('source or canonical text')
        for key, ident, revision, weights in [
                ('quran', MODEL_ID, REVISION, WEIGHTS_SHA256),
                ('generic', GENERIC_ID, GENERIC_REVISION, GENERIC_WEIGHTS)]:
            model = evidence['models'][key]
            if (model['id'], model['revision'], model['weightsSha256'], model['license']) != (
                    ident, revision, weights, 'Apache-2.0'):
                raise ValueError('unpinned model')
        measurements = evidence['measurements']
        from common import load_index, load_text, norm, surah_slice
        from spoken_letters import alignment_text
        surah = evidence['surah']
        begin, end, _ = surah_slice(load_index(), surah)
        refs = load_text(evidence['riwaya'])[begin:end]
        chars = [len(norm(t).replace(' ', '')) for t in refs]
        if len(measurements) != len(rows):
            raise ValueError('incomplete entry provenance')
        if len(rows) != len(refs):
            raise ValueError('incomplete surah')
        baseline = evidence['baseMeasurements']
        if len(baseline) != len(rows):
            raise ValueError('incomplete base measurement')
        median = statistics.median((e['endMs'] - e['startMs']) / chars[i]
                                  for i, e in enumerate(baseline)
                                  if e['startMs'] is not None and e['conf'] >= .5 and chars[i])
        for position, (actual, measured) in enumerate(zip(rows, measurements)):
            if measured['model'] not in ('quran', 'generic', 'inherited'):
                raise ValueError('unknown entry model')
            for field in ('startMs', 'endMs', 'conf'):
                if actual[field] != measured[field]:
                    raise ValueError('entry differs from measured evidence')
            conf = measured['conf']
            if not math.isfinite(conf) or not 0 <= conf <= 1:
                raise ValueError('invalid confidence')
            if measured['model'] != 'inherited' and conf < .45:
                raise ValueError('low new confidence')
            if measured['model'] == 'quran' and any(
                    measured[f] != baseline[position][f] for f in ('startMs', 'endMs', 'conf')):
                raise ValueError('changed Quran base measurement')
            if conf >= .8 and measured.get('snapped') is not True:
                raise ValueError('HIGH without silence witness')
        previous = -1
        for entry in measurements:
            if not previous <= entry['startMs'] < entry['endMs'] <= evidence['totalMs']:
                raise ValueError('invalid measured interval')
            previous = entry['endMs']
        windows = evidence['windows']
        if not windows:
            raise ValueError('no measured complementary window')
        covered = set()
        for window in windows:
            if (window['sourceSha256'] != source_sha or window['canonicalTextChanged'] is not False
                    or window['accepted'] is not True or window['durationBad'] or window['issues']):
                raise ValueError('unaccepted window')
            lo, hi = window['range']
            measured = measurements[lo - 1:hi]
            if (lo < 1 or hi < lo or hi > len(rows) or len(measured) != hi - lo + 1
                    or any(e['model'] != 'generic' for e in measured)
                    or measured[0]['conf'] < .5 or measured[-1]['conf'] < .5):
                raise ValueError('weak neighbour or incomplete window')
            covered.update(range(lo - 1, hi))
            context_lo, context_hi = window.get('contextRange', window['range'])
            if not 1 <= context_lo <= lo <= hi <= context_hi <= len(rows):
                raise ValueError('invalid canonical context range')
            if 'contextRange' in window:
                context = window['contextEntries']
                if (len(context) != context_hi - context_lo + 1
                        or [e['ayahIdx'] for e in context] != list(range(context_lo - 1, context_hi))
                        or window['entries'] != context[lo - context_lo:hi - context_lo + 1]):
                    raise ValueError('selected rows differ from full raw context')
                start, end = window['windowMs']
                if not 0 <= start < end <= evidence['totalMs']:
                    raise ValueError('invalid original context window')
                previous = start
                for e in context:
                    if (not previous <= e['startMs'] < e['endMs'] <= end
                            or not math.isfinite(e['conf']) or not 0 <= e['conf'] <= 1):
                        raise ValueError('invalid raw context measurement')
                    previous = e['endMs']
            expected = [alignment_text(surah, i, refs[i - 1]) for i in range(context_lo, context_hi + 1)]
            actual_input = window['alignmentInput']
            if context_lo == 1 and actual_input[:1] == ['بسم الله الرحمن الرحيم']:
                actual_input = actual_input[1:]
            if actual_input != expected:
                raise ValueError('window input differs from canonical reference')
            raw_rows = window['entries']
            if len(raw_rows) != len(measured):
                raise ValueError('incomplete raw window')
            for entry, raw in zip(measured, raw_rows):
                if (entry['startMs'] != raw['startMs'] or entry['endMs'] != raw['endMs']
                        or entry['conf'] != min(raw['conf'], .74) or entry.get('snapped') is not False):
                    raise ValueError('raw complementary measurement changed')
            for i in range(lo - 1, hi):
                duration = measurements[i]['endMs'] - measurements[i]['startMs']
                if not .5 * median * chars[i] <= duration <= 2 * median * chars[i]:
                    raise ValueError('window duration outside unchanged bounds')
        if covered != {i for i, e in enumerate(measurements) if e['model'] == 'generic'}:
            raise ValueError('unwitnessed complementary entry')
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        return 'Dual CTC evidence rejected: ' + str(exc)
    return None


def records_error(idx):
    for surah, engine in (idx.get('engineBySurah') or {}).items():
        if engine != ENGINE:
            continue
        s = int(surah)
        evidence = (idx.get('dualAlignmentEvidenceBySurah') or {}).get(str(s), {})
        rows = [e for e in idx.get('entries', []) if e['ayahId'].startswith(str(s) + ':')]
        shas = idx.get('audioSha256') or []
        error = evidence_error(evidence, shas[s - 1] if len(shas) >= s else None, rows)
        if error:
            return f'س{s}: {error}'
    return None
