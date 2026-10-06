"""Isolate measured Dhariyat repair while Mursalat remains explicitly unresolved."""
import copy,gzip,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_benkirane_measured_repairs as B
C,T,R=B.C,B.T,B.R

def main():
    parent=B.checked('ops/source-repair/parents/codex-opener-benkirane_warsh-f98bc7b3.jz',B.PARENT,True)
    measured=B.checked('ops/source-repair/candidates/codex-benkirane-51-77-repair-20261006.jz','20f6052e322bc3dc50a61c34fb2a07f86b1999563119fd533219679602b8e834',True)
    candidate=copy.deepcopy(parent);repairs={e['ayahId']:e for e in measured['entries'] if e['ayahId'].startswith('51:')}
    C.require(len(repairs)==60,'incomplete measured Dhariyat')
    candidate['entries']=[copy.deepcopy(repairs.get(e['ayahId'],e)) for e in parent['entries']]
    for field in ('engineBySurah','alignmentModelBySurah'):candidate.setdefault(field,{})['51']=copy.deepcopy(measured[field]['51'])
    changes=[{'before':x,'after':y} for x,y in zip(parent['entries'],candidate['entries']) if x!=y]
    for c in changes:
        strip=lambda e:{k:v for k,v in e.items() if k not in ('startMs','endMs')}
        C.require(c['after']['ayahId'].startswith('51:') and strip(c['before'])==strip(c['after']),'unrelated/confidence change')
    proof={'qualityClaim':False,'sourceProof':measured['transform']['sameSourceRepair']['sources']['51'],'changes':changes,
      'contextReportsSha256':'05b10fb97669ca43b9edf939ffeacceb0952366bd76ce0a4462405eefcbf9f0b',
      'contextRawBundleSha256':'5359e95e8537b707fca31841d7bb8aca1e3f3478fd08152d32e921940dcff6a1',
      'limits':['77 remains exactly as published and still requires repair; its rejected combined candidate is not adopted.',
                '77:27 contains a repeated partial phrase; generic/Quran context disagreement remains unresolved under original heard gate.',
                'This changes only51 and must pass fresh final-SHA full QA. No completeness claim.']}
    tr=C.repaired_transform(parent,candidate,[51],B.PARENT,B.KEY);tr.pop('sourceRepair',None)
    moved,added,removed=T.entry_change_counts(parent['entries'],candidate['entries']);C.require(moved==len(changes) and added==removed==0,'population changed')
    tr.update(op='ctc_quran_surah_splice:51',fromSha256=B.PARENT,fromKey=B.KEY,entriesSha256=T.entries_sha(candidate['entries']),parentEntriesSha256=T.entries_sha(parent['entries']),movedEntries=moved,addedEntries=0,removedEntries=0,by='build_benkirane51_only',reason='Measured Dhariyat-only repair; Mursalat remains unresolved',sameSourceRepair=proof,unpublishedLocalCandidate=True);candidate['transform']=tr
    why=T.promote.index_gate(candidate,parent=parent,parent_sha=B.PARENT);C.require(not why,str(why));fatal,warnings,_=R.structural(candidate,B.KEY,False);C.require(not fatal,str(fatal));C.require('51' in T.promote.census_surahs(candidate),'missing census')
    out='ops/source-repair/candidates/codex-benkirane51-only-20261006.jz';b=gzip.compress(json.dumps(candidate,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode(),mtime=0);p=B.ROOT/out;C.require(not p.exists() or p.read_bytes()==b,'existing output differs');p.write_bytes(b)
    result=dict(path=out,sha256=hashlib.sha256(b).hexdigest(),parentSha256=B.PARENT,changedEntries=moved,warnings=warnings,proof=proof)
    (B.ROOT/'ops/out/codex-benkirane51-only-20261006.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='proof'},ensure_ascii=False))

if __name__=='__main__':main()
