"""Parallel complete census, with exact union of unchanged actual audio rows.

Parts are isolated by candidate SHA and workflow run. Only the collector can
write state-census; it rejects missing, duplicate or changed evidence. This
uses the existing audit, judge and final census gate without new thresholds.
"""
import argparse
import copy
import gzip
import hashlib
import json
import os
from pathlib import Path
import time

import ci_run
import promote as P
import run as R


def digest(body):
    return hashlib.sha256(body).hexdigest()


def prior_has_errors(prior):
    """True only for a report with untranscribed windows (sample.errors > 0)."""
    sample = prior.get('sample') if isinstance(prior, dict) else None
    n = (sample or {}).get('errors')
    return isinstance(n, int) and not isinstance(n, bool) and n > 0


def part_key(sha, run_id, surah):
    if (len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha)
            or not str(run_id).isdigit() or not 1 <= int(surah) <= 114):
        raise ValueError('Invalid immutable part identity')
    return f'state-census-parts/{sha}/{run_id}/{int(surah):03d}.json'


def row_ids(idx, surahs):
    return {e['ayahId'] for e in idx['entries']
            if int(e['ayahId'].split(':')[0]) in surahs and e.get('startMs') is not None}


def source_binding(idx, surah):
    rows = [e for e in idx['entries'] if e['ayahId'].startswith(f'{surah}:')]
    return {'audioSha256': idx['audioSha256'][surah - 1],
            'fileRefs': sorted({e['fileRef'] for e in rows})}


def aggregate(idx, sha, key, parts, run_id, run_sha, text, canonical_sha, tool_sha):
    expected = sorted(map(int, P.census_surahs(idx)))
    if len(parts) != len(expected):
        raise ValueError('Missing census part')
    seen, rows, fatal, warnings, openers, errors = set(), [], [], [], {}, {}
    model_sha = None
    provenance = []
    for part in parts:
        proof = part.get('partProvenance') or {}
        s = proof.get('surah')
        if s not in expected or s in seen:
            raise ValueError('Unexpected or duplicate part')
        seen.add(s)
        if (part.get('sha256') != sha or part.get('key') != key
                or part.get('kind') != 'splice-census-part' or part.get('source') != 'ci'
                or str(part.get('runId')) != str(run_id)
                or proof.get('runSha') != run_sha or proof.get('toolSha256') != tool_sha
                or proof.get('canonicalSha256') != canonical_sha
                or proof.get('sourceBinding') != source_binding(idx, s)
                or part.get('engine') != 'pywhispercpp/ggml-q8 (tiny-ar-quran)'
                or (part.get('census') or {}).get('surahs') != [s]):
            raise ValueError('Part provenance or source changed')
        ms = proof.get('modelSha256') or ''
        if len(ms) != 64 or (model_sha is not None and ms != model_sha):
            raise ValueError('Different audio measurement model')
        model_sha = ms
        sample = part.get('sample') or {}
        measured = sample.get('rows') or []
        wanted = row_ids(idx, {s})
        if (len(measured) != len(wanted) or {r.get('aid') for r in measured} != wanted
                or (part.get('census') or {}).get('population') != len(wanted)):
            raise ValueError('Incomplete or duplicated actual rows')
        nerr = sample.get('errors')
        if not isinstance(nerr, int) or nerr < 0:
            raise ValueError('Invalid error count')
        for row in measured:
            a = int(row['aid'].split(':')[1])
            if row.get('cluster') != s:
                raise ValueError('Row belongs to another surah')
            if row.get('verdict') == 'تعذّر':
                if row.get('kind') != 'غير حاسم' or not nerr:
                    raise ValueError('Unrecorded audio failure')
            else:
                heard = row.get('heard') or {}
                if set(heard) != {'fwd', 'dec', 'long'}:
                    raise ValueError('Missing actual audio transcript')
                prev = text[R.flat(s, a - 1)] if a > 1 else (R.BASMALA if s not in (1, 9) else '')
                v, k, why = R.judge(text[R.flat(s, a)], prev, heard['fwd'], heard['dec'], heard['long'],
                                    no_pre=bool(row.get('noPreAudio')))
                if (row.get('verdict'), row.get('kind'), row.get('why')) != (v, k, why):
                    raise ValueError('Actual transcript verdict changed')
            rows.append(copy.deepcopy(row))
        for f in part.get('fatal') or []:
            if f not in fatal:
                fatal.append(f)
        for w in part.get('warn') or []:
            if w not in warnings:
                warnings.append(w)
        for o in part.get('openers') or []:
            prior = openers.get(o['surah'])
            if prior is not None and prior != o:
                raise ValueError('Inconsistent duplicated opener measurements')
            openers[o['surah']] = copy.deepcopy(o)
        for window, why in (sample.get('errorWindows') or {}).items():
            errors[f'{s}/{window}'] = why
        provenance.append({'surah': s, 'key': part_key(sha, run_id, s),
                           'reportSha256': digest(json.dumps(part, ensure_ascii=False, sort_keys=True,
                                                            separators=(',', ':')).encode()),
                           'errors': nerr, 'population': len(measured)})
    if seen != set(expected) or len(rows) != len(row_ids(idx, set(expected))):
        raise ValueError('Incomplete whole census union')
    rows.sort(key=lambda r: tuple(map(int, r['aid'].split(':'))))
    rep = copy.deepcopy(parts[0])
    rep.pop('partProvenance', None)
    rep.update(kind='splice-census', fatal=fatal, warn=warnings,
               openers=[openers[s] for s in sorted(openers)], ts=time.time(),
               census={'surahs': expected, 'population': len(rows),
                       'note': 'Complete union of isolated actual audio census parts'},
               parallelCensus={'runId': str(run_id), 'runSha': run_sha,
                               'toolSha256': tool_sha, 'canonicalSha256': canonical_sha,
                               'modelSha256': model_sha, 'parts': provenance})
    by_cluster = {}
    for row in rows:
        if row['verdict'] != 'تعذّر':
            by_cluster.setdefault(row['cluster'], []).append(row['kind'])
    seed = int(hashlib.sha256(f'census/{expected}'.encode()).hexdigest()[:12], 16)
    rep = R._finish(rep, rows, by_cluster, seed, sum(p['errors'] for p in provenance))
    rep['sample']['errorWindows'] = errors
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--key', required=True)
    ap.add_argument('--expect-sha', required=True)
    ap.add_argument('--surah', type=int)
    ap.add_argument('--collect', action='store_true')
    a = ap.parse_args()
    if (not a.key.startswith('timings-staging/') or not a.key.endswith('.jz')
            or bool(a.surah) == bool(a.collect) or not os.environ.get('GITHUB_RUN_ID')
            or not os.environ.get('GITHUB_SHA')):
        raise ValueError('Explicit candidate and actual CI identity required')
    cl, bucket = ci_run._s3_from_env()
    R.s3 = lambda: (cl, bucket)
    idx, sha = R.fetch_index(a.key, a.expect_sha)
    expected = sorted(map(int, P.census_surahs(idx)))
    if not expected:
        raise ValueError('No source or engine surahs to census')
    run_id, run_sha = os.environ['GITHUB_RUN_ID'], os.environ['GITHUB_SHA']
    canonical = R.ASSETS / f"text_{idx['riwaya']}.jz"
    if not canonical.exists():
        canonical.parent.mkdir(parents=True, exist_ok=True)
        cl.download_file(bucket, f"quran-text/text_{idx['riwaya']}.jz", str(canonical))
    canonical_bytes = canonical.read_bytes()
    text = json.loads(gzip.decompress(canonical_bytes))
    if len(text) != 6236:
        raise ValueError('Incomplete canonical Quran reference')
    canonical_sha, tool_sha = digest(canonical_bytes), digest(Path(__file__).read_bytes())
    os.environ.update(QA_SEED_SALT='census', QA_SOURCE='ci', QA_RUN_ID=run_id)
    if a.collect:
        parts = [json.loads(cl.get_object(Bucket=bucket, Key=part_key(sha, run_id, s))['Body'].read())
                 for s in expected]
        rep = aggregate(idx, sha, a.key, parts, run_id, run_sha, text, canonical_sha, tool_sha)
        out = 'state-census/' + a.key.replace('/', '_') + '.json'
        # No successful or independently witnessed report may be overwritten.
        try:
            previous = cl.get_object(Bucket=bucket, Key=out)
        except cl.exceptions.NoSuchKey:
            condition = {'IfNoneMatch': '*'}
        else:
            prior = json.loads(previous['Body'].read())
            # A same-SHA report that could not transcribe some window is not a successful
            # report (promote refuses it); only that one may be replaced, by a complete union.
            if prior.get('sha256') == sha and not prior_has_errors(prior):
                raise ValueError('Exact-SHA complete census already exists; preserve it')
            condition = {'IfMatch': previous['ETag']}
    else:
        if a.surah not in expected:
            raise ValueError('Caller cannot choose an unrelated surah')
        model = Path(os.environ.get('QA_MODEL', '/tmp/ggml-q8.bin'))
        if not model.exists() or model.stat().st_size < 1_000_000:
            model.parent.mkdir(parents=True, exist_ok=True)
            cl.download_file(bucket, 'models/whisper-tiny-ar-quran/ggml-q8_0.bin', str(model))
        R.LOCAL_MODEL = model
        R.LOCAL_CACHE = Path(os.environ.get('QA_CACHE', '/tmp/qa_audio'))
        from pywhispercpp.model import Model
        R._LM = Model(str(model), language='ar', n_threads=2, print_progress=False,
                      print_realtime=False, print_timestamps=False)
        os.environ.update(QA_KIND='splice-census-part', QA_CENSUS_SURAHS=str(a.surah))
        args = argparse.Namespace(struct_only=False, allow_unmarked=True, local=True, rejudge=False,
                                  clusters=20, per_cluster=10, band=None, refined=None, long_seg=False,
                                  batch=48, threads=1, host=None, expect_sha=sha)
        rep = R.audit(a.key, args)
        rep['partProvenance'] = {'surah': a.surah, 'runSha': run_sha, 'toolSha256': tool_sha,
                                 'canonicalSha256': canonical_sha, 'modelSha256': digest(model.read_bytes()),
                                 'sourceBinding': source_binding(idx, a.surah)}
        out = part_key(sha, run_id, a.surah)
        condition = {'IfNoneMatch': '*'}
    # Re-read candidate after actual measurements, before publishing any result.
    R.fetch_index(a.key, sha)
    body = json.dumps(rep, ensure_ascii=False, indent=1).encode()
    cl.put_object(Bucket=bucket, Key=out, Body=body, ContentType='application/json', **condition)
    print(json.dumps({'key': out, 'sha256': sha, 'population': (rep.get('census') or {}).get('population'),
                      'verdict': rep.get('verdict'), 'errors': (rep.get('sample') or {}).get('errors')}))
    if a.collect:
        error = P.census_gate(cl, bucket, a.key, sha, idx)
        if error:
            raise ValueError(error)


if __name__ == '__main__':
    main()
