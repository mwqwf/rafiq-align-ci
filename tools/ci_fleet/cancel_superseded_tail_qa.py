"""Cancel explicitly pinned root-owned QA runs superseded by measured tail fixes.

Evidence stays in GitHub/R2. No other reader, run, stage, or live index changes.
"""
import json
from qa_recover_stalled import gh
REPO='mwqwf/rafiq-align-ci'
KEYS={
 37394065900:'timings-staging/hafs/darweez.249d793b.jz',
 37384770337:'timings-staging/warsh/derini_warsh.fd3b23b0.jz',
 37383854044:'timings-staging/warsh/derini_warsh.fd3b23b0.jz',
 37384779422:'timings-staging/hafs/f_khamery.d58b78bf.jz',
 37383866319:'timings-staging/hafs/f_khamery.d58b78bf.jz',
 37384833213:'timings-staging/hafs/zahrani.b962a19c.jz',
 37383912518:'timings-staging/hafs/zahrani.b962a19c.jz',
}


def eligible(run, ident):
    return (ident in KEYS and run.get('id')==ident
      and run.get('path')=='.github/workflows/free-post-stage-quality.yml'
      and run.get('display_title')=='free-post-stage '+KEYS[ident]
      and run.get('event')=='workflow_dispatch'
      and run.get('repository',{}).get('full_name')==REPO
      and run.get('repository',{}).get('private') is False
      and run.get('status') in ('queued','pending','waiting','in_progress'))


def main():
    for ident,key in KEYS.items():
        run=gh(f'actions/runs/{ident}')
        ok=eligible(run,ident)
        print(json.dumps({'run':ident,'key':key,'status':run.get('status'),'cancelSuperseded':ok,
          'reason':('Measured decoded EOF487131ms vs candidate487157ms; replacement47ef82a5 requires new full QA' if ident==37394065900 else 'Measured terminal clipping in 37388055996 and 37389928059; refined candidates require fresh final-SHA QA')}))
        if ok:gh(f'actions/runs/{ident}/cancel',{})
        elif run.get('status')!='completed':raise ValueError('Run identity changed; no cancellation')

if __name__=='__main__':main()
