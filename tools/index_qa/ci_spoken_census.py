"""Add a measured dual-model witness to an otherwise complete census.

Only an inconclusive 20:1 in ctc-spoken-1 may be checked. No production writes.
The original report and row are retained; updates use an ETag precondition.
"""
import argparse
import copy
import gc
import gzip
import hashlib
import json
import os
import pathlib
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools' / 'alignment_v3'))
import ctc_seg as C
import quran_ctc_model as Q
from common import load_index, load_text, surah_slice, to_wav16k
from vad import read_wav
from spoken_letters import alignment_text
from spoken_census_witness import witness_error
from dual_ctc_model import GENERIC_ID, GENERIC_REVISION, GENERIC_WEIGHTS
import promote as P


def configure_generic():
    from huggingface_hub import snapshot_download
    snapshot = pathlib.Path(snapshot_download(GENERIC_ID, revision=GENERIC_REVISION,
                            allow_patterns=['*.json', 'pytorch_model.bin', 'README.md']))
    digest = hashlib.sha256()
    with (snapshot / 'pytorch_model.bin').open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(chunk)
    if digest.hexdigest() != GENERIC_WEIGHTS:
        raise ValueError('Generic model weight SHA differs from pinned source')
    C.MODEL_ID = str(snapshot)
    return {'id': GENERIC_ID, 'revision': GENERIC_REVISION,
            'weightsSha256': GENERIC_WEIGHTS, 'license': 'Apache-2.0'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--keys', required=True)
    parser.add_argument('--targeted-keys', default='',
                        help='Explicit subset: fixed 1s preroll and joined spoken letter names')
    parser.add_argument('--context-ayahs', type=int, choices=(3, 4, 5), default=3,
                        help='Complete canonical prefix, bounded by the measured candidate window')
    parser.add_argument('--out', default='ops/out/spoken-census-witness.json')
    args = parser.parse_args()
    keys = [k for k in args.keys.replace(',', ' ').split() if k]
    targeted = set(args.targeted_keys.replace(',', ' ').split())
    if not 1 <= len(keys) <= 3 or len(set(keys)) != len(keys):
        raise ValueError('One to three unique explicitly selected candidate keys required')
    if not targeted <= set(keys) or os.environ.get('CTC_INT8') != '0':
        raise ValueError('Explicit selected targets and original float32 model inference required')
    cl, bucket = P.s3()
    jobs = []
    receipts = []
    for key in keys:
        if not key.startswith('timings-staging/') or key.count('/') != 2:
            raise ValueError('Staging keys only')
        body = cl.get_object(Bucket=bucket, Key=key)['Body'].read()
        idx = json.loads(gzip.decompress(body))
        sha = hashlib.sha256(body).hexdigest()
        census_key = 'state-census/' + key.replace('/', '_') + '.json'
        response = cl.get_object(Bucket=bucket, Key=census_key)
        original = response['Body'].read()
        report = json.loads(original)
        if report.get('sha256') != sha or P.census_gate(cl, bucket, key, sha, idx):
            raise ValueError('Complete error-free census on this exact SHA required')
        row = next(r for r in report['sample']['rows'] if r['aid'] == '20:1')
        if row['kind'] == 'بريء' and row.get('independentSpokenCtc'):
            receipts.append({'key': key, 'sha256': sha, 'target': '20:1',
                             'verdict': 'بريء', 'alreadyVerified': True, 'productionChanged': False})
            continue
        if row['kind'] != 'غير حاسم' or 'independentSpokenCtc' in row:
            raise ValueError('Only an original inconclusive target can receive a new witness')
        ev = idx['alignmentWindowEvidenceBySurah']['20']
        if ev['range'][0] != 1 or not 3 <= ev['range'][1] <= 5 or ev['windowMs'][0] != 0:
            raise ValueError('Known prefix window only')
        if args.context_ayahs > ev['range'][1]:
            raise ValueError('Context exceeds candidate measured prefix')
        source = next(e['fileRef'] for e in idx['entries'] if e['ayahId'] == '20:1')
        path = ROOT / 'scratch' / 'spoken-census' / (sha + '.mp3')
        path.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(urllib.request.Request(source, headers={'User-Agent': 'Mozilla/5.0'}),
                                    timeout=120) as audio:
            raw = audio.read()
        if hashlib.sha256(raw).hexdigest() != idx['audioSha256'][19]:
            raise ValueError('Original audio differs from indexed source SHA')
        path.write_bytes(raw)
        wav = to_wav16k(str(path))
        # A complete bounded prefix supplies canonical neighbours.
        # Its end is measured in the candidate, never chosen from model scores.
        prefix_end = next(e['endMs'] for e in idx['entries']
                          if e['ayahId'] == f'20:{args.context_ayahs}')
        target_start = next(e['startMs'] for e in idx['entries'] if e['ayahId'] == '20:1')
        prefix_start = max(0, target_start - 1000) if key in targeted else 0
        pcm = read_wav(wav)[prefix_start * 16:prefix_end * 16]
        start, end, _ = surah_slice(load_index(), 20)
        refs = load_text(idx['riwaya'])[start:end]
        inputs = ['بسم الله الرحمن الرحيم'] + [alignment_text(20, i, refs[i - 1])
                   for i in range(1, args.context_ayahs + 1)]
        if key in targeted:
            inputs = inputs[1:]
            inputs[0] = inputs[0].replace(' ', '')
        proof = {'target': '20:1', 'sourceSha256': idx['audioSha256'][19],
                 'canonicalTextChanged': False, 'models': {}, 'range': [1, args.context_ayahs],
                 'windowMs': [prefix_start, prefix_end],
                 'context': 'targeted-joined' if key in targeted else 'full-prefix',
                 'runtime': {'precision': 'float32', 'threads': int(os.environ['CTC_THREADS'])}}
        jobs.append({'key': key, 'idx': idx, 'censusKey': census_key, 'etag': response['ETag'],
                     'report': report, 'original': original, 'row': row,
                     'pcm': pcm, 'inputs': inputs, 'proof': proof})
    for name in (('generic', 'quran') if jobs else ()):
        model = configure_generic() if name == 'generic' else Q.configure()
        for job in jobs:
            inputs = job['inputs'] if name == 'generic' else [Q.reference_text(t) for t in job['inputs']]
            raw = C._segment(C._emissions(job['pcm']), len(job['pcm']), inputs)
            if job['proof']['context'] == 'full-prefix':
                raw = raw[1:]
            offset = job['proof']['windowMs'][0]
            entries = [{'ayahIdx': i, 'startMs': offset + int(st * 1000), 'endMs': offset + int(en * 1000),
                        'conf': C._conf(score)} for i, (st, en, score) in enumerate(raw)]
            for i in range(len(entries) - 1):
                entries[i]['endMs'] = entries[i + 1]['startMs']
            job['proof']['models'][name] = {'alignmentModel': model,
                                          'alignmentInput': inputs, 'entries': entries}
        C._M.clear()
        gc.collect()
    provenance = {'kind': 'audio', 'source': 'ci', 'run_id': os.environ['GITHUB_RUN_ID'],
                  'run_sha': os.environ['GITHUB_SHA'], 'tool': 'tools/index_qa/ci_spoken_census.py',
                  'tool_sha': hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()}
    output = ROOT / args.out
    output.parent.mkdir(parents=True, exist_ok=True)
    diagnostics = []
    for job in jobs:
        error = witness_error(job['proof'], job['idx'])
        job['proof']['provenance'] = provenance
        diagnostics.append({'key': job['key'], 'proof': job['proof'],
                            'validationError': error, 'productionChanged': False})
    # Preserve actual raw measurements even when any witness is rejected.
    output.write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(diagnostics, ensure_ascii=False), flush=True)
    if any(d['validationError'] for d in diagnostics):
        raise ValueError('Independent witness rejected; diagnostics saved, census unchanged')
    for job in jobs:
        original_sha = hashlib.sha256(job['original']).hexdigest()
        archive = 'state-census-original/' + job['key'].replace('/', '_') + '/' + original_sha + '.json'
        try:
            archived = cl.get_object(Bucket=bucket, Key=archive)['Body'].read()
        except cl.exceptions.NoSuchKey:
            cl.put_object(Bucket=bucket, Key=archive, Body=job['original'],
                          ContentType='application/json', IfNoneMatch='*')
        else:
            if hashlib.sha256(archived).hexdigest() != original_sha:
                raise ValueError('Original archive does not match unchanged census bytes')
        row = job['row']
        row['originalTinyRow'] = copy.deepcopy(row)
        row['independentSpokenCtc'] = job['proof']
        row['kind'] = row['verdict'] = 'بريء'
        row['why'] = 'طه: شاهدان صوتيان مستقلان بنموذجين ثابتين يطابقان الحروف المنطوقة والنص الأصلي وحدود النسخة؛ نتيجة Tiny غير الحاسمة محفوظة كاملة'
        job['report']['ts'] = time.time()
        job['report']['independentSpokenCtcOriginal'] = {'key': archive, 'sha256': original_sha}
        data = json.dumps(job['report'], ensure_ascii=False).encode()
        cl.put_object(Bucket=bucket, Key=job['censusKey'], Body=data,
                      ContentType='application/json', IfMatch=job['etag'])
        receipts.append({'key': job['key'], 'sha256': job['report']['sha256'],
                         'target': '20:1', 'verdict': 'بريء', 'proof': job['proof'],
                         'originalReport': archive, 'productionChanged': False})
    output.write_text(json.dumps(receipts, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(receipts, ensure_ascii=False))


if __name__ == '__main__':
    main()
