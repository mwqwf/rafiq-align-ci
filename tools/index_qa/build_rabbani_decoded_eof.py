"""Correct measured EOF overhangs without changing the strict sample-window guard."""
import copy,gzip,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_registered_candidate as C
import stage_transform as T
import run as R
ROOT=Path(__file__).resolve().parents[2]
PARENT='d9534de9ed7aed07154a5784f2cefc5b7fef16981061bf9e4c3f9bc22a44b2aa'
KEY='timings/warsh/rabbani_warsh.jz'
def checked(path,sha):
 b=(ROOT/path).read_bytes();C.require(hashlib.sha256(b).hexdigest()==sha,'changed input '+path);return json.loads(gzip.decompress(b))
def main():
 parent=checked('ops/source-repair/parents/codex-opener-rabbani_warsh-d9534de9.jz',PARENT)
 candidate=checked('ops/source-repair/candidates/codex-rabbani_warsh-opener-repair-20261006.jz','893e1a230f18e929a9c902e50a6110b2e896dfbb6962a59415037de02215f75c')
 path='ops/out/codex-rabbani-eof-contexts-complete-20261006.json.gz';raw=checked(path,'8500798e28b8aea136d88c3f288f633a776b1dc91d315993ac1c93067c480df7');reports=[]
 for r in raw:
  b=json.dumps(r['payload'],ensure_ascii=False,separators=(',',':')).encode();C.require(len(b)==r['bytes'] and hashlib.sha256(b).hexdigest()==r['sha256'],'raw evidence changed')
  if 'measurementComplete' in r['payload']:reports.append(r['payload'])
 C.require({r['reader'] for r in reports}=={'rabbani_warsh_77_expanded','rabbani_warsh_96_expanded'},'wrong context population')
 eofProof=[]
 for r in reports:
  src=r['source'];s=src['surah'];C.require(r['measurementComplete'] and not r['errors'] and src['sha256']==parent['audioSha256'][s-1],'source mismatch')
  dec=r['audio']['decoded'];C.require(dec['decodedWithoutErrors'] and dec['windowEndSampleExclusive']==dec['frames'],'incomplete EOF')
  eof=dec['frames']*1000//16000;aid=f'{s}:{C.splice_surah.COUNTS[s-1]}';row=next(e for e in candidate['entries'] if e['ayahId']==aid)
  C.require(0<row['endMs']-eof<30,'not the measured MPEG padding overhang')
  ms=r['measurements'];C.require(len(ms)==4 and all(next(e['endMs'] for e in m['rawEntries'] if e['ayahId']==aid)<eof for m in ms),'final speech not contained')
  candidate.setdefault('engineBySurah',{})[str(s)]='ctc-quran-window-1'
  model=copy.deepcopy(next(m['alignmentModel'] for m in ms if m['model']=='quran'));model['canonicalTextChanged']=False
  candidate.setdefault('alignmentModelBySurah',{})[str(s)]=model
  eofProof.append(dict(ayahId=aid,beforeEndMs=row['endMs'],decodedEofMs=eof,sourceSha256=src['sha256'],provenance=r['provenance']));row['endMs']=eof
 changes=[{'before':a,'after':b} for a,b in zip(parent['entries'],candidate['entries']) if a!=b]
 for c in changes:
  strip=lambda e:{k:v for k,v in e.items() if k not in ('startMs','endMs')}
  C.require(strip(c['before'])==strip(c['after']),'confidence/source changed')
 oldproof=copy.deepcopy(candidate['transform'].get('sameSourceRepair'));tr=C.repaired_transform(parent,candidate,[56,77,96,102],PARENT,KEY);tr.pop('sourceRepair',None)
 moved,added,removed=T.entry_change_counts(parent['entries'],candidate['entries']);C.require(moved==8 and added==removed==0,'unexpected change population')
 proof=dict(qualityClaim=False,originalOpenerProof=oldproof,decodedEofProof=eofProof,rawBundlePath=path,rawBundleSha256=hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),limits=['Native contexts include partial96:15; that row is deliberately unchanged.','Only last ends77:50 and96:19 floor verified PCM EOF. Original confidence unchanged.','No padding/quality guard is modified; full fresh QA mandatory.'])
 tr.update(op='ctc_quran_window:56,77,96,102',fromSha256=PARENT,fromKey=KEY,entriesSha256=T.entries_sha(candidate['entries']),parentEntriesSha256=T.entries_sha(parent['entries']),movedEntries=moved,addedEntries=0,removedEntries=0,by='build_rabbani_decoded_eof',reason='Restore measured openers and trim only proven EOF overhangs',sameSourceRepair=proof,unpublishedLocalCandidate=True);candidate['transform']=tr
 why=T.promote.index_gate(candidate,parent=parent,parent_sha=PARENT);C.require(not why,str(why));fatal,warnings,_=R.structural(candidate,KEY,False);C.require(not fatal,str(fatal));C.require({'56','77','96','102'}<=T.promote.census_surahs(candidate),'census omitted changed surah')
 out='ops/source-repair/candidates/codex-rabbani-openers-eof-20261006.jz';b=gzip.compress(json.dumps(candidate,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode(),mtime=0);p=ROOT/out;C.require(not p.exists() or p.read_bytes()==b,'existing candidate changed');p.write_bytes(b)
 report=dict(path=out,sha256=hashlib.sha256(b).hexdigest(),parentSha256=PARENT,changedEntries=moved,proof=proof,warnings=warnings);(ROOT/'ops/out/codex-rabbani-openers-eof-20261006.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='proof'},ensure_ascii=False))
if __name__=='__main__':main()
