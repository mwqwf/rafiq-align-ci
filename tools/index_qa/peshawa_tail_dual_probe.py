#!/usr/bin/env python3
"""Read-only two-model check of the final verse after free ASR found clipping.

Two fixed windows and both native channels; canonical target only. This is a
diagnostic, not a replacement for the rejected previous-verse window witness.
"""
import argparse
import gc
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import peshawa_tail_free_decode as F
import independent_window_pilot as P

CANDIDATE = 'ops/source-repair/candidates/codex-peshawa-s63-20261005-v3.jz'
CANDIDATE_SHA = 'ef312d31cb8047ea440240c32ea9f41921bf842ae3f348af7e0d58da9b90d8e0'
WINDOW_STARTS_MS = (264000, 264500)


def assess(row, target, contract):
    e = row['entries'][0]
    begin, end = row['windowMs']
    if (not begin <= e['startMs'] < e['endMs'] <= end
            or not math.isfinite(e['conf']) or not 0 <= e['conf'] <= 1):
        raise ValueError('invalid measured interval or confidence')
    row.update(startDeltaMs=e['startMs']-target['startMs'],
               endDeltaMs=e['endMs']-target['endMs'])
    row['withinExistingTargetThresholds'] = (
        e['conf'] >= contract.TARGET_CONF
        and abs(row['startDeltaMs']) <= contract.START_TOL
        and abs(row['endDeltaMs']) <= contract.END_TOL)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-policy', choices=('cache-only', 'quran-pinned-ephemeral'), default='cache-only')
    args = parser.parse_args(argv)
    report = {'schema': 1, 'kind': 'peshawa-final-verse-target-only-dual-diagnostic',
        'measurementComplete': False, 'qualityClaim': False, 'productionChanged': False,
        'originalWindowWitnessStillRejected': True, 'replacesOfficialWitness': False,
        'limits': ['Only 63:11, after unprompted source-specific ASR located its words',
                   'Target-only alignment can force text; free ASR must be considered separately',
                   'Native channels are not independent recordings',
                   'Both models share XLSR architecture; no absolute accuracy guarantee'],
        'candidateSha256': CANDIDATE_SHA, 'sourceSha256': F.SOURCE['sha256'],
        'windowStartMs': WINDOW_STARTS_MS, 'measurements': [],
        'provenance': {'runId': os.environ.get('GITHUB_RUN_ID', ''),
            'runSha': os.environ.get('GITHUB_SHA', ''), 'toolSha256': F.S.sha_file(__file__)}}
    phase = 'environment'
    try:
        if os.environ.get('CTC_INT8') != '0' or os.environ.get('CTC_THREADS') != '2':
            raise ValueError('fixed float32/two-thread runtime required')
        report['versions'] = F.S.validate_versions()
        for key in ('HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE', 'HF_HUB_DISABLE_XET'):
            os.environ[key] = '1'
        contract = P.load_contract()
        idx, provenance = P.read_candidate(CANDIDATE, CANDIDATE_SHA, F.SOURCE['sha256'])
        target = next(e for e in idx['entries'] if e['ayahId'] == '63:11')
        report['candidateTarget'] = target
        common = importlib.import_module('common')
        begin, stop, _ = common.surah_slice(common.load_index(), 63)
        canonical = common.load_text('hafs')[begin:stop][10]
        report['canonicalReference'] = canonical
        assets = P.ROOT/'core/quran/src/main/assets/quran'
        report['referenceSha256'] = {name: F.S.sha_file(assets/name)
                                    for name in ('index.jz', 'text_hafs.jz')}
        phase = 'source'
        with tempfile.TemporaryDirectory(prefix='rafiq-peshawa-dual-', dir=os.environ.get('RUNNER_TEMP')) as tmp:
            path = Path(tmp)/'063.mp3'
            F.S.metadata.fetch(F.SOURCE['url'], path, limit=4*1024*1024)
            collector, report['audio'] = F.decode(path)
            phase = 'models'
            with F.S.model_snapshots(args.model_policy) as (snapshots, inventory):
                report['modelAcquisition'] = inventory
                import huggingface_hub as hub
                import numpy as np
                specs = P.model_specs(contract)
                bound = {(s['id'], s['revision']): snapshots[s['name']] for s in specs}
                witness = importlib.import_module('ci_spoken_census')
                backend = P.Backend(witness)
                with P.offline_model_loads(hub, specs, bound):
                    pcm = np.frombuffer(collector.data, dtype='<i2').reshape(-1, collector.channels)
                    for model_name in ('generic', 'quran'):
                        model = backend.configure(model_name)
                        text = canonical if model_name == 'generic' else backend.reference_text(canonical)
                        for start_ms in WINDOW_STARTS_MS:
                            for channel in range(collector.channels):
                                phase = 'inference'
                                window = pcm[start_ms*16:, channel].astype(np.float32)/32768.0
                                raw = list(backend.segment(window, [text]))
                                measured = P.raw_result(raw, ['63:11'], start_ms, backend.conf)
                                row = {'model': model_name, 'channel': f'native-{channel+1}',
                                    'alignmentModel': model, 'alignmentInput': [text],
                                    'windowMs': [start_ms, len(pcm)/16],
                                    'inputPcmSha256': hashlib.sha256(window.tobytes()).hexdigest(), **measured}
                                assess(row, target, contract)
                                report['measurements'].append(row)
                                F.S.emit({'candidateSha256': CANDIDATE_SHA,
                                    'sourceSha256': F.SOURCE['sha256'], 'qualityClaim': False,
                                    'provenance': report['provenance'], 'measurement': row}, 'PESHAWA_TAIL_DUAL_PART')
                        backend.clear()
                        gc.collect()
                F.S.verify_source(path, F.SOURCE)
        if F.S.sha_file(P.ROOT/CANDIDATE) != CANDIDATE_SHA:
            raise ValueError('candidate changed during measurement')
        if len(report['measurements']) != 2*2*collector.channels:
            raise ValueError('incomplete model/window/channel matrix')
        report['measurementComplete'] = True
        report['allTargetsWithinExistingThresholds'] = all(
            x['withinExistingTargetThresholds'] for x in report['measurements'])
        entries = [r['entries'][0] for r in report['measurements']]
        report['modelsChannelsAndWindowsAgree'] = (
            max(e['startMs'] for e in entries)-min(e['startMs'] for e in entries) <= contract.START_TOL
            and max(e['endMs'] for e in entries)-min(e['endMs'] for e in entries) <= contract.END_TOL)
    except Exception as exc:
        report['error'] = {'phase': phase, 'type': type(exc).__name__}
    finally:
        F.S.emit(report, 'PESHAWA_TAIL_DUAL_REPORT')
    return 0 if report['measurementComplete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
