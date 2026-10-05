"""Retry only a failed read-only QA review after diagnosis refresh.

Preserves the seven successful audio measurements, original run and commit.
Never retries audio jobs or changes candidates, reports, or production indexes.
"""
import argparse
import json
import hashlib
from pathlib import Path
import re
import subprocess
try:
    from .qa_recover_stalled import gh
except ImportError:
    from qa_recover_stalled import gh

REPO = 'mwqwf/rafiq-align-ci'
EXPECTED = {'plan', 'heard', 'quality openers', 'quality census',
            'quality rs1', 'quality rs2', 'quality rs3', 'quality rs4', 'review'}


def eligible(run, jobs, log, run_id, commit, key):
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        return False
    if not re.fullmatch(r'timings-staging/[a-z_]+/[a-z0-9_]+\.[0-9a-f]{8}\.jz', key):
        return False
    if (run.get('id') != run_id or run.get('head_sha') != commit
            or run.get('event') != 'workflow_dispatch'
            or run.get('path') != '.github/workflows/free-post-stage-quality.yml'
            or run.get('display_title') != 'free-post-stage ' + key
            or run.get('repository', {}).get('full_name') != REPO
            or run.get('repository', {}).get('private') is not False
            or run.get('status') != 'completed' or run.get('conclusion') != 'failure'
            or run.get('run_attempt') != 1):
        return False
    if len(jobs) != len(EXPECTED) or {j.get('name') for j in jobs} != EXPECTED:
        return False
    if any(j.get('status') != 'completed' or j.get('conclusion') !=
           ('failure' if j['name'] == 'review' else 'success') for j in jobs):
        return False
    return ('تشخيص الكتالوج يصف فهرساً آخر' in log
            and 'الحراس الأصلية لم تقبل أهلية الترقية' in log)


def witness_log(path, sha, run_id, commit, job_id):
    root = Path(__file__).resolve().parents[2]
    p = (root / path).resolve()
    if p.parent != root / 'ops/out' or p.suffix != '.json':
        raise ValueError('Failure witness must be a bounded local ops/out JSON')
    raw = p.read_bytes()
    if not re.fullmatch(r'[0-9a-f]{64}', sha) or hashlib.sha256(raw).hexdigest() != sha:
        raise ValueError('Failure witness digest mismatch')
    d = json.loads(raw)
    if (d.get('runId'), d.get('headSha'), d.get('reviewJobId'), d.get('repository')) != (run_id, commit, job_id, REPO):
        raise ValueError('Failure witness describes another job')
    if d.get('diagnosisRefreshConclusion') != 'success':
        raise ValueError('No completed diagnosis refresh')
    refreshed = gh(f"actions/runs/{int(d['diagnosisRefreshRun'])}")
    if refreshed.get('status') != 'completed' or refreshed.get('conclusion') != 'success' or refreshed.get('path') != '.github/workflows/diagnosis.yml':
        raise ValueError('Diagnosis refresh no longer verified')
    return d['recordedFailureLog']


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run', type=int, required=True)
    ap.add_argument('--commit', required=True)
    ap.add_argument('--key', required=True)
    ap.add_argument('--failure-witness')
    ap.add_argument('--witness-sha')
    a = ap.parse_args()
    run = gh(f'actions/runs/{a.run}')
    jobs = gh(f'actions/runs/{a.run}/jobs?filter=latest&per_page=100')['jobs']
    review = next((j for j in jobs if j.get('name') == 'review'), None)
    if review is None:
        raise ValueError('Missing review; no rerun')
    if a.failure_witness:
        log = witness_log(a.failure_witness, a.witness_sha or '', a.run, a.commit, review['id'])
    else:
        log = subprocess.run(['gh', 'api', f'repos/{REPO}/actions/jobs/{review["id"]}/logs'],
                             capture_output=True, text=True, check=True).stdout
    ok = eligible(run, jobs, log, a.run, a.commit, a.key)
    print(json.dumps({'run': a.run, 'job': review['id'], 'eligibleReviewOnly': ok}))
    if not ok:
        raise ValueError('Original public QA cycle no longer matches; no rerun')
    gh(f'actions/jobs/{review["id"]}/rerun', {'enable_debug_logging': False})
    print('Requested read-only review only; original audio evidence preserved')


if __name__ == '__main__':
    main()
