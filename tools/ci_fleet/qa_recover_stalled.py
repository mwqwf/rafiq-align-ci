#!/usr/bin/env python3
"""Recover only manual QA runs stuck in dependency installation; never touch audio evidence."""
import argparse,datetime,json,subprocess
REPO='mwqwf/rafiq-align-ci'
ALLOWED={'.github/workflows/audio_qa.yml','.github/workflows/splice_census.yml'}
INSTALL='أدوات النظام'
def eligible(run,jobs,now):
 if run.get('event')!='workflow_dispatch' or run.get('path') not in ALLOWED or run.get('status')!='in_progress':return False
 active=[j for j in jobs if j.get('status')=='in_progress']
 if not active:return False
 for job in active:
  steps=[s for s in job.get('steps',[]) if s.get('status')=='in_progress']
  if len(steps)!=1 or steps[0].get('name')!=INSTALL:return False
  at=datetime.datetime.fromisoformat(steps[0]['started_at'].replace('Z','+00:00'))
  if (now-at).total_seconds()<1800:return False
 return True
def gh(path,body=None):
 cmd=['gh','api',f'repos/{REPO}/{path}']
 if body is not None:cmd+=['--method','POST','--input','-']
 cp=subprocess.run(cmd,input=json.dumps(body) if body is not None else None,text=True,capture_output=True,check=True)
 return json.loads(cp.stdout) if cp.stdout.strip() else None
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--runs',nargs='+',type=int,required=True);args=ap.parse_args()
 for ident in args.runs:
  run=gh(f'actions/runs/{ident}');jobs=gh(f'actions/runs/{ident}/jobs')['jobs'];ok=eligible(run,jobs,datetime.datetime.now(datetime.timezone.utc))
  print(json.dumps({'run':ident,'eligibleForCancellation':ok,'status':run['status'],'path':run['path']},ensure_ascii=False),flush=True)
  if ok:gh(f'actions/runs/{ident}/cancel',{});print('Cancelled dependency-stalled QA run',ident,flush=True)
if __name__=='__main__':main()
