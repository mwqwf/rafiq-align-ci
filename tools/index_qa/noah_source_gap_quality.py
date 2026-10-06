"""Dedicated, exact-byte QA for the owner-authorized whole Qamar source-gap drop.

The general non-dropping post_stage_guard remains unchanged. This entry point
accepts one immutable drop, proves every surviving entry is identical, and runs
the existing complete quality/heard/census gates. It never publishes an index.
"""
import argparse,copy,gzip,hashlib,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
from post_stage_guard import require
KEY='timings-staging/warsh/noah_warsh.b99262ae.jz'
SHA='b99262ae6b1b13592a29025d3cfc9760029a2e0c13769768808459e5f3f51437'
TARGET='timings/warsh/noah_warsh.jz'
PARENT='17191c80f66c87db6f31f8bea091ab8f2e526083e8e4bc6a318aefe42b44a029'
SOURCE='1d5b8df34dee1fa57181b61c9fe081cff3279295fb68690f205970fb7ce1a977'
EVIDENCE='ops/out/codex-duration-context-37392377734-reports.json'
EVIDENCE_SHA='7fbc87cb7170153cfc0aa54c699c4e04ed168611faf3411b4f800e197410dc6d'
REASON='Owner-directed whole-surah removal for the measured middle source gap54:16/17; all surviving entries unchanged.'

def validate_documents(idx,parent):
    for d in (idx,parent):
        require((d.get('riwaya'),d.get('reciterId'))==('warsh','noah_warsh'),'wrong source identity')
    require(len(parent['entries'])==6236 and not parent.get('missing',{}).get('count'),'unexpected parent coverage')
    dropped=[e for e in parent['entries'] if e['ayahId'].startswith('54:')]
    require({e['ayahId'] for e in dropped}=={f'54:{a}' for a in range(1,56)} and len(dropped)==55,'parent lacks whole surah')
    require(idx['entries']==[e for e in parent['entries'] if not e['ayahId'].startswith('54:')],'surviving entries changed or partial drop')
    require(len(idx['entries'])==6181,'unexpected surviving count')
    miss=idx.get('missing') or {}
    require(miss.get('count')==55 and miss.get('ids')==[f'54:{a}' for a in range(1,56)],'wrong absence declaration')
    require(miss.get('byReason')=={'unknown':0,'source_truncated':55},'incorrect absence reason')
    tx=idx.get('transform') or {}
    require((tx.get('op'),tx.get('fromKey'),tx.get('fromSha256'),tx.get('droppedEntries'),tx.get('reasonCode'))==('drop_surah:54',TARGET,PARENT,55,'SOURCE_TRUNCATED'),'wrong explicit drop intent')
    require(tx.get('reasonUser') and tx.get('reason'),'missing user-facing source-gap explanation')
    require(idx.get('lowCount')==sum(e.get('confBand')=='LOW' for e in idx['entries']),'LOW count mismatch')
    expected={k:v for k,v in parent.get('engineBySurah',{}).items() if k!='54'}
    require(idx.get('engineBySurah')==expected,'unrelated engine declaration changed')
    allowed={'entries','missing','transform','lowCount','engineBySurah'}
    require({k:v for k,v in parent.items() if k not in allowed}=={k:v for k,v in idx.items() if k not in allowed},'unrelated header/source changed')
    require(parent['audioSha256'][53]==SOURCE,'source identity changed')

def validate_evidence(parent):
    b=(ROOT/EVIDENCE).read_bytes();require(hashlib.sha256(b).hexdigest()==EVIDENCE_SHA,'source evidence changed')
    rep=next(r for r in json.loads(b) if r.get('reader')=='noah_warsh')
    require(rep['measurementComplete'] and not rep['errors'],'incomplete source evidence')
    source=rep['source']
    require(source['parentSha256']==PARENT and source['sha256']==SOURCE and source['surah']==54 and source['riwaya']=='warsh','evidence identity mismatch')
    byid={e['ayahId']:e for e in parent['entries']}
    require(source['contextEntries']==[byid[f'54:{a}'] for a in range(13,21)],'source-gap context changed')
    free=rep['freeResults']
    require({(m['model'],m['channel']) for m in free}=={('generic','native-1'),('quran','native-1')},'missing independent free measurements')
    require(all(not m['canonicalTextInput'] and not m['forcedAlignment'] and m['rawChunks'] for m in free),'invalid free evidence')
    require(rep['audio']['decoded']['decodedWithoutErrors'],'source did not decode cleanly')

def validate_binding(key,sha,parent_sha,blob,parent_blob):
    require((key,sha,parent_sha)==(KEY,SHA,PARENT),'this guard only accepts the explicitly bound source-gap drop')
    require(hashlib.sha256(blob).hexdigest()==SHA and hashlib.sha256(parent_blob).hexdigest()==PARENT,'changed live bytes')
    idx,parent=json.loads(gzip.decompress(blob)),json.loads(gzip.decompress(parent_blob))
    validate_documents(idx,parent)
    return idx,parent

def load_bound_candidate(key,sha,parent_sha):
    require((key,sha,parent_sha)==(KEY,SHA,PARENT),'this guard only accepts the explicitly bound source-gap drop')
    import promote as P
    import run as R
    from quran_ctc_model import records_error
    cl,bucket=P.s3();blob=cl.get_object(Bucket=bucket,Key=key)['Body'].read();pb=cl.get_object(Bucket=bucket,Key=TARGET)['Body'].read()
    idx,parent=validate_binding(key,sha,parent_sha,blob,pb);validate_evidence(parent)
    require(P.load_frozen(cl,bucket)[0].get(TARGET)==PARENT,'parent not frozen on expected bytes')
    for why in (records_error(idx),P.index_gate(idx,parent=parent,parent_sha=PARENT),P.catalog_gate(idx,P.catalog(cl,bucket))):
        require(not why,'original index guard: '+str(why))
    canonical=json.loads(gzip.decompress((R.ASSETS/'text_warsh.jz').read_bytes()));require(len(canonical)==6236,'canonical reference missing')
    fatal,_,_=R.structural(idx,KEY,allow_unmarked=False,txt_ref=canonical);require(not fatal,'original structural guard: '+str(fatal))
    return cl,bucket,idx,parent

def bound_provenance(original):
    def result():
        p=original();p['intentionalDrop']={'key':KEY,'sha256':SHA,'parentSha256':PARENT,'surah':54,'removedEntries':55,'evidencePath':EVIDENCE,'evidenceSha256':EVIDENCE_SHA}
        p['toolSha256']['tools/index_qa/noah_source_gap_quality.py']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        return p
    return result

def main(argv=None):
    ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['plan','quality','heard'],required=True)
    mode,rest=ap.parse_known_args(argv)
    if mode.mode=='plan':
        p=argparse.ArgumentParser();p.add_argument('--key',required=True);p.add_argument('--sha',required=True);p.add_argument('--parent-sha',required=True);a=p.parse_args(rest)
        _,_,idx,_=load_bound_candidate(a.key,a.sha,a.parent_sha)
        print(json.dumps({'key':KEY,'sha256':SHA,'survivingEntriesUnchanged':True,'entries':len(idx['entries']),'wholeSurahDropped':54,'productionChanged':False}));return 0
    if mode.mode=='heard':
        import post_stage_heard as H
        H.load_bound_candidate=load_bound_candidate;H.ci_provenance=bound_provenance(H.ci_provenance)
        old=sys.argv
        try:sys.argv=[H.__file__,*rest];return H.main()
        finally:sys.argv=old
    import post_stage_quality as Q
    import promote as P
    Q.load_bound_candidate=load_bound_candidate;Q.provenance=bound_provenance(Q.provenance)
    original=P.main
    def preview_with_authorized_scope():
        # review supplies a read-only client; only the existing explicit drop flags are added.
        old=sys.argv
        try:
            require('--yes' not in old,'QA cannot publish')
            sys.argv=[*old,'--allow-truncated',REASON,'--allow-shrink',TARGET,'--reason',REASON]
            return original()
        finally:sys.argv=old
    P.main=preview_with_authorized_scope
    try:return Q.main(rest)
    finally:P.main=original

if __name__=='__main__':raise SystemExit(main())
