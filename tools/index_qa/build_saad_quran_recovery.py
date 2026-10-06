"""Recover three complete same-byte source surahs; offline proposal, full QA pending."""
import copy,gzip,hashlib,json,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_registered_candidate as C
import stage_transform as T
import run as R
ROOT=Path(__file__).resolve().parents[2]
PARENT='8e9f8131711748d617a6339a1d1ab5a511959bf4eb396700d9d4fdf724a747c0'
KEY='timings/hafs/saad.jz'
ENGINE='ctc-quran-surah-1'
TAIL22_SHA='35a60eee9ae861fe8a662b4b568767d70123c57ae16342031ab3f8757a34ecd0'
CONTEXT43_SHA='43639e39c7379dc160598371a0acbf6c41c1957e3d1eecdfed9c9c16455d28e6'
CONTEXT70_SHA='60f8a5babe7b60d0b7e663da7435462609736e1d874dd2c34c35c3d223b8dd16'
REPORTS={22:'262e5097e3dc26f00490da174fb9475cdf38de6675178a2857c575b39bf48fa3',28:'4f4fd390701f225c2e38346be154cba1f0bf97136abcb468572128afe308613d',45:'ddf348363400297ca608363339554c6f01b2ded143a2c808b4e30899a45faf13'}
def checked(path,sha,z=False):
 b=(ROOT/path).read_bytes();C.require(hashlib.sha256(b).hexdigest()==sha,'changed evidence '+path)
 return json.loads(gzip.decompress(b) if z else b)
def main():
 pp='ops/source-repair/parents/codex-hafs-saad-8e9f8131.jz';parent=checked(pp,PARENT,True)
 C.require(parent['reciterId']=='saad' and parent['riwaya']=='hafs' and len(parent['audioSha256'])==114,'parent identity')
 contexts=checked('ops/out/codex-source-context-37395546994-and-37395853329-reports.json','cefb8f1d30cae7276120f2e6d6bd6e8286ab85f87ff47394d2c237afe6978d7b')
 tail28=checked('ops/out/source-report-112053981792.json','bbd5fd2023191ea17a16d9f29faae06551011b335426ef4abb9c11e8bce1ca11')
 checked('ops/out/saad28-tail-37396603183-complete.json.gz','e076fa5b0038c9718a622ee9d9e6bf146b56defeed982fe7374d1192fcbb4e41',True)
 checked('ops/out/saad22-context-37397731207-complete.json.gz','8ad2f02c6c7572e35f04cff3104736a4da44519541f96c69d6a8e3e8c63c4180',True)
 proof={'kind':'same-byte-source-quran-recovery','qualityClaim':False,'sources':{},'limits':['Forced alignment is not independent presence proof.','LOW confidence retained. Full exact-SHA QA, census and heard gate mandatory.','Measurement mirror URL retained in evidence; catalog fileRef has identical parent audio SHA.']}
 with tempfile.TemporaryDirectory() as td:
  td=Path(td);files=[]
  for s,sha in REPORTS.items():
   rep=checked('ops/out/source-report-112053959165.json' if s==22 else f'ops/out/codex-source-quran-saad{s}-37389920485.json',sha)
   C.require(rep['measurementComplete'] and not rep['errors'] and rep['source']['sha256']==parent['audioSha256'][s-1],'source mismatch')
   a=copy.deepcopy(rep['alignment']);C.require(a['engine']==ENGINE and len(a['entries'])==C.splice_surah.COUNTS[s-1],'alignment engine/count')
   C.require(not any(e['ayahId'].startswith(str(s)+':') for e in parent['entries']),'surah already exists')
   ctx=checked('ops/out/source-report-112057600813.json',TAIL22_SHA) if s==22 else tail28 if s==28 else next(r for r in contexts if r['reader']=='saad45_tail')
   C.require(ctx['measurementComplete'] and not ctx['errors'] and ctx['source']['sha256']==rep['source']['sha256'],'tail context mismatch')
   eof=int(ctx['audio']['decoded']['durationSeconds']*1000)
   q=[m for m in ctx['measurements'] if m['model']=='quran'];C.require(len(q)==2,'both channels required')
   changes=[]
   if s==45:
    for ay,start,end in [(35,None,362726),(36,362726,370161),(37,370161,eof)]:
     row=a['entries'][ay-1];old=copy.deepcopy(row)
     if start is not None:
      C.require(all(next(e['startMs'] for e in m['rawEntries'] if e['ayahId']==f'{s}:{ay}')==start for m in q),'unmeasured boundary')
      row['startMs']=start
     row['endMs']=end;changes.append({'before':old,'after':copy.deepcopy(row)})
   elif s==28:
    C.require(all(next(e['endMs'] for e in m['rawEntries'] if e['ayahId']=='28:88')==1318686 for m in q),'tail changed')
    old=copy.deepcopy(a['entries'][-1]);a['entries'][-1]['endMs']=eof;changes.append({'before':old,'after':copy.deepcopy(a['entries'][-1])})
   else:
    old=copy.deepcopy(a['entries'][-1]);a['entries'][-1]['endMs']=eof;changes.append({'before':old,'after':copy.deepcopy(a['entries'][-1])})
    # Full-source starts already agree with the independent short contexts within 0.5s.
    # Preserve the original zero confidence for 43/70; only exact-SHA QA can accept them.
    for job,hash_,ay in [(112057601242,CONTEXT43_SHA,43),(112057601071,CONTEXT70_SHA,70)]:
     context=checked(f'ops/out/source-report-{job}.json',hash_)
     C.require(context['measurementComplete'] and not context['errors'] and context['source']['sha256']==rep['source']['sha256'],'interior evidence mismatch')
     rows=[next(e for e in m['rawEntries'] if e['ayahId']==f'22:{ay}') for m in context['measurements']]
     C.require(len(rows)==4 and all(abs(e['startMs']-a['entries'][ay-1]['startMs'])<500 for e in rows),'interior context disagreement')
     proof.setdefault('interiorContextReports',{})[str(ay)]={'sha256':hash_,'provenance':context['provenance'],'measurements':context['measurements']}
   for c in changes:
    strip=lambda e:{k:v for k,v in e.items() if k not in ('startMs','endMs')}
    C.require(strip(c['before'])==strip(c['after']),'confidence changed')
   a['totalMs']=eof
   a['sha256']=rep['source']['sha256']
   # Record the actual mirror measurement without misrepresenting it as the catalog URL.
   a['fileRef']=rep['source']['url']
   p=td/f'{s}.json';p.write_text(json.dumps(a,ensure_ascii=False));files.append(str(p))
   proof['sources'][str(s)]={'source':rep['source'],'reportSha256':sha,'contextProvenance':ctx['provenance'],'decodedEofMs':eof,'changes':changes,'originalBands':rep['alignment']['bands']}
  out=td/'merged.jz';oldargv=sys.argv
  sys.argv=[C.splice_surah.__file__,'--index',str(ROOT/pp),'--surah','22,28,45','--aligned',*files,'--url','https://server16.mp3quran.net/saad/Rewayat-Hafs-A-n-Assem/{s:03d}.mp3','--engine-tag',ENGINE,'--out',str(out)]
  try:C.splice_surah.main()
  finally:sys.argv=oldargv
  C.require(Path(str(out)+'.taken').read_text()=='22,28,45','incomplete merge');candidate=json.loads(gzip.decompress(out.read_bytes()))
 outside=lambda es:[e for e in es if int(e['ayahId'].split(':')[0]) not in REPORTS]
 C.require(outside(parent['entries'])==outside(candidate['entries']),'unrelated rows changed')
 C.require(parent['audioSha256']==candidate['audioSha256'] and parent.get('sourceBySurah')==candidate.get('sourceBySurah'),'source changed')
 C.require(candidate['missing']['count']==0 and not candidate['missing']['ids'] and not any(candidate['missing']['byReason'].values()),'remaining gap misreported');candidate['missing']['byReason']={}
 moved,added,removed=T.entry_change_counts(parent['entries'],candidate['entries']);C.require((moved,added,removed)==(0,203,0),'wrong recovery population')
 tr=C.repaired_transform(parent,candidate,[22,28,45],PARENT,KEY);tr.pop('sourceRepair',None);tr.pop('dropSurah',None);tr.pop('reasonCode',None);tr.pop('reasonUser',None)
 tr.update(op='ctc_quran_surah_splice:22,28,45',fromSha256=PARENT,fromKey=KEY,entriesSha256=T.entries_sha(candidate['entries']),parentEntriesSha256=T.entries_sha(parent['entries']),movedEntries=moved,addedEntries=added,removedEntries=removed,by='build_saad_quran_recovery',reason='Full-source Quran alignment with native tail contexts; original source bytes retained',sameSourceRepair=proof,unpublishedLocalCandidate=True)
 candidate['transform']=tr
 if 'lowCount' in candidate:candidate['lowCount']=sum(e.get('confBand')=='LOW' for e in candidate['entries'])
 why=T.promote.index_gate(candidate,parent=parent,parent_sha=PARENT);C.require(not why,'index guard: '+str(why))
 fatal,warnings,_=R.structural(candidate,KEY,False);C.require(not fatal,str(fatal))
 C.require({'22','28','45'}<=set(T.promote.census_surahs(candidate)),'census omitted recovery')
 path=ROOT/'ops/source-repair/candidates/codex-saad-quran-22-28-45-20261006.jz';b=gzip.compress(json.dumps(candidate,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode(),mtime=0)
 C.require(not path.exists() or path.read_bytes()==b,'existing output differs');path.write_bytes(b)
 report={'path':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(b).hexdigest(),'parentSha256':PARENT,'addedEntries':added,'missing':0,'warnings':warnings,'proof':proof}
 (ROOT/'ops/out/codex-saad-quran-22-28-45-recovery-20261006.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='proof'},ensure_ascii=False))
if __name__=='__main__':main()
