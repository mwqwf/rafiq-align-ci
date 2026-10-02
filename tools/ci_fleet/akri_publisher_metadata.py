#!/usr/bin/env python3
"""Public publisher metadata only; never download, modify or promote recordings."""
import datetime,json,subprocess,sys
from pathlib import Path
subprocess.run([sys.executable,"-m","pip","install","--quiet","yt-dlp"],check=True)
targets=["https://www.youtube.com/watch?v=KzuP7DQkXdI","https://www.youtube.com/watch?v=wrwvoeI81Q4","scsearch20:مروان العكري النور","scsearch20:Marwan Alakri Noor"]
results=[]
for target in targets:
 row={"target":target,"candidateOnly":True}
 cmd=[sys.executable,"-m","yt_dlp","--skip-download","--flat-playlist","--dump-single-json","--no-warnings","--socket-timeout","15","--retries","1",target]
 try:
  p=subprocess.run(cmd,text=True,capture_output=True,timeout=90)
  row["rc"]=p.returncode
  if p.returncode==0:
   d=json.loads(p.stdout); items=d.get("entries") or [d]
   row["items"]=[{k:x.get(k) for k in ("id","title","duration","webpage_url","url","uploader","channel","license","description")} for x in items if x]
   for item in row["items"]:
    if isinstance(item.get("description"),str):item["description"]=item["description"][:1000]
  else:row["error"]=p.stderr[-2000:]
 except Exception as e:row["error"]=str(e)
 results.append(row)
result={"timestampUtc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"kind":"documented-public-publisher-metadata","results":results,"productionChanged":False,"audioDownloaded":False,"titlesAndDurationsAreNotIdentityOrCompletenessProof":True}
dest=Path("ops/out/akri-publisher-metadata-20261002.json");dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({"output":str(dest),"targets":len(targets),"successfulMetadata":sum(x.get("rc")==0 for x in results),"productionChanged":False},ensure_ascii=False))
