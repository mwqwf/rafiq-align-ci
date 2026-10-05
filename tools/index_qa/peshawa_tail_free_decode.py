#!/usr/bin/env python3
"""Free ASR of the repeated Peshawa 63 tail; no reference, alignment or adoption."""
import argparse
import array
import gc
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

SOURCE = {"surah": 63,
    "url": "https://download.quranicaudio.com/quran/peshawa_qadir_al-kurdi/mp3/063.mp3",
    "sha256": "bbfc9570680b5172ad15e417ce0ef5b8aaf8d15e16ec6f12fe46ea1752243301",
    "bytes": 2288268}
WINDOWS = ((188, 248), (244, 284))
MAX_SECONDS = 300


class NativeCollector:
    """Keep bounded native PCM, preserving channel order and every decoded frame."""
    def __init__(self, channels):
        if channels not in (1, 2):
            raise S.metadata.ProbeError("expected one or two native channels")
        self.channels = channels
        self.data = bytearray()

    def feed(self, block):
        if len(self.data) + len(block) > MAX_SECONDS * S.RATE * self.channels * 2:
            raise S.metadata.ProbeError("decoded source exceeded duration bound")
        self.data.extend(block)

    def finish(self):
        if not self.data or len(self.data) % (self.channels * 2):
            raise S.metadata.ProbeError("incomplete PCM frame")
        frames = len(self.data) // (self.channels * 2)
        if frames < WINDOWS[-1][1] * S.RATE:
            raise S.metadata.ProbeError("decoded source does not cover the planned tail")
        return {"nativeChannels": self.channels, "frames": frames,
                "durationSeconds": frames / S.RATE}

    def window(self, start, end):
        self.finish()
        if (start, end) not in WINDOWS:
            raise S.metadata.ProbeError("unplanned window")
        raw = self.data[start * S.RATE * self.channels * 2:end * S.RATE * self.channels * 2]
        values = array.array('h', raw)
        if sys.byteorder != 'little':
            values.byteswap()
        result = {}
        for i in range(self.channels):
            channel = values[i::self.channels]
            if sys.byteorder != 'little':
                channel.byteswap()
            result[f'native-{i + 1}'] = channel.tobytes()
        return result


def decode(path):
    S.verify_source(path, SOURCE)
    probe = subprocess.run(['ffprobe', '-v', 'error', '-protocol_whitelist', 'file,pipe',
        '-show_entries', 'format=duration:stream=codec_type,channels,sample_rate,channel_layout',
        '-of', 'json', str(path)], capture_output=True, timeout=20)
    if probe.returncode or probe.stderr:
        raise S.metadata.ProbeError('strict container probe failed')
    container = json.loads(probe.stdout)
    streams = [x for x in container['streams'] if x.get('codec_type') == 'audio']
    duration = float(container['format']['duration'])
    if len(streams) != 1 or not math.isfinite(duration) or not 0 < duration <= MAX_SECONDS:
        raise S.metadata.ProbeError('unexpected container')
    collector = NativeCollector(streams[0]['channels'])
    decoded = S.metadata._decode_pcm(path, collector, channel_arguments=[])
    S.verify_source(path, SOURCE)
    return collector, {"container": container, "decoded": decoded,
        "nativeChannelsUnmixed": True, "sourceUnchanged": True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-policy', choices=('cache-only', 'quran-pinned-ephemeral'), default='cache-only')
    args = parser.parse_args(argv)
    report = {"schema": 1, "kind": "peshawa-tail-free-asr", "ok": False,
        "qualityClaim": False, "productionChanged": False, "coverageCertified": False,
        "canonicalTextRead": False, "forcedAlignment": False, "source": SOURCE,
        "windowsSeconds": WINDOWS, "windowOverlapSeconds": 4,
        "limits": ["Fixed tail only; no verse presence or boundary certificate",
                   "Independent checkpoints share XLSR architecture",
                   "Raw frame timings are not certified verse timings"],
        "provenance": {"runId": os.environ.get('GITHUB_RUN_ID', ''),
                       "runSha": os.environ.get('GITHUB_SHA', ''),
                       "toolSha256": S.sha_file(__file__), "asrHelperSha256": S.sha_file(S.__file__),
                       "decoderHelperSha256": S.sha_file(S.metadata.__file__)},
        "models": [], "results": []}
    started = time.monotonic()
    phase = 'environment'
    try:
        if os.environ.get('CTC_INT8') != '0' or os.environ.get('CTC_THREADS') != '2':
            raise S.metadata.ProbeError('CPU float32 and two threads required')
        for key in ('HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE', 'HF_HUB_DISABLE_XET'):
            os.environ[key] = '1'
        report['versions'] = S.validate_versions()
        report['decoderVersion'] = S.metadata.decoder_version()
        phase = 'source'
        with tempfile.TemporaryDirectory(prefix='rafiq-peshawa-free-', dir=os.environ.get('RUNNER_TEMP')) as tmp:
            path = Path(tmp) / '063.mp3'
            report['download'] = S.metadata.fetch(SOURCE['url'], path, limit=4 * 1024 * 1024)
            collector, report['audio'] = decode(path)
            phase = 'models'
            with S.model_snapshots(args.model_policy) as (snapshots, inventory):
                report['modelAcquisition'] = inventory
                for spec in S.MODELS:
                    backend = S.FreeCTC(snapshots[spec['name']], spec)
                    report['models'].append({**spec, 'vocabulary': backend.vocabulary,
                        'files': S.model_files(snapshots[spec['name']], spec)})
                    S.emit({k: v for k, v in report.items() if k != 'results'}, 'PESHAWA_FREE_ASR_PROVENANCE')
                    phase = 'inference'
                    for start, end in WINDOWS:
                        for channel, raw in collector.window(start, end).items():
                            result = S.measure_window(backend, raw,
                                dict(SOURCE, windowSeconds=[start, end]), channel, spec['name'],
                                checkpoint=lambda part: S.emit(part, 'PESHAWA_FREE_ASR_PART'))
                            report['results'].append(result)
                    del backend
                    gc.collect()
                S.verify_source(path, SOURCE)
            if len(report['results']) != len(S.MODELS) * len(WINDOWS) * collector.channels:
                raise S.metadata.ProbeError('incomplete model/channel/window matrix')
            report['ok'] = True
    except Exception as exc:
        report['error'] = {'phase': phase, 'type': type(exc).__name__,
            'message': str(exc) if isinstance(exc, S.metadata.ProbeError) else 'measurement incomplete'}
    finally:
        report['elapsedSeconds'] = time.monotonic() - started
        S.emit(report, 'PESHAWA_FREE_ASR_REPORT')
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
