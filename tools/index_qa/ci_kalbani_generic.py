"""Read-only float32 measurements for explicitly verified original Vorbis files.

No index, storage, artifact or cache writes. All raw actual contexts are emitted
to ordinary CI logs, including failed measurements. Acceptance remains in the
existing source, duration, model and exact-SHA audio gates.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools' / 'alignment_v3'))
import ci_spoken_census as W
import run as R
from common import load_text, load_index, surah_slice
from spoken_letters import alignment_text


def validated_plan(plan, sources, surah):
    if (plan.get('reciterId') != 'a_klb' or plan.get('riwaya') != 'hafs'
            or plan.get('canonicalTextChanged') is not False
            or plan.get('productionChanged') is not False):
        raise ValueError('Only read-only known Kalbani sources are eligible')
    requests = [x for x in plan['surahs'] if x['surah'] == surah]
    approved = [x for x in sources if x['surah'] == surah and x['accepted']]
    if len(requests) != 1 or len(approved) != 1:
        raise ValueError('Missing or duplicate source request')
    request, source = requests[0], approved[0]
    if (request['sourceSha256'] != source['sha256'] or request['sourceUrl'] != source['url']
            or source['sourceBytesChanged'] or source['locallyTranscoded']
            or source['decoderErrors'] or source['decodeRc'] != 0):
        raise ValueError('Unverified or changed publisher source')
    begin, end, _ = surah_slice(load_index(), surah)
    if not 1 <= len(request['windows']) <= 40:
        raise ValueError('Unbounded request')
    for win in request['windows']:
        lo, hi = win['range']; start, stop = win['windowMs']
        if not (1 <= lo <= hi <= end - begin and 0 <= start < stop <= source['nativeDurationMs']
                and stop - start <= 1200000):
            raise ValueError('Invalid canonical or physical context')
    return request, source


def native_pcm(path, expected_duration_ms):
    duration = R._file_duration_ms(path)
    pcm = R._full_decode_pcm(path)
    if abs(duration - expected_duration_ms) > 2 or abs(len(pcm) / 16 - duration) > 2:
        raise ValueError('Container/native physical duration differs')
    return pcm


def original_pcm(path, expected_frame_duration_ms):
    """Use the existing strict MP3 decoder and unchanged encoder-padding guard."""
    with open(path,'rb') as f:
        if f.read(4)==b'OggS':raise ValueError('Original MP3 mode cannot relax the Vorbis guard')
    duration=R._file_duration_ms(path)
    if abs(duration-expected_frame_duration_ms)>2:raise ValueError('Original MPEG frame duration changed')
    return R._full_decode_pcm(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--plan', required=True)
    ap.add_argument('--surah', type=int, required=True)
    a = ap.parse_args()
    path = ROOT / a.plan
    if (path.parent != ROOT / 'ops' / 'source-repair'
            or not path.name.startswith('kalbani-float-generic-plan-')
            or path.suffix != '.json' or os.environ.get('CTC_INT8') != '0'
            or os.environ.get('CTC_THREADS') != '2'
            or not os.environ.get('GITHUB_RUN_ID') or not os.environ.get('GITHUB_SHA')):
        raise ValueError('Explicit immutable CI float32 plan required')
    plan_bytes = path.read_bytes()
    plan=json.loads(plan_bytes);original=plan.get('original1435') is True
    proof='kalbani-1435-remaining-source-evidence-20261002.json' if original else 'kalbani-clean-vorbis-source-evidence-20261001.json'
    evidence = json.loads((ROOT / 'ops/source-repair' / proof).read_text())
    request, source = validated_plan(plan, evidence['sources'], a.surah)
    if original and (source['item']!='14352014_201801GGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGY' or source['metadataFile']['source']!='original' or a.surah not in (5,9,10,11)):
        raise ValueError('Only the explicit verified publisher original population is eligible')
    # This standalone probe never uses a mirror, credentials or product storage.
    R.LOCAL_CACHE = ROOT / 'scratch' / 'kalbani-generic-native'
    R.MIRROR.update(riwaya=None, reciter=None)
    R._mirror_url = lambda url: None
    native = Path(R._local_audio(source['url']))
    if hashlib.sha256(native.read_bytes()).hexdigest() != source['sha256']:
        raise ValueError('Whole original publisher SHA changed')
    if original:
        data=native.read_bytes()
        if len(data)!=int(source['metadataFile']['size']) or hashlib.md5(data).hexdigest()!=source['metadataFile']['md5']:raise ValueError('Publisher original MD5/size changed')
    pcm = original_pcm(native, source['nativeDurationMs']) if original else native_pcm(native, source['nativeDurationMs'])
    model = W.configure_generic()
    start, end, _ = surah_slice(load_index(), a.surah)
    refs = load_text('hafs')[start:end]
    provenance = {'source': 'ci', 'run_id': os.environ['GITHUB_RUN_ID'],
                  'run_sha': os.environ['GITHUB_SHA'],
                  'tool': 'tools/index_qa/ci_kalbani_generic.py',
                  'tool_sha': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  'plan_sha': hashlib.sha256(plan_bytes).hexdigest()}
    for win in request['windows']:
        lo, hi = win['range']; ws, we = win['windowMs']
        clip = pcm[ws * 16:we * 16]
        if len(clip) != (we - ws) * 16:
            raise ValueError('Incomplete native context')
        inputs = [alignment_text(a.surah, i, refs[i - 1]) for i in range(lo, hi + 1)]
        raw = W.C._segment(W.C._emissions(clip), len(clip), inputs)
        rows = [{'ayahIdx': i + lo - 1, 'startMs': ws + int(st * 1000),
                 'endMs': ws + int(en * 1000), 'conf': W.C._conf(score)}
                for i, (st, en, score) in enumerate(raw)]
        for i in range(len(rows) - 1):
            rows[i]['endMs'] = rows[i + 1]['startMs']
        measured = {'reciterId': 'a_klb', 'surah': a.surah, 'riwaya': 'hafs',
                    'range': [lo, hi], 'windowMs': [ws, we], 'sourceSha256': source['sha256'],
                    'alignmentModel': model, 'alignmentInput': inputs, 'entries': rows,
                    'canonicalTextChanged': False, 'runtime': {'precision': 'float32', 'threads': 2},
                    'provenance': provenance, 'accepted': False, 'durationBad': [], 'issues': []}
        print('KALBANI_GENERIC_WINDOW=' + json.dumps(measured, ensure_ascii=False), flush=True)
    print('KALBANI_GENERIC_COMPLETE=' + json.dumps({'surah': a.surah, 'windows': len(request['windows']),
          'sourceSha256': source['sha256'], 'nativeDurationMs': len(pcm) // 16, 'nativeFrameDurationMs':R._file_duration_ms(native),
          'provenance': provenance}), flush=True)


if __name__ == '__main__':
    main()
