"""Bound the recovered Najm endpoint to verified decoded samples, not MP3 header.

This fixes 26 ms of out-of-file timing data. It does not change decoder policy,
quality thresholds, confidence, or any other entry. Fresh final-SHA QA required.
"""
import copy,gzip,hashlib,json,math,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_registered_candidate as C
import stage_transform as T
import run as R
ROOT=Path(__file__).resolve().parents[2]
PARENT='d14fedebbae69f2e29b83d5c081e72214d532fa4a6efb4d094252a9e98a57342'
SOURCE='60b8e8341a40671d93beda8dd5b1ce3d1485b1ff32f219d582871aaf1d7988c5'
def read(path,sha,packed=False):
 b=(ROOT/path).read_bytes();C.require(hashlib.sha256(b).hexdigest()==sha,'input changed: '+path)
 return json.loads(gzip.decompress(b) if packed else b)
def main():
 old=read('ops/source-repair/candidates/codex-darweez-s53-20261006.jz','62a5bb349f0a962fc707f09c9dd366339c514bb7db57786c390de8833856cc0b',True)
 parent=read('ops/source-repair/parents/codex-hafs-darweez-d14fedeb.jz',PARENT,True)
 evidence=read('ops/out/codex-repair-boundaries-37393561427-reports.json','46d3efdb3e6d6b241f2bc8b24e37f5bbe19ad09dc6955e256b791c6a0cd1a9fe')
 tail=next(r for r in evidence if r['reader']=='darweez_tail');opening=next(r for r in evidence if r['reader']=='darweez_opening')
 C.require(tail['measurementComplete'] and opening['measurementComplete'] and not tail['errors'] and not opening['errors'],'incomplete diagnosis')
 a=tail['audio'];d=a['decoded'];other=opening['audio']['decoded']
 C.require(a['download']['sha256']==old['audioSha256'][52]==SOURCE and d['decodedWithoutErrors'] and d['frames']==other['frames']==7794103 and d['fullNativePcmSha256']==other['fullNativePcmSha256'],'source/decode mismatch')
 eof=math.floor(d['frames']*1000/16000)
 ends=[m['rawEntries'][-1]['endMs'] for m in tail['measurements']]
 C.require(len(ends)==4 and max(ends)<eof==487131,'terminal speech outside file')
 c=copy.deepcopy(old);last=next(e for e in c['entries'] if e['ayahId']=='53:62')
 C.require(last['endMs']==487157,'unexpected old endpoint');before=copy.deepcopy(last);last['endMs']=eof
 C.require([e for e in old['entries'] if e['ayahId']!='53:62']==[e for e in c['entries'] if e['ayahId']!='53:62'],'unrelated entry changed')
 c['transform']['decodedEofRepair']={'sourceSha256':SOURCE,'reportSha256':'46d3efdb3e6d6b241f2bc8b24e37f5bbe19ad09dc6955e256b791c6a0cd1a9fe','decodedFrames':d['frames'],'sampleRateHz':16000,'previousEndMs':before['endMs'],'endMs':eof,'forcedTerminalEndsMs':ends,'qualityClaim':False,'reason':'Header duration exceeded actual samples; fix data, retain strict decoder gate.'}
 c['transform']['entriesSha256']=T.entries_sha(c['entries'])
 c['transform']['movedEntries']=T.entry_change_counts(parent['entries'],c['entries'])[0]
 C.require(not T.promote.index_gate(c,parent=parent,parent_sha=PARENT),'index gate')
 fatal,warnings,_=R.structural(c,'timings/hafs/darweez.jz',False);C.require(not fatal,str(fatal))
 path='ops/source-repair/candidates/codex-darweez-s53-decoded-eof-20261006.jz'
 b=gzip.compress(json.dumps(c,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode(),mtime=0)
 out=ROOT/path
 if out.exists():C.require(out.read_bytes()==b,'candidate changed')
 else:out.write_bytes(b)
 report={'path':path,'sha256':hashlib.sha256(b).hexdigest(),'parentSha256':PARENT,'proof':c['transform']['decodedEofRepair'],'structuralFatal':fatal,'structuralWarnings':warnings,'qualityChecks':'pending'}
 (ROOT/'ops/out/codex-darweez-decoded-eof-repair-20261006.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()
