"""Read-only native PCM measurement of a pause located by free CTC evidence.

Choose the midpoint of the longest strict quiet interval, independently of any
heard-gate threshold. No timing is written and no model inference is repeated.
"""
import hashlib,json,math,os,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import final_verse_free_batch as B
S=B.S
SOURCE={'surah':69,'riwaya':'hafs','url':'https://server6.mp3quran.net/balilah/069.mp3','sha256':'9fa2851995b76495854440c097a1e3f1834ea40d58b3bb09e982b13fa09ea6f5','requestedWindowSeconds':[274,277]}
RAW_SHA='11c923f6e8ee05f46c25317c0a61f05f8750cf4d025f9040c6b807379a1a6e22'
def quiet_intervals(rows,minimum_frames=12):
 intervals=[];start=None
 for n,row in enumerate(rows+[{'quiet':False}]):
  if row['quiet'] and start is None:start=n
  elif not row['quiet'] and start is not None:
   if n-start>=minimum_frames:intervals.append((rows[start]['startMs'],rows[n-1]['endMs']))
   start=None
 return intervals

def main():
 import gzip,numpy as np
 rep={'schema':1,'kind':'native-quiet-pause-diagnostic','measurementComplete':False,'qualityClaim':False,'productionChanged':False,'source':SOURCE,'errors':[],'boundaryEvidenceSha256':RAW_SHA,
      'policy':{'rmsMaximumDbfs':-50,'peakMaximumDbfs':-40,'frameMs':10,'minimumQuietMs':120,'phonemeSafetyMs':100,'selection':'midpoint of longest contiguous interval, both native channels quiet'},
      'provenance':{'runId':os.environ.get('GITHUB_RUN_ID'),'runSha':os.environ.get('GITHUB_SHA'),'toolSha256':S.sha_file(__file__)}}
 try:
  b=(B.ROOT/'ops/out/codex-repair-boundaries-37393561427-complete.json.gz').read_bytes();B.require(hashlib.sha256(b).hexdigest()==RAW_SHA,'free evidence changed')
  evidence=json.loads(gzip.decompress(b));times=[]
  report_bytes=(B.ROOT/'ops/out/codex-repair-boundaries-37393561427-reports.json').read_bytes()
  B.require(hashlib.sha256(report_bytes).hexdigest()=='46d3efdb3e6d6b241f2bc8b24e37f5bbe19ad09dc6955e256b791c6a0cd1a9fe','vocabulary evidence changed')
  report=next(r for r in json.loads(report_bytes) if r['reader']=='balilah26')
  vocab=next(m['vocabulary'] for m in report['models'] if m['name']=='quran')
  for rec in evidence:
   p=rec['payload'];q=p.get('rawChunk',{})
   if p.get('sourceSha256')!=SOURCE['sha256'] or p.get('model')!='quran' or q.get('chunk')!=2:continue
   # The two source-pinned free paths locate previous terminal sukun and next waw.
   g=q['frameTiming'];center=lambda f:1000*(q['absoluteInputStartSeconds']+(g['firstFrameCenterSample']+f*g['strideSamples'])/16000)
   B.require(q['absoluteInputStartSeconds']==273 and 'وَلَمْ أَدْرِ' in q['text'],'unexpected word context')
   prev=next(t for t in q['argmaxRuns'] if t[0]==vocab['ْ'] and t[1] in (65,66))
   nxt=next(t for t in q['argmaxRuns'] if t[0]==vocab['و'] and t[1]==155)
   times.append({'channel':p['channel'],'previousTokenMs':center(prev[2]-1),'nextTokenMs':center(nxt[1]),'rawPartSha256':rec['sha256']})
  B.require({t['channel'] for t in times}=={'native-1','native-2'},'both native free paths required')
  lo=max(t['previousTokenMs'] for t in times)+100;hi=min(t['nextTokenMs'] for t in times)-100
  rep['phonemeContext']=times;rep['inspectionRangeMs']=[lo,hi]
  with tempfile.TemporaryDirectory(prefix='balilah-pause-',dir=os.environ.get('RUNNER_TEMP')) as tmp:
   p=Path(tmp)/'source.mp3';receipt=S.metadata.fetch(SOURCE['url'],p,limit=B.MAX_SOURCE_BYTES)
   B.require(receipt['sha256']==SOURCE['sha256'],'source changed');c,proof=B.decode(p,SOURCE)
   channels={k:np.frombuffer(v,dtype='<i2').astype(np.float64)/32768 for k,v in c.channels().items()}
   B.require(set(channels)=={'native-1','native-2'},'native stereo required')
   rep['audio']={'download':receipt,**proof};rows=[]
   for start in range(math.ceil(lo/10)*10,math.floor(hi/10)*10,10):
    vals={}
    for name,x in channels.items():
     a=int(round((start-274000)*16));w=x[a:a+160];B.require(len(w)==160,'partial frame')
     rms=float(np.sqrt(np.mean(w*w)));peak=float(np.max(np.abs(w)))
     vals[name]={'rms':rms,'peak':peak,'rmsDbfs':20*math.log10(max(rms,1e-12)),'peakDbfs':20*math.log10(max(peak,1e-12))}
    rows.append({'startMs':start,'endMs':start+10,'channels':vals,'quiet':all(v['rms']<=10**(-50/20) and v['peak']<=10**(-40/20) for v in vals.values())})
   rep['frames']=rows;intervals=quiet_intervals(rows);rep['quietIntervalsMs']=intervals
   B.require(intervals,'no verified quiet interval; do not move boundary')
   selected=max(intervals,key=lambda ab:(ab[1]-ab[0],-ab[0]));rep['selectedQuietIntervalMs']=selected
   rep['proposedBoundaryMs']=(selected[0]+selected[1])//2
   B.require(S.sha_file(p)==SOURCE['sha256'],'source changed after analysis')
  rep['measurementComplete']=True
 except Exception as exc:rep['errors'].append({'type':type(exc).__name__,'message':str(exc)[:240]})
 finally:S.emit(rep,'BALILAH_PAUSE_REPORT')
 return 0 if rep['measurementComplete'] else 1
if __name__=='__main__':raise SystemExit(main())
