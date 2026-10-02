#!/usr/bin/env python3
"""Read-only native-byte and waveform comparison of one documented alternative."""
import datetime,hashlib,json,os,subprocess,sys,tempfile,urllib.request
from pathlib import Path
os.environ["OPENBLAS_NUM_THREADS"]="1"
subprocess.run([sys.executable,"-m","pip","install","--quiet","numpy","yt-dlp"],check=True)
import numpy as np
candidate="https://soundcloud.com/marwanalakri/an-noor"
reference="https://archive.org/download/n2-mp-3_20230516nnnnnn/024%20%20%D8%B3%D9%88%D8%B1%D8%A9%20%20%20%D8%A7%D9%84%D9%86%D9%88%D8%B1%20%D8%AA%D9%84%D8%A7%D9%88%D8%A9%20%D9%85%D8%B1%D9%88%D8%A7%D9%86%20%D8%A7%D9%84%D8%B9%D9%83%D8%B1%D9%8A%20%D8%A8%D8%B1%D9%88%D8%A7%D9%8A%D8%A9%20%D9%82%D8%A7%D9%84%D9%88%D9%86%20%20%20mp3.mp3"
out={"kind":"independent-native-waveform-source-comparison","candidatePage":candidate,"referenceUrl":reference,"productionChanged":False,"canonicalTextChanged":False,"audioModified":False,"audioPersisted":False}
def native(path):
 p=subprocess.run(["ffmpeg","-v","error","-xerror","-i",str(path),"-vn","-ac","1","-ar","8000","-f","f32le","pipe:1"],capture_output=True,timeout=120,check=True)
 return np.frombuffer(p.stdout,dtype="<f4").copy()
try:
 with tempfile.TemporaryDirectory(prefix="mushafak-akri-native-") as folder:
  folder=Path(folder); rp=folder/"reference.mp3"
  urllib.request.urlretrieve(reference,rp)
  command=[sys.executable,"-m","yt_dlp","--no-playlist","--socket-timeout","20","--retries","1","-f","bestaudio","-o",str(folder/"candidate.%(ext)s"),candidate]
  result=subprocess.run(command,capture_output=True,text=True,timeout=180)
  if result.returncode:raise ValueError(result.stderr[-2000:])
  files=list(folder.glob("candidate.*"))
  if len(files)!=1:raise ValueError("Expected one native candidate file")
  cp=files[0]; a=native(rp);b=native(cp)
  out["reference"]={"bytes":rp.stat().st_size,"sha256":hashlib.sha256(rp.read_bytes()).hexdigest(),"decodedMs":len(a)/8}
  out["candidate"]={"bytes":cp.stat().st_size,"sha256":hashlib.sha256(cp.read_bytes()).hexdigest(),"decodedMs":len(b)/8,"extension":cp.suffix}
  rows=[]
  for ms in [10000,150000,300000,450000,600000,740000]:
   start=ms*8;window=5*8000; x=a[start:start+window].astype(np.float64);x-=x.mean()
   best=(-1,None)
   for lag in range(-1200,1201,4):
    lo=start+lag
    if lo<0 or lo+window>len(b):continue
    y=b[lo:lo+window].astype(np.float64);y-=y.mean()
    den=np.linalg.norm(x)*np.linalg.norm(y)
    corr=float(np.dot(x,y)/den) if den else 0
    if corr>best[0]:best=(corr,lag/8)
   rows.append({"nativeStartMs":ms,"windowMs":5000,"bestCorrelation":best[0],"candidateLagMs":best[1]})
  out["waveforms"]=rows
  out["samePartialRecordingSupported"]=all(x["bestCorrelation"]>.95 for x in rows) and abs(len(a)-len(b))/8<1000
  out["completeReplacementAccepted"]=False
except Exception as e:out["error"]=str(e)
out["timestampUtc"]=datetime.datetime.now(datetime.timezone.utc).isoformat()
dest=Path("ops/out/akri-soundcloud-native-comparison-20261002.json");dest.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(out,ensure_ascii=False))
