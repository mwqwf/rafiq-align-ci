#!/usr/bin/env python3
"""Bounded, native-channel free ASR for sixteen repaired surah tails; no adoption."""
import argparse
import array
import gc
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import saad_free_decode as S

ROOT = Path(__file__).resolve().parents[2]
PLAN = 'ops/source-repair/codex-final-verse-free-asr-plan-20261005.json'
PLAN_SHA = 'a980398d1006f7237068ab983180b93e2d4116bbb2a71ddbefa9b1282117e3e9'
MAX_SOURCE_SECONDS = 7200
MAX_SOURCE_BYTES = 200 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise S.metadata.ProbeError(message)


def load_plan(group):
    raw = (ROOT/PLAN).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == PLAN_SHA, 'plan digest mismatch')
    plan = json.loads(raw)
    rows = plan['sources']
    require(group in (0, 1, 2) and len(rows) == 16 and plan['maxPerGroup'] == 6,
            'unexpected bounded population')
    require(len({r['id'] for r in rows}) == 16, 'duplicate source identity')
    selected = rows[group*6:(group+1)*6]
    for row in selected:
        path = (ROOT/row['candidatePath']).resolve()
        require(path.is_relative_to(ROOT/'ops/source-repair/candidates'), 'candidate outside allowed directory')
        require(S.sha_file(path) == row['candidateSha256'], 'candidate digest mismatch')
        idx = json.loads(gzip.decompress(path.read_bytes()))
        entries = [e for e in idx['entries'] if e['ayahId'].startswith(str(row['surah'])+':')]
        require(idx['reciterId'] == row['reciterId'] and idx['riwaya'] == row['riwaya']
                and idx['audioSha256'][row['surah']-1] == row['sha256']
                and entries[-1] == row['target'] and row['target']['fileRef'] == row['url'],
                'candidate target or source differs from plan')
        start, end = row['requestedWindowSeconds']
        require(type(start) is int and type(end) is int and 0 <= start < end <= MAX_SOURCE_SECONDS
                and end-start <= 70, 'window outside fixed bounds')
        S.metadata.validate_url(row['url'])
    return selected


class NativeWindow:
    def __init__(self, channels, start, end):
        require(channels in (1, 2), 'unsupported native channel count')
        require(type(start) is int and type(end) is int and 0 <= start < end <= MAX_SOURCE_SECONDS*S.RATE
                and end-start <= 70*S.RATE, 'invalid sample window')
        self.count, self.start, self.end = channels, start, end
        self.frames = 0
        self.pending = bytearray()
        self.window = bytearray()
        self.digest = hashlib.sha256()

    def feed(self, block):
        width = self.count*2
        require(self.frames*width+len(self.pending)+len(block) <= MAX_SOURCE_SECONDS*S.RATE*width,
                'decoded source exceeds bound')
        self.digest.update(block)
        self.pending.extend(block)
        size = len(self.pending)//width*width
        next_frame = self.frames+size//width
        lo, hi = max(self.start, self.frames), min(self.end, next_frame)
        if lo < hi:
            self.window.extend(self.pending[(lo-self.frames)*width:(hi-self.frames)*width])
        del self.pending[:size]
        self.frames = next_frame

    def finish(self):
        stop = min(self.frames, self.end)
        require(not self.pending and stop > self.start
                and len(self.window) == (stop-self.start)*self.count*2, 'missing or partial tail PCM')
        return {'frames': self.frames, 'nativeChannels': self.count,
                'durationSeconds': self.frames/S.RATE, 'fullNativePcmSha256': self.digest.hexdigest(),
                'windowStartSample': self.start, 'windowEndSampleExclusive': stop,
                'windowSamplesPerChannel': stop-self.start, 'requestedEndClampedToDecodedEof': self.end>self.frames}

    def channels(self):
        self.finish()
        values = array.array('h', self.window)
        if sys.byteorder != 'little':
            values.byteswap()
        result = {}
        for i in range(self.count):
            channel = values[i::self.count]
            if sys.byteorder != 'little':
                channel.byteswap()
            result[f'native-{i+1}'] = channel.tobytes()
        return result


def decode(path, source):
    require(S.sha_file(path) == source['sha256'], 'source SHA mismatch before decode')
    probe = subprocess.run(['ffprobe', '-v', 'error', '-protocol_whitelist', 'file,pipe',
        '-show_entries', 'format=duration:stream=codec_type,channels,sample_rate,channel_layout',
        '-of', 'json', str(path)], capture_output=True, timeout=20)
    require(probe.returncode == 0 and not probe.stderr, 'strict container probe failed')
    container = json.loads(probe.stdout)
    streams = [x for x in container['streams'] if x.get('codec_type') == 'audio']
    duration = float(container['format']['duration'])
    require(len(streams) == 1 and math.isfinite(duration) and 0 < duration <= MAX_SOURCE_SECONDS,
            'unexpected container')
    start, end = source['requestedWindowSeconds']
    collector = NativeWindow(streams[0]['channels'], start*S.RATE, end*S.RATE)
    decoded = S.metadata._decode_pcm(path, collector, channel_arguments=[])
    require(S.sha_file(path) == source['sha256'], 'source changed during decode')
    return collector, {'container': container, 'decoded': decoded, 'sourceUnchanged': True,
                       'nativeChannelsUnmixed': True, 'canonicalTextRead': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--group', type=int, choices=(0, 1, 2), required=True)
    parser.add_argument('--model-policy', choices=('cache-only', 'quran-pinned-ephemeral'), default='cache-only')
    args = parser.parse_args(argv)
    report = {'schema': 1, 'kind': 'final-verse-free-asr-batch', 'group': args.group,
        'measurementComplete': False, 'productionChanged': False, 'qualityClaim': False,
        'coverageCertified': False, 'canonicalTextRead': False, 'forcedAlignment': False,
        'planSha256': PLAN_SHA, 'sources': [], 'models': [], 'results': [], 'errors': [],
        'limits': ['Only planned tails; no automatic presence or boundary certificate',
                   'Models share XLSR architecture; channel agreement is not model independence',
                   'Qalun/Warsh evidence must be interpreted according to the declared riwaya',
                   'Candidate timings choose windows; gross shifts can leave the actual verse outside them'],
        'provenance': {'runId': os.environ.get('GITHUB_RUN_ID', ''),
            'runSha': os.environ.get('GITHUB_SHA', ''), 'toolSha256': S.sha_file(__file__),
            'asrHelperSha256': S.sha_file(S.__file__), 'decoderHelperSha256': S.sha_file(S.metadata.__file__)}}
    started = time.monotonic()
    phase = 'plan'
    try:
        sources = load_plan(args.group)
        report['requestedSources'] = sources
        require(os.environ.get('CTC_INT8') == '0' and os.environ.get('CTC_THREADS') == '2',
                'fixed float32/two-thread runtime required')
        report['versions'] = S.validate_versions()
        for key in ('HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE', 'HF_HUB_DISABLE_XET'):
            os.environ[key] = '1'
        windows = []
        phase = 'sources'
        with tempfile.TemporaryDirectory(prefix='rafiq-final-verses-', dir=os.environ.get('RUNNER_TEMP')) as tmp:
            for row in sources:
                path = Path(tmp)/(row['id']+'.mp3')
                try:
                    receipt = S.metadata.fetch(row['url'], path, limit=MAX_SOURCE_BYTES)
                    require(receipt['sha256'] == row['sha256'], 'download differs from pinned source')
                    collector, proof = decode(path, row)
                    actual = dict(row, windowSeconds=[collector.start/S.RATE,
                        min(collector.frames,collector.end)/S.RATE])
                    report['sources'].append({'id':row['id'],'download':receipt,**proof})
                    windows.append((actual,collector.channels()))
                except Exception as exc:
                    report['errors'].append({'source':row['id'],'phase':'source','type':type(exc).__name__})
                finally:
                    path.unlink(missing_ok=True)
            require(windows, 'no complete source window available')
            phase = 'models'
            with S.model_snapshots(args.model_policy) as (snapshots, inventory):
                report['modelAcquisition'] = inventory
                for spec in S.MODELS:
                    backend = S.FreeCTC(snapshots[spec['name']],spec)
                    report['models'].append({**spec,'vocabulary':backend.vocabulary,
                                            'files':S.model_files(snapshots[spec['name']],spec)})
                    S.emit({k:v for k,v in report.items() if k!='results'},'FINAL_VERSE_FREE_ASR_PROVENANCE')
                    phase = 'inference'
                    for source, channels in windows:
                        for name,raw in channels.items():
                            try:
                                result = S.measure_window(backend,raw,source,name,spec['name'],
                                    checkpoint=lambda part:S.emit(part,'FINAL_VERSE_FREE_ASR_PART'))
                                result['sourceId'] = source['id']
                                report['results'].append(result)
                            except Exception as exc:
                                report['errors'].append({'source':source['id'],'model':spec['name'],
                                    'channel':name,'phase':'inference','type':type(exc).__name__})
                    del backend
                    gc.collect()
            expected = 2*sum(len(channels) for source,channels in windows)
            require(len(report['results']) == expected, 'incomplete model/channel matrix')
            load_plan(args.group)  # Candidate inputs must still match after inference.
            report['measurementComplete'] = not report['errors'] and len(windows)==len(sources)
    except Exception as exc:
        report['errors'].append({'phase':phase,'type':type(exc).__name__})
    finally:
        report['elapsedSeconds'] = time.monotonic()-started
        S.emit(report,'FINAL_VERSE_FREE_ASR_REPORT')
    return 0 if report['measurementComplete'] else 1


if __name__=='__main__':
    raise SystemExit(main())
