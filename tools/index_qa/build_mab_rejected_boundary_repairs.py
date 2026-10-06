"""Repair measured rs1 defects and Haaqqa tail; do not resample an unchanged rejected candidate."""
import copy,gzip,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_registered_candidate as C
import stage_transform as T
import run as R
ROOT=Path(__file__).resolve().parents[2]
PARENT='746e762fc2722d0c6cc108d239aa0ad5ba1947e13189013201f4b3964201fee5'
KEY='timings/warsh/m_abdulkareem_warsh.jz'
SPEC={'mab_rs1_11_22':[21,22,23],'mab_rs1_16_9':[8,9,10],'mab_rs1_18_90':[89,90,91],'mab_rs1_23_52':[52,53],'mab_rs1_23_79':[78,79],'mab_rs1_90_19':[18,19,20],'mab90_4_8':list(range(4,9)),'mab90_10_14':list(range(10,15)),'mab78_32_36':list(range(32,37)),'m_abdulkareem_warsh_69_expanded':list(range(45,53))}
def checked(path,sha,z=False):
 b=(ROOT/path).read_bytes();C.require(hashlib.sha256(b).hexdigest()==sha,'changed input '+path);return json.loads(gzip.decompress(b) if z else b)
def main():
 parent=checked('ops/source-repair/parents/codex-warsh-m_abdulkareem_warsh-746e762f.jz',PARENT,True)
 candidate=checked('ops/source-repair/candidates/codex-m_abdulkareem_warsh-context-repair-v2-20261006.jz','736a4f09a4ba89f04937e90f9308f3b2ed30e643f2d56f309afbbc89cff5a0ef',True)
 rp='ops/out/codex-mab-v3-contexts-20261006.json';bp='ops/out/codex-mab-v3-contexts-complete-20261006.json.gz'
 reports=checked(rp,'8eee02435e0b2ac7a55c3e70946f109fe2ca44bf18e9e3a4a058e930df6a64c3');raw=checked(bp,'93e1f5bf76c2256a29537382ae00ea6c535dcbce98ed64795b7b90afebab596d',True)
 C.require(len(reports)==14 and len({r['reader'] for r in reports})==14,'wrong evidence population')
 for record in raw:
  b=json.dumps(record['payload'],ensure_ascii=False,separators=(',',':')).encode();C.require(len(b)==record['bytes'] and hashlib.sha256(b).hexdigest()==record['sha256'],'raw evidence changed')
 rows={e['ayahId']:e for e in candidate['entries']};selected=[];surahs={21};eofs={}
 for ident,ayahs in SPEC.items():
  rep=next(r for r in reports if r['reader']==ident);src=rep['source'];s=src['surah'];surahs.add(s)
  C.require(rep['measurementComplete'] and not rep['errors'] and src['sha256']==parent['audioSha256'][s-1] and src['riwaya']=='warsh','incomplete/source mismatch')
  ms=rep['measurements'];C.require({(m['model'],m['channel']) for m in ms}=={(m,c) for m in ('generic','quran') for c in ('native-1','native-2')},'missing native/model measurements')
  C.require(len(rep['freeResults'])==4 and all(not m['forcedAlignment'] and not m['canonicalTextInput'] for m in rep['freeResults']),'missing free measurement')
  for a in ayahs:
   aid=f'{s}:{a}';es=[next(e for e in m['rawEntries'] if e['ayahId']==aid) for m in ms];qs=[next(e for e in m['rawEntries'] if e['ayahId']==aid) for m in ms if m['model']=='quran']
   C.require(max(e['startMs'] for e in es)-min(e['startMs'] for e in es)<=500 and min(e['conf'] for e in qs)>=.45,'ambiguous/weak target '+aid)
   start=min(e['startMs'] for e in qs);rows[aid]['startMs']=start;rows[f'{s}:{a-1}']['endMs']=start
  last=f'{s}:{ayahs[-1]}'
  if ayahs[-1]==C.splice_surah.COUNTS[s-1]:
   dec=rep['audio']['decoded'];C.require(dec['decodedWithoutErrors'] and dec['windowEndSampleExclusive']==dec['frames'],'final context not to EOF');eof=dec['frames']*1000//16000;rows[last]['endMs']=eof;eofs[s]=eof
  C.require(rows[last]['endMs']>=max(next(e['endMs'] for e in m['rawEntries'] if e['ayahId']==last) for m in ms),'retained context end would clip speech '+last)
  model=copy.deepcopy(next(m['alignmentModel'] for m in ms if m['model']=='quran'));model['canonicalTextChanged']=False
  candidate.setdefault('engineBySurah',{})[str(s)]='ctc-quran-window-1';candidate.setdefault('alignmentModelBySurah',{})[str(s)]=model
  selected.append({'reader':ident,'ayahs':ayahs,'sourceSha256':src['sha256'],'provenance':rep['provenance']})
 changes=[{'before':a,'after':b} for a,b in zip(parent['entries'],candidate['entries']) if a!=b]
 for c in changes:
  strip=lambda e:{k:v for k,v in e.items() if k not in ('startMs','endMs')}
  C.require(strip(c['before'])==strip(c['after']) and int(c['after']['ayahId'].split(':')[0]) in surahs,'confidence/unrelated metadata changed')
 proof=dict(qualityClaim=False,original21Proof=copy.deepcopy(candidate['transform'].get('sameSourceRepair')),selectedContexts=selected,decodedEofMs=eofs,changes=changes,reportPath=rp,reportSha256=hashlib.sha256((ROOT/rp).read_bytes()).hexdigest(),rawBundlePath=bp,rawBundleSha256=hashlib.sha256((ROOT/bp).read_bytes()).hexdigest(),limits=['Original v2 rejection and severe rs1 samples retained; this candidate actually changes those diagnosed timings.','All original confidence retained. No acceptance thresholds or sampling procedure changed.','23:51 ambiguous context start and23:80/81 outside target remain unchanged.','Fresh final-SHA full QA, census and independent heard gate mandatory.'])
 tr=C.repaired_transform(parent,candidate,sorted(surahs),PARENT,KEY);tr.pop('sourceRepair',None);moved,added,removed=T.entry_change_counts(parent['entries'],candidate['entries']);C.require(moved==len(changes) and added==removed==0,'population changed')
 tr.update(op='ctc_quran_window:'+','.join(map(str,sorted(surahs))),fromSha256=PARENT,fromKey=KEY,entriesSha256=T.entries_sha(candidate['entries']),parentEntriesSha256=T.entries_sha(parent['entries']),movedEntries=moved,addedEntries=0,removedEntries=0,by='build_mab_rejected_boundary_repairs',reason='Repair measured rejected boundaries and compressed Haaqqa tail using native source contexts',sameSourceRepair=proof,unpublishedLocalCandidate=True);candidate['transform']=tr
 why=T.promote.index_gate(candidate,parent=parent,parent_sha=PARENT);C.require(not why,str(why));fatal,warnings,_=R.structural(candidate,KEY,False);C.require(not fatal,str(fatal));C.require(set(map(str,surahs))<=T.promote.census_surahs(candidate),'census missing')
 out='ops/source-repair/candidates/codex-mab-context-v3-20261006.jz';b=gzip.compress(json.dumps(candidate,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode(),mtime=0);p=ROOT/out;C.require(not p.exists() or p.read_bytes()==b,'existing output differs');p.write_bytes(b)
 report=dict(path=out,sha256=hashlib.sha256(b).hexdigest(),parentSha256=PARENT,changedEntries=moved,op=tr['op'],warnings=warnings,proof=proof);(ROOT/'ops/out/codex-mab-context-v3-20261006.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='proof'},ensure_ascii=False))
if __name__=='__main__':main()
