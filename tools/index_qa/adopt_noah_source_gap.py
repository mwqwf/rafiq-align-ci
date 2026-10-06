"""Adopt only the exact owner-authorized Qamar drop after its complete bound QA.

No general shrink switch is exposed. Original promote gates remain in force.
"""
import argparse,contextlib,io,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import noah_source_gap_quality as N
import post_stage_quality as Q
import heard_gate as H
import promote as P

QA_RUN='37405972254'
QA_COMMIT='c33da11fc39f71bb3ee159d9c66373130635cd93'

def validate_provenance(proof):
    N.require(proof.get('run_id')==QA_RUN and proof.get('commit')==QA_COMMIT,'not the bound complete QA cycle')
    intent=proof.get('intentionalDrop') or {}
    N.require((intent.get('key'),intent.get('sha256'),intent.get('parentSha256'),intent.get('surah'),intent.get('removedEntries'),intent.get('evidenceSha256'))==(N.KEY,N.SHA,N.PARENT,54,55,N.EVIDENCE_SHA),'missing intentional-drop QA binding')

def validate_all_reports(cl,bucket,idx):
    modified=cl.head_object(Bucket=bucket,Key=N.KEY)['LastModified'].timestamp()
    for check in ['openers','rs1','rs2','rs3','rs4']+(['census'] if P.census_surahs(idx) else []):
        rep=json.loads(cl.get_object(Bucket=bucket,Key=Q.state_key(N.KEY,check))['Body'].read())
        Q.validate_report(rep,N.KEY,N.SHA,idx,check);Q.validate_time(rep,check,modified)
        validate_provenance(rep.get('postStageProvenance') or {})
        N.require(not (rep.get('sample') or {}).get('errors'),'incomplete quality witness')
    rep=json.loads(cl.get_object(Bucket=bucket,Key=H.state_key(N.KEY))['Body'].read())
    validate_provenance(rep.get('provenance') or {});Q.validate_time(rep,'heard',modified)
    N.require(rep.get('measurementComplete') is True and not rep.get('measurementErrors') and rep.get('sha256')==N.SHA,'incomplete or stale heard witness')

def invoke(yes=False):
    old=sys.argv
    try:
        sys.argv=['promote.py','--only',N.KEY,'--allow-shrink',N.TARGET,'--reason',N.REASON,'--allow-truncated',N.REASON]+(['--yes'] if yes else [])
        P.main()
    finally:sys.argv=old

def adopt():
    cl,bucket,idx,parent=N.load_bound_candidate(N.KEY,N.SHA,N.PARENT)
    validate_all_reports(cl,bucket,idx)
    old_s3,old_frozen,old_reports=P.s3,P.load_frozen,P.REPORTS_CACHE
    try:
        records=Q.read_reports(cl,bucket,N.KEY)
        N.require(records and not any((r.get('sample') or {}).get('errors') for _,r in records if r.get('sha256')==N.SHA),'missing/incomplete original reports')
        P.REPORTS_CACHE=records
        def preview_frozen(client,bkt):
            frozen,body,etag=old_frozen(client,bkt)
            N.require(frozen.get(N.TARGET)==N.PARENT,'frozen parent changed')
            return {k:v for k,v in frozen.items() if k!=N.TARGET},body,etag
        output=io.StringIO()
        try:
            P.s3=lambda:(Q.ReadOnlyClient(cl),bucket);P.load_frozen=preview_frozen
            with contextlib.redirect_stdout(output):invoke()
        finally:P.s3,P.load_frozen=old_s3,old_frozen
        print(output.getvalue(),end='')
        N.require(f'✅ جاهز: {N.KEY} → {N.TARGET}' in output.getvalue(),'original promote gates rejected; production remains frozen')
        N.load_bound_candidate(N.KEY,N.SHA,N.PARENT);validate_all_reports(cl,bucket,idx)
        try:
            P.unfreeze(N.TARGET,N.REASON);invoke(yes=True)
        finally:
            actual=P.object_sha(cl,bucket,N.TARGET)[0];frozen,_,_=old_frozen(cl,bucket)
            if frozen.get(N.TARGET)!=actual:P.freeze(cl,bucket,N.TARGET,actual,'Refreeze after authorized source-gap adoption attempt')
        actual=P.object_sha(cl,bucket,N.TARGET)[0]
        manifest=json.loads(cl.get_object(Bucket=bucket,Key='timings/manifest.json')['Body'].read())
        rows=[r for r in manifest['indexes'] if (r.get('riwaya'),r.get('reciterId'))==('warsh','noah_warsh')]
        N.require(actual==N.SHA and old_frozen(cl,bucket)[0].get(N.TARGET)==N.SHA and len(rows)==1 and rows[0].get('sha256')==N.SHA,'publication/manifest/frozen mismatch')
        print(json.dumps(dict(productionKey=N.TARGET,sha256=N.SHA,entries=6181,wholeSurahDropped=54,missing=55,manifestVerified=True,frozenVerified=True,completionClaim=False)))
    finally:P.s3,P.load_frozen,P.REPORTS_CACHE=old_s3,old_frozen,old_reports

if __name__=='__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    adopt()
