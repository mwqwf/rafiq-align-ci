"""Offline full-source timing repair with separately measured tails; preserves confidence."""
import copy,gzip,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_registered_candidate as C
import stage_transform as T
import run as R
ROOT=Path(__file__).resolve().parents[2]
PARENT='f98bc7b302a415e1755ac319cb900f546ac25d3229d8a77e6014b4fe46fae300'
KEY='timings/warsh/benkirane_warsh.jz'
def checked(path,sha,z=False):
 b=(ROOT/path).read_bytes();C.require(hashlib.sha256(b).hexdigest()==sha,'evidence changed: '+path)
 return json.loads(gzip.decompress(b) if z else b)
def main():
 parent=checked('ops/source-repair/parents/codex-opener-benkirane_warsh-f98bc7b3.jz',PARENT,True)
 contexts=checked('ops/out/codex-benkirane-contexts-20261006.json','05b10fb97669ca43b9edf939ffeacceb0952366bd76ce0a4462405eefcbf9f0b')
 raw=checked('ops/out/codex-benkirane-contexts-complete-20261006.json.gz','5359e95e8537b707fca31841d7bb8aca1e3f3478fd08152d32e921940dcff6a1',True)
 for r in raw:
  b=json.dumps(r['payload'],ensure_ascii=False,separators=(',',':')).encode();C.require(len(b)==r['bytes'] and hashlib.sha256(b).hexdigest()==r['sha256'],'raw context changed')
 C.require({r['reader'] for r in contexts}=={'benkirane51_middle','benkirane51_tail','benkirane77_tail'},'context population changed')
 candidate=copy.deepcopy(parent);rows={e['ayahId']:e for e in candidate['entries']};proof={'qualityClaim':False,'sources':{},'contextReportsSha256':'05b10fb97669ca43b9edf939ffeacceb0952366bd76ce0a4462405eefcbf9f0b','contextRawBundleSha256':'5359e95e8537b707fca31841d7bb8aca1e3f3478fd08152d32e921940dcff6a1'}
 for s in (51,77):
  reps=[r for r in contexts if r['source']['surah']==s]
  ref=reps[0]['source'];full=checked(ref['evidencePath'],ref['evidenceSha256'])
  C.require(full['measurementComplete'] and not full['errors'] and full['source']['sha256']==parent['audioSha256'][s-1],'full-source mismatch')
  aligned=full['alignment'];C.require(aligned['engine']=='ctc-quran-surah-1' and len(aligned['entries'])==C.splice_surah.COUNTS[s-1],'alignment count/engine')
  starts={f'{s}:{i+1}':e['startMs'] for i,e in enumerate(aligned['entries'])};native={};eof=None
  for rep in reps:
   C.require(rep['measurementComplete'] and not rep['errors'] and rep['source']['sha256']==parent['audioSha256'][s-1],'context incomplete/mismatched')
   ms=rep['measurements'];C.require({(m['model'],m['channel']) for m in ms}=={(m,c) for m in ('generic','quran') for c in ('native-1','native-2')},'missing matrix')
   C.require(len(rep['freeResults'])==4 and all(not m['forcedAlignment'] and not m['canonicalTextInput'] for m in rep['freeResults']),'free evidence missing')
   for ay in rep['source']['contextAyahs']:
    aid=f'{s}:{ay}';es=[next(e for e in m['rawEntries'] if e['ayahId']==aid) for m in ms];qs=[next(e for e in m['rawEntries'] if e['ayahId']==aid) for m in ms if m['model']=='quran']
    C.require(max(e['startMs'] for e in es)-min(e['startMs'] for e in es)<=500,'context start disagreement')
    C.require(min(e['conf'] for e in qs)>=.45,'weak context')
    native.setdefault(aid,[]).extend(e['startMs'] for e in qs)
   if rep['reader'].endswith('_tail'):
    dec=rep['audio']['decoded'];C.require(dec['decodedWithoutErrors'] and dec['windowEndSampleExclusive']==dec['frames'],'EOF not decoded');eof=dec['frames']*1000//16000
  for aid,measurements in native.items():
   C.require(max(measurements)-min(measurements)<=500,'overlapping contexts disagree')
   starts[aid]=min(measurements)
  C.require(eof and all(f'{s}:{e["ayahIdx"]+1}' in native for e in aligned['entries'] if e['conf']<.45),'unresolved LOW full-source timing')
  for i,e in enumerate(aligned['entries']):
   aid=f'{s}:{i+1}';C.require(e['ayahIdx']==i,'unordered alignment');rows[aid]['startMs']=starts[aid];rows[aid]['endMs']=starts[f'{s}:{i+2}'] if i+1<len(aligned['entries']) else eof
   C.require(0<=rows[aid]['startMs']<rows[aid]['endMs']<=eof,'invalid repaired interval')
  candidate.setdefault('engineBySurah',{})[str(s)]='ctc-quran-surah-1';candidate.setdefault('alignmentModelBySurah',{})[str(s)]=copy.deepcopy(aligned['alignmentModel'])
  proof['sources'][str(s)]={'alignmentReportPath':ref['evidencePath'],'alignmentReportSha256':ref['evidenceSha256'],'nativeStarts':native,'decodedEofMs':eof,'sourceSha256':ref['sha256']}
 changes=[{'before':a,'after':b} for a,b in zip(parent['entries'],candidate['entries']) if a!=b]
 for c in changes:
  strip=lambda e:{k:v for k,v in e.items() if k not in ('startMs','endMs')}
  C.require(strip(c['before'])==strip(c['after']) and int(c['after']['ayahId'].split(':')[0]) in (51,77),'confidence/unrelated data changed')
 proof['changes']=changes;proof['limits']=['Original confidence retained; LOW measurements are not promoted.','500ms overlap spread remains subject to original full QA thresholds.','Complete final-SHA heard/census/quality review required.']
 tr=C.repaired_transform(parent,candidate,[51,77],PARENT,KEY);tr.pop('sourceRepair',None)
 moved,added,removed=T.entry_change_counts(parent['entries'],candidate['entries']);C.require(moved==len(changes) and added==removed==0,'population changed')
 tr.update(op='ctc_quran_surah_splice:51,77',fromSha256=PARENT,fromKey=KEY,entriesSha256=T.entries_sha(candidate['entries']),parentEntriesSha256=T.entries_sha(parent['entries']),movedEntries=moved,addedEntries=0,removedEntries=0,by='build_benkirane_measured_repairs',reason='Full-source timing proposal with independently measured compressed tails',sameSourceRepair=proof,unpublishedLocalCandidate=True);candidate['transform']=tr
 why=T.promote.index_gate(candidate,parent=parent,parent_sha=PARENT);C.require(not why,str(why))
 fatal,warnings,_=R.structural(candidate,KEY,False);C.require(not fatal,str(fatal));C.require({'51','77'}<=T.promote.census_surahs(candidate),'missing census')
 out='ops/source-repair/candidates/codex-benkirane-51-77-repair-20261006.jz';b=gzip.compress(json.dumps(candidate,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode(),mtime=0);p=ROOT/out;C.require(not p.exists() or p.read_bytes()==b,'existing output differs');p.write_bytes(b)
 report=dict(path=out,sha256=hashlib.sha256(b).hexdigest(),parentSha256=PARENT,changedEntries=moved,warnings=warnings,proof=proof);(ROOT/'ops/out/codex-benkirane-measured-repairs-20261006.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='proof'},ensure_ascii=False))
if __name__=='__main__':main()
