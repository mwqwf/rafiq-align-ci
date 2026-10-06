"""Repair measured Hazmi tails and retain prior measured opener proposal; offline only."""
import copy,gzip,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_registered_candidate as C
import stage_transform as T
import run as R
ROOT=Path(__file__).resolve().parents[2]
PARENT='64b9c22bf0f97ee087421a604620a755f3d2e0645285f630f3956af4d26d5c41'
KEY='timings/hafs/a_alhazmi.jz'
def checked(path,sha,z=False):
 b=(ROOT/path).read_bytes();C.require(hashlib.sha256(b).hexdigest()==sha,'digest mismatch '+path)
 return json.loads(gzip.decompress(b) if z else b)
def main():
 parent=checked('ops/source-repair/parents/codex-opener-a_alhazmi-64b9c22b.jz',PARENT,True)
 candidate=checked('ops/source-repair/candidates/codex-a_alhazmi-opener-repair-20261006.jz','18512b7a369ab2da99a19ea66390b7b2d50c0fcefce865ddce4a3d0770148e20',True)
 reports=checked('ops/out/codex-hazmi-tail-contexts-20261006.json','e08db0ee344b610e909a2d3fd6000f75b51ca99e17e9437cfa392254c19bbeef')
 raw=checked('ops/out/codex-hazmi-tail-contexts-complete-20261006.json.gz','b2f49d13fb91aaa4b5d9ade4b7ff37ee3f3431b65a19e64a7715565ba739b9ef',True)
 for r in raw:
  b=json.dumps(r['payload'],ensure_ascii=False,separators=(',',':')).encode();C.require(len(b)==r['bytes'] and hashlib.sha256(b).hexdigest()==r['sha256'],'raw evidence changed')
 C.require({r['reader'] for r in reports}=={'hazmi77_tail','hazmi67_23_26','hazmi67_tail'},'wrong measurement population')
 rows={e['ayahId']:e for e in candidate['entries']};measured={};eofs={}
 for rep in reports:
  C.require(rep['measurementComplete'] and not rep['errors'],'incomplete measurement')
  src=rep['source'];s=src['surah'];C.require(src['sha256']==parent['audioSha256'][s-1],'source mismatch')
  ms=rep['measurements'];C.require({(m['model'],m['channel']) for m in ms}=={(m,c) for m in ('generic','quran') for c in ('native-1','native-2')},'missing matrix')
  C.require(len(rep['freeResults'])==4 and all(not m['forcedAlignment'] and not m['canonicalTextInput'] for m in rep['freeResults']),'missing free evidence')
  for ay in src['contextAyahs']:
   aid=f'{s}:{ay}';es=[next(e for e in m['rawEntries'] if e['ayahId']==aid) for m in ms];qs=[next(e for e in m['rawEntries'] if e['ayahId']==aid) for m in ms if m['model']=='quran']
   C.require(max(e['startMs'] for e in es)-min(e['startMs'] for e in es)<=150,'start disagreement')
   C.require(min(e['conf'] for e in qs)>=.45,'weak forced evidence')
   measured[aid]=min(e['startMs'] for e in qs)
  if rep['reader'].endswith('_tail'):
   dec=rep['audio']['decoded'];C.require(dec['decodedWithoutErrors'] and dec['windowEndSampleExclusive']==dec['frames'],'EOF not fully decoded')
   eofs[s]=dec['frames']*1000//16000
 for aid,start in measured.items():
  s,a=map(int,aid.split(':'));rows[aid]['startMs']=start;rows[f'{s}:{a-1}']['endMs']=start
 for s,eof in eofs.items():rows[f'{s}:{C.splice_surah.COUNTS[s-1]}']['endMs']=eof
 changes=[{'before':a,'after':b} for a,b in zip(parent['entries'],candidate['entries']) if a!=b]
 for c in changes:
  strip=lambda e:{k:v for k,v in e.items() if k not in ('startMs','endMs')}
  C.require(strip(c['before'])==strip(c['after']),'confidence or metadata changed')
  C.require(int(c['after']['ayahId'].split(':')[0]) in (67,77),'unrelated surah changed')
 for s in (67,77):candidate.setdefault('engineBySurah',{})[str(s)]='ctc-quran-window-1'
 for rep in reports:candidate.setdefault('alignmentModelBySurah',{})[str(rep['source']['surah'])]=copy.deepcopy(next(m['alignmentModel'] for m in rep['measurements'] if m['model']=='quran'))
 proof={'qualityClaim':False,'changes':changes,'decodedEofMs':eofs,'reports':[{k:r[k] for k in ('reader','source','provenance','measurements')} for r in reports],'originalOpenerProof':candidate['transform'].get('sameSourceRepair'),'rawBundleSha256':hashlib.sha256((ROOT/'ops/out/codex-hazmi-tail-contexts-complete-20261006.json.gz').read_bytes()).hexdigest(),'limits':['No fabricated timing from heard-only maps. Native contexts measured all changed tail starts.','Original confidence retained. Complete final-SHA independent QA required.']}
 tr=C.repaired_transform(parent,candidate,[67,77],PARENT,KEY);tr.pop('sourceRepair',None)
 moved,added,removed=T.entry_change_counts(parent['entries'],candidate['entries']);C.require(moved==len(changes) and added==removed==0,'population changed')
 tr.update(op='ctc_quran_window:67,77',fromSha256=PARENT,fromKey=KEY,entriesSha256=T.entries_sha(candidate['entries']),parentEntriesSha256=T.entries_sha(parent['entries']),movedEntries=moved,addedEntries=0,removedEntries=0,by='build_hazmi_native_tail_repairs',reason='Repair independently measured compressed tails and preserve measured opener',sameSourceRepair=proof,unpublishedLocalCandidate=True)
 candidate['transform']=tr
 why=T.promote.index_gate(candidate,parent=parent,parent_sha=PARENT);C.require(not why,str(why))
 fatal,warnings,_=R.structural(candidate,KEY,False);C.require(not fatal,str(fatal));C.require({'67','77'}<=T.promote.census_surahs(candidate),'missing census')
 path='ops/source-repair/candidates/codex-a_alhazmi-native-tails-20261006.jz';b=gzip.compress(json.dumps(candidate,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode(),mtime=0);p=ROOT/path;C.require(not p.exists() or p.read_bytes()==b,'candidate exists with different bytes');p.write_bytes(b)
 report=dict(path=path,sha256=hashlib.sha256(b).hexdigest(),parentSha256=PARENT,changedEntries=moved,warnings=warnings,proof=proof)
 (ROOT/'ops/out/codex-hazmi-native-tail-repair-20261006.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='proof'},ensure_ascii=False))
if __name__=='__main__':main()
