"""Build a source-bound Fatiha candidate from complete native-channel measurements."""
import copy,gzip,hashlib,json,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_registered_candidate as C
import stage_transform as T
import run as R
ROOT=Path(__file__).resolve().parents[2]
PARENT='3a5804507f4f2a2cb66d0f873e38fc27b3506b8e7547a10fce5dc721f583e2a4'
SOURCE='a9a743e67cbae4e241744847e18fbac55c77090e5cbc8a4144dba78a412a5924'
URL='https://www.nquran.com/audiof/quran/Sh_%20shatri/001.mp3'
TEMPLATE='https://www.nquran.com/audiof/quran/Sh_%20shatri/{s:03d}.mp3'
KEY='timings/hafs/obk.jz'
REPORT='ops/out/codex-obk-full-context-20261006.json'
REPORT_SHA='03fcc833f7992ea44ff66da4f58d5c43afe4d7942095731d7393e495e223c3cf'

def checked(path,sha,z=False):
    b=(ROOT/path).read_bytes();C.require(hashlib.sha256(b).hexdigest()==sha,'changed evidence '+path)
    return json.loads(gzip.decompress(b) if z else b)

def main():
    pp='ops/source-repair/parents/codex-hafs-obk-3a580450.jz'
    parent=checked(pp,PARENT,True);rep=checked(REPORT,REPORT_SHA)
    checked('ops/out/codex-obk-full-context-complete-20261006.json.gz','69c4b9a9df41b37d84da305d17a1bc0e20c6e39c6f574d3c67b220e70299372c',True)
    md=checked('ops/out/codex-obk-nquran-metadata-37408270942.json','8eadcd3b647d1927482f883eb849b1fa029c0213990ecadfacad51a229a1181b')
    m=md['sources'][0]
    C.require(parent['reciterId']=='obk' and parent['riwaya']=='hafs' and len(parent['audioSha256'])==114,'parent identity')
    C.require(md['complete'] and m['ok'] and m['file']['sha256']==SOURCE and m['file']['finalUrl']==URL and m['identitySourceUrl']=='https://www.nquran.com/ar/view/3870','publisher identity')
    C.require(rep['measurementComplete'] and not rep['errors'] and rep['source']['sha256']==SOURCE and rep['source']['url']==URL and rep['source']['surah']==1 and rep['source']['riwaya']=='hafs','context identity')
    dec=rep['audio']['decoded'];C.require(dec['decodedWithoutErrors'] and dec['frames']==992653 and dec['windowStartSample']==0 and dec['windowEndSampleExclusive']==992653,'incomplete source window')
    pairs={(model,channel) for model in ('generic','quran') for channel in ('native-1','native-2')}
    C.require({(v['model'],v['channel']) for v in rep['freeResults']}==pairs and all(not v['canonicalTextInput'] and not v['forcedAlignment'] and v['rawChunks'] for v in rep['freeResults']),'missing unforced evidence')
    C.require({(v['model'],v['channel']) for v in rep['measurements']}==pairs,'missing independent contexts')
    selected=next(v for v in rep['measurements'] if (v['model'],v['channel'])==('quran','native-1'))
    C.require([v['ayahId'] for v in selected['entries']]==[f'1:{i}' for i in range(1,8)],'incomplete canonical population')
    for measurement in rep['measurements']:
        C.require(len(measurement['rawEntries'])==7,'incomplete independent context')
        for i,row in enumerate(measurement['rawEntries']):
            C.require(row['ayahId']==f'1:{i+1}' and abs(row['startMs']-selected['entries'][i]['startMs'])<1000,'model onset disagreement')
        C.require(measurement['rawEntries'][0]['startMs']==7427 and measurement['rawEntries'][-1]['endMs']==59488,'opening/tail evidence changed')
    eof=992653*1000//16000
    model=copy.deepcopy(selected['alignmentModel']);model['canonicalTextChanged']=False
    entries=[dict(ayahIdx=i,startMs=e['startMs'],endMs=eof if i==6 else e['endMs'],conf=e['conf'],snapped=False) for i,e in enumerate(selected['entries'])]
    a=dict(surah=1,riwaya='hafs',totalMs=eof,entries=entries,engine='ctc-quran-window-1',alignmentModel=model,sha256=SOURCE,fileRef=URL)
    with tempfile.TemporaryDirectory() as td:
        td=Path(td);aligned=td/'aligned.json';aligned.write_text(json.dumps(a,ensure_ascii=False));out=td/'merged.jz'
        old=sys.argv;sys.argv=[C.splice_surah.__file__,'--index',str(ROOT/pp),'--surah','1','--aligned',str(aligned),'--url',TEMPLATE,'--engine-tag',a['engine'],'--alt-source','--out',str(out)]
        try:C.splice_surah.main()
        finally:sys.argv=old
        C.require(Path(str(out)+'.taken').read_text()=='1','incomplete splice');candidate=json.loads(gzip.decompress(out.read_bytes()))
    candidate['audioSha256'][0]=SOURCE
    outside=lambda rows:[e for e in rows if not e['ayahId'].startswith('1:')]
    C.require(outside(candidate['entries'])==outside(parent['entries']),'unrelated entries changed')
    expected=list(parent['audioSha256']);expected[0]=SOURCE;C.require(candidate['audioSha256']==expected,'unrelated source changed')
    C.require(candidate['sourceBySurah']['1']==TEMPLATE,'source declaration missing')
    for field in sorted(set(parent)|set(candidate)):
        if field.endswith('BySurah'):
            C.require({k:v for k,v in parent.get(field,{}).items() if k!='1'}=={k:v for k,v in candidate.get(field,{}).items() if k!='1'},'unrelated provenance changed')
    rows=[e for e in candidate['entries'] if e['ayahId'].startswith('1:')]
    C.require(len(rows)==7 and all(e['fileRef']==URL and e['conf']==v['conf'] and e['startMs']==v['startMs'] and e['endMs']==v['endMs'] for e,v in zip(rows,entries)),'measured data rewritten')
    if 'lowCount' in candidate:candidate['lowCount']=sum(e.get('confBand')=='LOW' for e in candidate['entries'])
    moved,added,removed=T.entry_change_counts(parent['entries'],candidate['entries']);C.require(added==removed==0,'coverage changed')
    tr=C.repaired_transform(parent,candidate,[1],PARENT,KEY)
    proof={'qualityClaim':False,'sourceUrl':URL,'audioSha256':SOURCE,'publisherIdentityUrl':m['identitySourceUrl'],'reportPath':REPORT,'reportSha256':REPORT_SHA,'measurementModel':'quran','measurementChannel':'native-1','decodedEofMs':eof,'measuredFinalSpeechEndMs':59488,'limits':['First native channel selected consistently; confidence unchanged from its measurement.','All four independent contexts agree on basmala onset and final speech end.','Publisher attribution is not biometric voice certification. Exact-SHA original QA remains mandatory.']}
    tr.update(op='ctc_quran_window:1',fromSha256=PARENT,fromKey=KEY,entriesSha256=T.entries_sha(candidate['entries']),parentEntriesSha256=T.entries_sha(parent['entries']),movedEntries=moved,addedEntries=added,removedEntries=removed,by='build_obk_publisher_repair',reason='Complete Fatiha measurement including basmala from healthy publisher source and both native channels',sourceRepair=proof,unpublishedLocalCandidate=True)
    candidate['transform']=tr
    why=T.promote.index_gate(candidate,parent=parent,parent_sha=PARENT);C.require(not why,str(why))
    fatal,warnings,_=R.structural(candidate,KEY,False);C.require(not fatal,str(fatal));C.require('1' in T.promote.census_surahs(candidate),'changed source omitted from census')
    path='ops/source-repair/candidates/codex-obk1-publisher-20261006.jz';b=gzip.compress(json.dumps(candidate,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode(),mtime=0)
    p=ROOT/path;C.require(not p.exists() or p.read_bytes()==b,'existing candidate differs');p.write_bytes(b)
    report=dict(path=path,sha256=hashlib.sha256(b).hexdigest(),parentKey=KEY,parentSha256=PARENT,op=tr['op'],changedEntries=moved,proof=proof,warnings=warnings)
    (ROOT/'ops/out/codex-obk1-publisher-candidate-20261006.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='proof'},ensure_ascii=False))

if __name__=='__main__':main()
