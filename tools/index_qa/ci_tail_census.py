"""Measure known original Warsh 85:22 with two immutable float32 models.

Original Tiny row/report retained. Only the exact inconclusive source is
eligible; conditional writes cannot replace a concurrently changed report.
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
import ci_spoken_census as W
import promote as P
import run as R
from tail_census_witness import SOURCE_SHA, SOURCE_URL, CONTEXT_IDS, canonical_input, witness_error


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--key', required=True)
    ap.add_argument('--out', default='ops/out/spoken-census-witness.json')
    a = ap.parse_args()
    if (not a.key.startswith('timings-staging/warsh/laghdaf_shinqiti.')
            or a.key.count('/') != 2 or not a.key.endswith('.jz')
            or os.environ.get('CTC_INT8') != '0' or os.environ.get('CTC_THREADS') != '2'):
        raise ValueError('Explicit staged original-source key and bounded float32 runtime required')
    cl, bucket = P.s3()
    body = cl.get_object(Bucket=bucket, Key=a.key)['Body'].read()
    idx = json.loads(gzip.decompress(body)); sha = hashlib.sha256(body).hexdigest()
    if (idx['reciterId'] != 'laghdaf_shinqiti' or idx['riwaya'] != 'warsh'
            or idx['audioSha256'][84] != SOURCE_SHA or idx['sourceBySurah']['85'] != SOURCE_URL):
        raise ValueError('Only the fixed known original publisher source is eligible')
    state = 'state-census/' + a.key.replace('/', '_') + '.json'
    response = cl.get_object(Bucket=bucket, Key=state)
    original = response['Body'].read(); report = json.loads(original)
    if report.get('sha256') != sha or P.census_gate(cl, bucket, a.key, sha, idx):
        raise ValueError('Complete error-free exact-SHA census required')
    row = next(e for e in report['sample']['rows'] if e['aid'] == '85:22')
    if row['kind'] == 'بريء' and row.get('independentCanonicalTailCtc'):
        print(json.dumps({'key': a.key, 'sha256': sha, 'alreadyVerified': True})); return
    if row['kind'] != 'غير حاسم' or 'independentCanonicalTailCtc' in row:
        raise ValueError('Only an original inconclusive target may receive a witness')
    source = next(e['fileRef'] for e in idx['entries'] if e['ayahId'] == '85:22')
    if source != SOURCE_URL:
        raise ValueError('Wrong indexed file reference')
    path = ROOT / 'scratch' / 'canonical-tail-census' / (sha + '.ogg')
    path.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(urllib.request.Request(source, headers={'User-Agent': 'Mozilla/5.0'}), timeout=120) as audio:
        raw = audio.read()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA:
        raise ValueError('Original publisher audio changed')
    path.write_bytes(raw)
    pcm_all = R._full_decode_pcm(path)
    start = next(e['startMs'] for e in idx['entries'] if e['ayahId'] == '85:21')
    end = next(e['endMs'] for e in idx['entries'] if e['ayahId'] == '85:22') + 6000
    if end * 16 > len(pcm_all):
        raise ValueError('Original source lacks complete measured context')
    pcm = pcm_all[start * 16:end * 16]
    inputs = canonical_input(idx)
    proof = {'target': '85:22', 'sourceSha256': SOURCE_SHA, 'canonicalTextChanged': False,
             'contextAyahIds': CONTEXT_IDS, 'windowMs': [start, end], 'models': {},
             'runtime': {'precision': 'float32', 'threads': 2}}
    for name in ['generic', 'quran']:
        model = W.configure_generic() if name == 'generic' else W.Q.configure()
        actual_input = inputs if name == 'generic' else [W.Q.reference_text(t) for t in inputs]
        raw = W.C._segment(W.C._emissions(pcm), len(pcm), actual_input)
        entries = [{'ayahId': aid, 'startMs': start + int(st * 1000),
                    'endMs': start + int(en * 1000), 'conf': W.C._conf(score)}
                   for aid, (st, en, score) in zip(CONTEXT_IDS, raw)]
        for i in range(len(entries) - 1):
            entries[i]['endMs'] = entries[i + 1]['startMs']
        proof['models'][name] = {'alignmentModel': model, 'alignmentInput': actual_input, 'entries': entries}
        W.C._M.clear(); gc.collect()
    error = witness_error(proof, idx)
    proof['provenance'] = {'kind': 'audio', 'source': 'ci', 'run_id': os.environ['GITHUB_RUN_ID'],
                           'run_sha': os.environ['GITHUB_SHA'], 'tool': 'tools/index_qa/ci_tail_census.py',
                           'tool_sha': hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()}
    output = ROOT / a.out; output.parent.mkdir(parents=True, exist_ok=True)
    diagnostic = {'key': a.key, 'sha256': sha, 'proof': proof, 'validationError': error, 'productionChanged': False}
    output.write_text(json.dumps(diagnostic, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(diagnostic, ensure_ascii=False), flush=True)
    if error:
        raise ValueError(error)
    original_sha = hashlib.sha256(original).hexdigest()
    archive = 'state-census-original/' + a.key.replace('/', '_') + '/' + original_sha + '.json'
    try:
        archived = cl.get_object(Bucket=bucket, Key=archive)['Body'].read()
    except cl.exceptions.NoSuchKey:
        cl.put_object(Bucket=bucket, Key=archive, Body=original, ContentType='application/json', IfNoneMatch='*')
    else:
        if hashlib.sha256(archived).hexdigest() != original_sha:
            raise ValueError('Original census archive does not match unchanged bytes')
    row['originalTinyRow'] = copy.deepcopy(row)
    row['independentCanonicalTailCtc'] = proof
    row['kind'] = row['verdict'] = 'بريء'
    row['why'] = 'شاهدان صوتيان مستقلان فعليان على النص الأصلي85:22 وجارته وبسملة السورة التالية؛ المصدر والحدود والثقة والمدد مطابقة، ونتيجة Tiny غير الحاسمة محفوظة كاملة'
    report['independentCanonicalTailOriginal'] = {'key': archive, 'sha256': original_sha}
    report['ts'] = time.time()
    cl.put_object(Bucket=bucket, Key=state, Body=json.dumps(report, ensure_ascii=False).encode(),
                  ContentType='application/json', IfMatch=response['ETag'])
    diagnostic['originalReport'] = archive; diagnostic['verdict'] = 'بريء'
    output.write_text(json.dumps(diagnostic, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
