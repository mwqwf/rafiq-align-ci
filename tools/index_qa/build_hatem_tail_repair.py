"""Repair measured Qamar tail with original confidence; full final-SHA QA required."""
import copy,gzip,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_registered_candidate as C
import stage_transform as T
import run as R
ROOT=Path(__file__).resolve().parents[2]
PARENT='5d7e73699ae633807bd57ecb60ea235f503318fdacf8c13bd3b81132eb10f85e'
KEY='timings/hafs/hatem.jz'
def checked(path,sha):
 b=(ROOT/path).read_bytes();C.require(hashlib.sha256(b).hexdigest()==sha,'changed input '+path);return json.loads(gzip.decompress(b))
def main():
 parent=checked('ops/source-repair/parents/codex-opener-hatem-5d7e7369.jz',PARENT)
 candidate=checked('ops/source-repair/candidates/codex-hatem-opener-repair-20261006.jz','e1f2c6c2b61f3e46de65b36fbd1ef6eedad99b01061328a72b8d1617baf83ecd')
 path='ops/out/codex-hatem-expanded-contexts-complete-20261006.json.gz';raw=checked(path,'8014c224db28529f662d9d1131d5df7f262dba8a9817c2e4bb0cef1b5311c970')
 for record in raw:
  b=json.dumps(record['payload'],ensure_ascii=False,separators=(',',':')).encode();C.require(len(b)==record['bytes'] and hashlib.sha256(b).hexdigest()==record['sha256'],'raw measurement changed')
 r=next(x['payload'] for x in raw if x['payload'].get('reader')=='hatem_54_expanded')
 C.require(r['measurementComplete'] and not r['errors'] and r['source']['sha256']==parent['audioSha256'][53],'source mismatch')
 ms=r['measurements'];C.require({(m['model'],m['channel']) for m in ms}=={(m,c) for m in ('generic','quran') for c in ('native-1','native-2')},'missing matrix')
 C.require(len(r['freeResults'])==4 and all(not m['forcedAlignment'] and not m['canonicalTextInput'] for m in r['freeResults']),'free evidence missing')
 rows={e['ayahId']:e for e in candidate['entries']}
 for a in range(52,56):
  aid=f'54:{a}';es=[next(e for e in m['rawEntries'] if e['ayahId']==aid) for m in ms];qs=[next(e for e in m['rawEntries'] if e['ayahId']==aid) for m in ms if m['model']=='quran']
  C.require(max(e['startMs'] for e in es)-min(e['startMs'] for e in es)<=500 and min(e['conf'] for e in qs)>=.45,'weak/disagreeing boundary')
  start=min(e['startMs'] for e in qs);rows[aid]['startMs']=start;rows[f'54:{a-1}']['endMs']=start
 dec=r['audio']['decoded'];C.require(dec['decodedWithoutErrors'] and dec['windowEndSampleExclusive']==dec['frames'],'not decoded to EOF');eof=dec['frames']*1000//16000
 C.require(all(m['rawEntries'][-1]['endMs']<eof for m in ms),'speech outside EOF');rows['54:55']['endMs']=eof
 changes=[{'before':a,'after':b} for a,b in zip(parent['entries'],candidate['entries']) if a!=b]
 for c in changes:
  strip=lambda e:{k:v for k,v in e.items() if k not in ('startMs','endMs')}
  C.require(strip(c['before'])==strip(c['after']),'confidence changed')
  C.require(c['after']['ayahId']=='54:1' or c['after']['ayahId'] in {f'54:{a}' for a in range(51,56)},'unrelated entry changed')
 proof=dict(qualityClaim=False,originalOpenerProof=copy.deepcopy(candidate['transform'].get('sameSourceRepair')),changes=changes,decodedEofMs=eof,rawBundlePath=path,rawBundleSha256=hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),limits=['Surah82 sampled heard disagreement investigated with native contexts; Quran model13start63202 versus parent63093, so no unproved timing shift to its64924ms vicinity.','All original confidence retained, independent full QA mandatory.'])
 tr=C.repaired_transform(parent,candidate,[54],PARENT,KEY);tr.pop('sourceRepair',None);moved,added,removed=T.entry_change_counts(parent['entries'],candidate['entries']);C.require(moved==6 and added==removed==0,'wrong change population')
 tr.update(op='ctc_quran_window:54',fromSha256=PARENT,fromKey=KEY,entriesSha256=T.entries_sha(candidate['entries']),parentEntriesSha256=T.entries_sha(parent['entries']),movedEntries=moved,addedEntries=0,removedEntries=0,by='build_hatem_tail_repair',reason='Measured Qamar opener and compressed final verses with decoded EOF',sameSourceRepair=proof,unpublishedLocalCandidate=True);candidate['transform']=tr
 why=T.promote.index_gate(candidate,parent=parent,parent_sha=PARENT);C.require(not why,str(why));fatal,warnings,_=R.structural(candidate,KEY,False);C.require(not fatal,str(fatal));C.require('54' in T.promote.census_surahs(candidate),'census missing')
 out='ops/source-repair/candidates/codex-hatem-opener-tail-20261006.jz';b=gzip.compress(json.dumps(candidate,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode(),mtime=0);p=ROOT/out;C.require(not p.exists() or p.read_bytes()==b,'existing candidate differs');p.write_bytes(b)
 report=dict(path=out,sha256=hashlib.sha256(b).hexdigest(),parentSha256=PARENT,changedEntries=moved,warnings=warnings,proof=proof);(ROOT/'ops/out/codex-hatem-opener-tail-20261006.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='proof'},ensure_ascii=False))
if __name__=='__main__':main()
