"""Offline same-source timing proposals; preserve existing confidence and require full QA."""
import copy, gzip, hashlib, json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_registered_candidate as C
import stage_transform as T
import run as R
ROOT=Path(__file__).resolve().parents[2]
SPECS=[('mrifai',84,'58adaf7636a7a58294889ccbf1e4318640a686020ab83b035066b2bc8c15059f','44dff45cff4e31fbfe6e5909205e911386e647377519bb08d5e9548c35a7d319',112069149017,'1bfb5fc6ddfb693beadd30e1da235c336c681fbc4690df7474354a2a8e2764dd'),('yousef',107,'a3d44fd95cdc47e6cb183a788d94ff287380f7de8306e0e0bc40267a09be3c72','a1c4ce8c4f56e85042247197c611664b16761db4252e27cf0c3c9d99f59838b7',112069149168,None)]
def checked(path,sha,z=False):
 b=(ROOT/path).read_bytes();C.require(hashlib.sha256(b).hexdigest()==sha,'evidence digest mismatch: '+path)
 return json.loads(gzip.decompress(b) if z else b)
def main():
 bundle='ops/out/codex-mrifai-yousef-tail-complete-20261006.json.gz'
 raw=checked(bundle,'af38059d7859854d60f0f0a1222c68f078216e8af7f2cdb2e04b91f2e74d3476',True)
 for record in raw:
  b=json.dumps(record['payload'],ensure_ascii=False,separators=(',',':')).encode()
  C.require(len(b)==record['bytes'] and hashlib.sha256(b).hexdigest()==record['sha256'],'raw tail changed')
 results=[]
 for rid,s,sha,reportsha,job,tailsha in SPECS:
  key=f'timings/hafs/{rid}.jz';pp=f'ops/source-repair/parents/codex-hafs-{rid}-{sha[:8]}.jz'
  parent=checked(pp,sha,True);C.require(parent['reciterId']==rid and parent['riwaya']=='hafs','parent identity')
  path=f'ops/out/codex-{rid}{s}-recovery-20261006.json';rep=checked(path,reportsha)
  tailrecord=next(r for r in reversed(raw) if r['jobId']==job)
  tailsha=tailsha or tailrecord['sha256'];tail=checked(f'ops/out/codex-tail-{job}-20261006.json',tailsha)
  C.require(rep['measurementComplete'] and tail['measurementComplete'] and not rep['errors'] and not tail['errors'],'incomplete measurement')
  audio=parent['audioSha256'][s-1]
  C.require(rep['source']['sha256']==tail['source']['sha256']==audio,'source mismatch')
  a=rep['alignment'];C.require(a['engine']=='ctc-quran-surah-1' and len(a['entries'])==C.splice_surah.COUNTS[s-1] and not a['issues'],'full alignment invalid')
  dec=tail['audio']['decoded'];C.require(dec['decodedWithoutErrors'] and dec['windowEndSampleExclusive']==dec['frames'],'tail not decoded to EOF')
  eof=dec['frames']*1000//16000
  ms=tail['measurements'];C.require({(m['model'],m['channel']) for m in ms}=={(m,c) for m in ('generic','quran') for c in ('native-1','native-2')},'missing native measurements')
  C.require(len(tail['freeResults'])==4 and all(not m['canonicalTextInput'] and not m['forcedAlignment'] for m in tail['freeResults']),'missing free evidence')
  final=f'{s}:{len(a["entries"])}'
  C.require(all(abs(next(e['startMs'] for e in m['rawEntries'] if e['ayahId']==final)-a['entries'][-1]['startMs'])<500 for m in ms),'tail start disagreement')
  C.require(all(next(e['endMs'] for e in m['rawEntries'] if e['ayahId']==final)<=eof for m in ms),'speech beyond EOF')
  candidate=copy.deepcopy(parent);rows={e['ayahId']:e for e in candidate['entries']};changes=[]
  for i,measured in enumerate(a['entries']):
   aid=f'{s}:{i+1}';C.require(measured['ayahIdx']==i and aid in rows,'noncanonical population')
   before=copy.deepcopy(rows[aid]);rows[aid]['startMs']=measured['startMs'];rows[aid]['endMs']=eof if aid==final else measured['endMs']
   C.require(0<=rows[aid]['startMs']<rows[aid]['endMs']<=eof,'invalid measured interval')
   if before!=rows[aid]:changes.append({'before':before,'after':copy.deepcopy(rows[aid])})
  changed={c['before']['ayahId'] for c in changes}
  C.require([e for e in parent['entries'] if e['ayahId'] not in changed]==[e for e in candidate['entries'] if e['ayahId'] not in changed],'unrelated entries changed')
  for c in changes:
   strip=lambda e:{k:v for k,v in e.items() if k not in ('startMs','endMs')}
   C.require(strip(c['before'])==strip(c['after']),'original confidence changed')
  candidate.setdefault('engineBySurah',{})[str(s)]=a['engine'];candidate.setdefault('alignmentModelBySurah',{})[str(s)]=copy.deepcopy(a['alignmentModel'])
  tr=C.repaired_transform(parent,candidate,[s],sha,key);tr.pop('sourceRepair',None)
  moved,added,removed=T.entry_change_counts(parent['entries'],candidate['entries']);C.require(moved==len(changes) and added==removed==0,'coverage changed')
  proof={'qualityClaim':False,'reportPath':path,'reportSha256':reportsha,'tailReportSha256':tailsha,'rawTailBundlePath':bundle,'decodedEofMs':eof,'changes':changes,'limits':['All original confidence and unrelated entries preserved.','Full exact-SHA QA and independent heard/census required.','Forced alignment alone is not source completeness proof.']}
  tr.update(op=f'ctc_quran_surah_splice:{s}',fromSha256=sha,fromKey=key,entriesSha256=T.entries_sha(candidate['entries']),parentEntriesSha256=T.entries_sha(parent['entries']),movedEntries=moved,addedEntries=0,removedEntries=0,by='build_mrifai_yousef_repairs',reason='Measured same-source full-surah timings with native decoded EOF',sameSourceRepair=proof,unpublishedLocalCandidate=True)
  candidate['transform']=tr
  why=T.promote.index_gate(candidate,parent=parent,parent_sha=sha);C.require(not why,str(why))
  fatal,warnings,_=R.structural(candidate,key,False);C.require(not fatal,str(fatal));C.require(str(s) in T.promote.census_surahs(candidate),'census omitted changed surah')
  out=f'ops/source-repair/candidates/codex-{rid}-{s}-repair-20261006.jz';b=gzip.compress(json.dumps(candidate,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode(),mtime=0)
  p=ROOT/out;C.require(not p.exists() or p.read_bytes()==b,'existing candidate changed');p.write_bytes(b)
  results.append(dict(reciterId=rid,riwaya='hafs',path=out,sha256=hashlib.sha256(b).hexdigest(),parentKey=key,parentSha256=sha,changedEntries=moved,op=tr['op'],proof=proof,warnings=warnings))
 (ROOT/'ops/out/codex-mrifai-yousef-repairs-20261006.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps([{k:v for k,v in r.items() if k!='proof'} for r in results],ensure_ascii=False))
if __name__=='__main__':main()
