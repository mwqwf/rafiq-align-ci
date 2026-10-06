"""Recover prior verified bytes for Haaqqah, repair its measured clipped ending.

The old heard rejection remains in provenance. Never shift verse 26 merely to
pass that rejection: both models and free emissions support its existing start.
New final-SHA quality and float32 heard gates are mandatory.
"""
import base64
import copy
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys
import unicodedata
sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_registered_candidate as C
import stage_transform as T
import run as R
ROOT=Path(__file__).resolve().parents[2]
PARENT='f1b40abe72f4f85bd41cc87166f2cf8785960c1e267f09816b99532851812207'
OLD='26fcdd889052efeb863782dc31b8c9d41db19b33f9908da855e076226e759ca2'
SOURCE='9fa2851995b76495854440c097a1e3f1834ea40d58b3bb09e982b13fa09ea6f5'
TAIL='7fbc87cb7170153cfc0aa54c699c4e04ed168611faf3411b4f800e197410dc6d'
RAW='85b1afe86ce00f4196112d69e8152f88e4d309e861caa3440722980563c812da'
BOUND='46d3efdb3e6d6b241f2bc8b24e37f5bbe19ad09dc6955e256b791c6a0cd1a9fe'


def read(path,sha,packed=False):
    b=(ROOT/path).read_bytes();C.require(hashlib.sha256(b).hexdigest()==sha,'input changed: '+path)
    return json.loads(gzip.decompress(b) if packed else b)


def main():
    parent=read('ops/source-repair/parents/codex-hafs-balilah-f1b40abe.jz',PARENT,True)
    export=json.loads((ROOT/'ops/out/codex-old-balilah-26fcdd88-20261006.json').read_bytes())
    raw=base64.b64decode(export['gzipBase64'],validate=True)
    C.require(len(raw)==export['bytes'] and hashlib.sha256(raw).hexdigest()==export['sha256']==OLD,'prior candidate changed')
    old=json.loads(gzip.decompress(raw)); rows=[e for e in old['entries'] if e['ayahId'].startswith('69:')]
    C.require([e['ayahId'] for e in rows]==[f'69:{n}' for n in range(1,53)],'incomplete historical surah')
    C.require(old['audioSha256'][68]==parent['audioSha256'][68]==SOURCE,'source mismatch')
    C.require(old['reciterId']==parent['reciterId']=='balilah' and old['riwaya']==parent['riwaya']=='hafs','identity mismatch')
    C.require({e['fileRef'] for e in rows}=={e['fileRef'] for e in parent['entries'] if e['ayahId'].startswith('69:')},'audio reference changed')
    diagnostic=next(r for r in read('ops/out/codex-repair-boundaries-37393561427-reports.json',BOUND) if r['reader']=='balilah26')
    C.require(diagnostic['measurementComplete'] and not diagnostic['errors'],'incomplete verse26 diagnostic')
    targets=[next(e for e in m['rawEntries'] if e['ayahId']=='69:26') for m in diagnostic['measurements']]
    C.require(len(targets)==4 and min(e['conf'] for e in targets)>=.74 and all(e['startMs']==275618 for e in targets),'verse26 diagnosis disagrees')
    C.require(rows[25]['startMs']==275598,'historical verse26 changed')
    tail=next(r for r in read('ops/out/codex-duration-context-37392377734-reports.json',TAIL) if r['reader']=='balilah')
    C.require(tail['measurementComplete'] and not tail['errors'],'incomplete tail diagnostic')
    evidence=read('ops/out/codex-duration-context-37392377734-complete.json.gz',RAW,True)
    vocab={v:k for k,v in next(m['vocabulary'] for m in tail['models'] if m['name']=='quran').items()}
    observations=[]
    for rec in evidence:
        p=rec['payload'];b=json.dumps(p,ensure_ascii=False,separators=(',',':')).encode()
        C.require(len(b)==rec['bytes'] and hashlib.sha256(b).hexdigest()==rec['sha256'],'raw evidence changed')
        if p.get('sourceSha256')!=SOURCE or p.get('model')!='quran' or p.get('rawChunk',{}).get('chunk')!=2:continue
        chunk=p['rawChunk'];text=''.join(c for c in unicodedata.normalize('NFKD',chunk['text']) if unicodedata.category(c)!='Mn')
        C.require(text.rstrip().endswith('العظيم'),'missing freely decoded final word')
        tokens=[r for r in chunk['argmaxRuns'] if r[0]>4]
        letters=[r for r in tokens if unicodedata.category(vocab[r[0]]).startswith('L')]
        C.require(vocab[letters[-1][0]]=='م' and letters[-1][4]>=.95,'weak final consonant')
        g=chunk['frameTiming']
        def center(frame):return 1000*(chunk['absoluteInputStartSeconds']+(g['firstFrameCenterSample']+frame*g['strideSamples'])/16000)
        observations.append({'channel':p['channel'],'rawPartSha256':rec['sha256'],'finalConsonantMs':center(letters[-1][1]),'finalTokenMs':center(tokens[-1][2]-1)})
    C.require({o['channel'] for o in observations}=={'native-1','native-2'},'missing channel evidence')
    qends=[m['rawEntries'][-1]['endMs'] for m in tail['measurements'] if m['model']=='quran']
    end=math.ceil(max(qends+[o['finalTokenMs'] for o in observations])/100)*100+200
    C.require(rows[-1]['endMs']==470164 and end==472500 and end<tail['audio']['decoded']['durationSeconds']*1000,'unexpected terminal repair')
    rows=copy.deepcopy(rows);before=copy.deepcopy(rows[-1]);rows[-1]['endMs']=end
    candidate=copy.deepcopy(parent);replacement={e['ayahId']:e for e in rows}
    candidate['entries']=[replacement.get(e['ayahId'],e) for e in candidate['entries']]
    C.require(len(candidate['entries'])==6236 and [e for e in candidate['entries'] if not e['ayahId'].startswith('69:')]==[e for e in parent['entries'] if not e['ayahId'].startswith('69:')],'unrelated data changed')
    candidate.setdefault('engineBySurah',{})['69']='ctc-heardmap-1'
    if 'lowCount' in candidate:candidate['lowCount']=sum(e.get('confBand')=='LOW' for e in candidate['entries'])
    proof={'kind':'historical-surah-recovery-with-measured-tail','qualityClaim':False,'priorCandidateSha256':OLD,
      'sourceSha256':SOURCE,'boundaryReportSha256':BOUND,'tailReportSha256':TAIL,'tailRawBundleSha256':RAW,
      'terminalBefore':before,'terminalAfter':rows[-1],'terminalFrames':observations,
      'verse26':{'oldStartMs':275598,'fourDiagnosticStartsMs':[e['startMs'] for e in targets],
                 'changed':False,'oldHeardRejection':'69:26 +1.6s; preserved, never bypassed'},
      'limits':['Full final-SHA QA and float32 heard gate required.','No confidence increase.','Prior candidate cannot be promoted as-is; terminal word was clipped.']}
    tr=C.repaired_transform(parent,candidate,[69],PARENT,'timings/hafs/balilah.jz')
    moved,added,removed=T.entry_change_counts(parent['entries'],candidate['entries'])
    C.require(added==removed==0,'entry population changed')
    tr.update(op='ctc_heardmap_splice:69',fromSha256=PARENT,fromKey='timings/hafs/balilah.jz',
      entriesSha256=T.entries_sha(candidate['entries']),parentEntriesSha256=T.entries_sha(parent['entries']),
      movedEntries=moved,addedEntries=added,removedEntries=removed,sameSourceRepair=proof,
      by='build_recovered_balilah_candidate',unpublishedLocalCandidate=True,
      reason='Recover prior Haaqqah timing bytes, retain independently supported verse26, repair clipped final word')
    candidate['transform']=tr
    C.require(not T.promote.index_gate(candidate,parent=parent,parent_sha=PARENT),'index gate failed')
    fatal,warnings,info=R.structural(candidate,'timings/hafs/balilah.jz',False);C.require(not fatal,str(fatal))
    path='ops/source-repair/candidates/codex-balilah-s69-recovered-20261006.jz'
    b=gzip.compress(json.dumps(candidate,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode(),mtime=0)
    out=ROOT/path
    if out.exists():C.require(out.read_bytes()==b,'candidate changed')
    else:out.write_bytes(b)
    report={'path':path,'sha256':hashlib.sha256(b).hexdigest(),'parentSha256':PARENT,'changedEntries':moved,'structuralFatal':fatal,'structuralWarnings':warnings,'proof':proof}
    (ROOT/'ops/out/codex-balilah-recovered-candidate-20261006.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='proof'},ensure_ascii=False))


if __name__=='__main__':main()
