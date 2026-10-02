"""Immutable public census identity plan; job outputs contain only numeric IDs.

Exact source SHA, run and producer remain mandatory. No credential is stored
in this plan, and the existing parts/union audio gates perform all judgments.
"""
import argparse,hashlib,json,os,re,subprocess,sys
from pathlib import Path
import ci_run

def plan_key(run_id):
    if not str(run_id).isdigit():raise ValueError('Actual numeric CI run required')
    return f'state-census-plans/{run_id}/plan.json'

def make_plan(candidates,run_id,run_sha):
    d={'kind':'immutable-census-plan','runId':str(run_id),'runSha':run_sha,
       'toolSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'candidates':candidates}
    validate_plan(d,run_id,run_sha);return d

def validate_plan(d,run_id,run_sha):
    plan_key(run_id)
    if (d.get('kind')!='immutable-census-plan' or d.get('runId')!=str(run_id) or d.get('runSha')!=run_sha
            or not re.fullmatch('[0-9a-f]{40}',run_sha or '')
            or d.get('toolSha256')!=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()):
        raise ValueError('Census plan belongs to another actual run or producer')
    rows=d.get('candidates');seen=set()
    if not isinstance(rows,list):raise ValueError('Invalid census candidate population')
    for row in rows:
        if (set(row)!={'key','sha','surahs'} or not row['key'].startswith('timings-staging/')
                or not row['key'].endswith('.jz') or row['key'] in seen
                or not re.fullmatch('[0-9a-f]{64}',row['sha']) or not row['surahs']
                or any(type(s) is not int or not 1<=s<=114 for s in row['surahs'])
                or row['surahs']!=sorted(set(row['surahs']))):
            raise ValueError('Changed, duplicate or unbounded census identity')
        seen.add(row['key'])
    return d

def write_plan(cl,bucket,candidates,run_id,run_sha):
    d=make_plan(candidates,run_id,run_sha)
    cl.put_object(Bucket=bucket,Key=plan_key(run_id),Body=json.dumps(d).encode(),
                  ContentType='application/json',IfNoneMatch='*')
    return d

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--candidate',type=int,required=True);ap.add_argument('--surah',type=int);ap.add_argument('--collect',action='store_true');a=ap.parse_args()
    if bool(a.surah)==bool(a.collect):raise ValueError('One complete part or complete union required')
    run_id,run_sha=os.environ.get('GITHUB_RUN_ID'),os.environ.get('GITHUB_SHA');cl,bucket=ci_run._s3_from_env()
    d=validate_plan(json.loads(cl.get_object(Bucket=bucket,Key=plan_key(run_id))['Body'].read()),run_id,run_sha)
    if not 0<=a.candidate<len(d['candidates']):raise ValueError('Unexpected candidate ID')
    row=d['candidates'][a.candidate]
    if a.surah and a.surah not in row['surahs']:raise ValueError('Unexpected part outside complete population')
    args=[sys.executable,str(Path(__file__).with_name('ci_census_parts.py')),'--key',row['key'],'--expect-sha',row['sha']]
    args+=['--collect'] if a.collect else ['--surah',str(a.surah)]
    subprocess.run(args,check=True)
if __name__=='__main__':main()
