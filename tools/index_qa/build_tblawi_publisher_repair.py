"""Offline full Araf candidate from measured, explicitly declared publisher bytes."""
import copy,gzip,hashlib,json,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_registered_candidate as C
import stage_transform as T
import run as R
ROOT=Path(__file__).resolve().parents[2]
PARENT='3d4c52f080212f44ed7eb4861e15194843dd13997c9b253aa04db6bcd87871a2'
SOURCE='76b0d10dbb33d90cdbb98e71786653a497dbe73f7af704bf2297848ce1fbc547'
URL='https://www.nquran.com/audiof/quran/mohd_muh_tablawee/007.mp3'
TEMPLATE='https://www.nquran.com/audiof/quran/mohd_muh_tablawee/{s:03d}.mp3'
KEY='timings/hafs/tblawi.jz'
REPORT='ops/out/codex-tblawi7-nquran-recovery-20261006.json'
REPORT_SHA='d3911047369b537d662a28c3cc56bd6aa2f3d75f0e2473d1f650eba92a285622'
CONTEXT='ops/out/codex-tblawi-new-contexts-20261006.json'
CONTEXT_SHA='b1654d32b184481a0a5f85547704ec7a5db5eaf7e00118c75e0b2aa47c1e694c'

def checked(path,sha,z=False):
    b=(ROOT/path).read_bytes();C.require(hashlib.sha256(b).hexdigest()==sha,'changed evidence '+path)
    return json.loads(gzip.decompress(b) if z else b)

def main():
    pp='ops/source-repair/parents/codex-hafs-tblawi-3d4c52f0.jz'
    parent=checked(pp,PARENT,True)
    C.require(parent['reciterId']=='tblawi' and parent['riwaya']=='hafs' and len(parent['audioSha256'])==114,'parent identity')
    rep=checked(REPORT,REPORT_SHA);contexts=checked(CONTEXT,CONTEXT_SHA)
    metadata=checked('ops/out/codex-tblawi-nquran-metadata-37406467384.json','222a0abcea6e4ac6444eac886a4bcf00ca24a590f9cd3e6d883e04ee86002ed2')
    m=metadata['sources'][0]
    C.require(metadata['complete'] and m['ok'] and m['file']['sha256']==SOURCE and m['file']['finalUrl']==URL,'publisher bytes mismatch')
    C.require(m['identitySourceUrl']=='https://www.nquran.com/ar/view/10716' and m['riwaya']=='hafs' and m['surah']==7,'publisher identity mismatch')
    C.require(rep['measurementComplete'] and not rep['errors'] and rep['source']['sha256']==SOURCE and rep['source']['url']==URL,'recovery mismatch')
    a=copy.deepcopy(rep['alignment'])
    C.require(a['engine']=='ctc-quran-surah-1' and len(a['entries'])==206,'incomplete alignment')
    # Preserve the measured muqattaat duration warning; original QA still decides it.
    C.require(a['issues']==['مدة شاذة لآية 1: 11377م.ث لـ4 حرفاً'],'unexpected alignment issue')
    C.require({x['reader'] for x in contexts}=={'tblawi7_new_head','tblawi7_new_middle','tblawi7_new_tail'},'missing context')
    for ctx in contexts:
        C.require(ctx['measurementComplete'] and not ctx['errors'] and ctx['source']['sha256']==SOURCE and ctx['source']['url']==URL,'context source mismatch')
        C.require(ctx['audio']['decoded']['frames']==70049542 and ctx['audio']['decoded']['decodedWithoutErrors'],'decoded source mismatch')
        C.require({(x['model'],x['channel']) for x in ctx['freeResults']}=={(m,c) for m in ('generic','quran') for c in ('native-1','native-2')},'free measurement missing')
        C.require(all(not x['canonicalTextInput'] and not x['forcedAlignment'] and x['rawChunks'] for x in ctx['freeResults']),'forced presence evidence')
        for measurement in ctx['measurements']:
            for row in measurement['rawEntries']:
                n=int(row['ayahId'].split(':')[1]);expected=a['entries'][n-1]['startMs']
                C.require(abs(row['startMs']-expected)<1000,'context onset disagreement '+row['ayahId'])
    eof=70049542*1000//16000
    original_final=copy.deepcopy(a['entries'][-1]);a['entries'][-1]['endMs']=eof
    a.update(totalMs=eof,sha256=SOURCE,fileRef=URL)
    with tempfile.TemporaryDirectory() as td:
        td=Path(td);aligned=td/'aligned.json';aligned.write_text(json.dumps(a,ensure_ascii=False));out=td/'merged.jz'
        old=sys.argv;sys.argv=[C.splice_surah.__file__,'--index',str(ROOT/pp),'--surah','7','--aligned',str(aligned),'--url',TEMPLATE,'--engine-tag',a['engine'],'--alt-source','--out',str(out)]
        try:C.splice_surah.main()
        finally:sys.argv=old
        C.require(Path(str(out)+'.taken').read_text()=='7','incomplete splice')
        candidate=json.loads(gzip.decompress(out.read_bytes()))
    candidate['audioSha256'][6]=SOURCE
    outside=lambda rows:[e for e in rows if not e['ayahId'].startswith('7:')]
    C.require(outside(candidate['entries'])==outside(parent['entries']),'unrelated entries changed')
    expected=list(parent['audioSha256']);expected[6]=SOURCE
    C.require(candidate['audioSha256']==expected and candidate['sourceBySurah']['7']==TEMPLATE,'source declaration mismatch')
    rows=[e for e in candidate['entries'] if e['ayahId'].startswith('7:')]
    C.require(len(rows)==206 and all(e['fileRef']==URL and e['conf']==measured['conf'] for e,measured in zip(rows,a['entries'])),'confidence or source rewritten')
    C.require(all(e['startMs']==v['startMs'] and e['endMs']==v['endMs'] for e,v in zip(rows,a['entries'])),'unmeasured timing introduced')
    if 'lowCount' in candidate:candidate['lowCount']=sum(e.get('confBand')=='LOW' for e in candidate['entries'])
    moved,added,removed=T.entry_change_counts(parent['entries'],candidate['entries'])
    C.require(added==removed==0,'coverage changed')
    tr=C.repaired_transform(parent,candidate,[7],PARENT,KEY)
    proof={'qualityClaim':False,'sourceUrl':URL,'audioSha256':SOURCE,'publisherIdentityUrl':m['identitySourceUrl'],'reportPath':REPORT,'reportSha256':REPORT_SHA,'contextPath':CONTEXT,'contextSha256':CONTEXT_SHA,'decodedEofMs':eof,'originalFinalAlignment':original_final,'limits':['Publisher attribution and unforced model transcripts are preserved; no biometric reader certification claimed.','Full exact-SHA QA and independent heard/census remain mandatory.','All measured alignment confidences are retained; forced alignment alone is not coverage proof.']}
    tr.update(op='ctc_quran_surah_splice:7',fromSha256=PARENT,fromKey=KEY,entriesSha256=T.entries_sha(candidate['entries']),parentEntriesSha256=T.entries_sha(parent['entries']),movedEntries=moved,addedEntries=added,removedEntries=removed,by='build_tblawi_publisher_repair',reason='Full Araf measurement from healthy publisher audio with independent native contexts and decoded EOF',sourceRepair=proof,unpublishedLocalCandidate=True)
    proof['alignmentIssues']=copy.deepcopy(a['issues'])
    candidate['transform']=tr
    why=T.promote.index_gate(candidate,parent=parent,parent_sha=PARENT);C.require(not why,str(why))
    fatal,warnings,_=R.structural(candidate,KEY,False);C.require(not fatal,str(fatal));C.require('7' in T.promote.census_surahs(candidate),'census omitted changed source')
    path='ops/source-repair/candidates/codex-tblawi7-publisher-20261006.jz';b=gzip.compress(json.dumps(candidate,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode(),mtime=0)
    p=ROOT/path;C.require(not p.exists() or p.read_bytes()==b,'existing candidate differs');p.write_bytes(b)
    report=dict(path=path,sha256=hashlib.sha256(b).hexdigest(),parentKey=KEY,parentSha256=PARENT,op=tr['op'],changedEntries=moved,proof=proof,warnings=warnings)
    (ROOT/'ops/out/codex-tblawi7-publisher-candidate-20261006.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='proof'},ensure_ascii=False))

if __name__=='__main__':main()
