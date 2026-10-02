#!/usr/bin/env python3
"""Read-only additional publisher discovery; no alignment, audio changes or storage writes."""
import concurrent.futures, datetime, html, json, re, urllib.parse, urllib.request
from pathlib import Path
UA={"User-Agent":"Mozilla/5.0 (Mushafak verified-source research)"}
QUERIES=[
 '"مروان العكري" "النور" "كاملة"',
 '"مروان العكري" "النور" "62"',
 '"مروان العكري" "النور" soundcloud',
 '"Marwan Alakri" "Nur"',
 '"Marwan Al-Akri" "Noor"',
 '"مروان العكري" "النور" "2019"',
 '"مروان العكري" "النور" "2024"',
]
def get(url):
 with urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=25) as r:
  return r.status,r.read(2500000).decode("utf8","replace")
def search(item):
 engine,q=item
 url=("https://www.google.com/search?q=" if engine=="google" else "https://www.bing.com/search?q=")+urllib.parse.quote(q)
 result={"engine":engine,"query":q,"url":url}
 try:
  status,s=get(url);result["status"]=status
  links=[]
  for raw in re.findall(r'href=["\']([^"\']+)["\']',s):
   u=html.unescape(raw)
   if u.startswith("/url?"):u=urllib.parse.parse_qs(urllib.parse.urlsplit(u).query).get("q",[""])[0]
   if u.startswith("http") and not any(d in urllib.parse.urlsplit(u).netloc for d in ("google.","bing.","microsoft.","gstatic.","googleusercontent.")):
    if u not in links:links.append(u)
  result["links"]=links[:35]
  result["textExcerpt"]=re.sub(r"<[^>]*>"," ",s)[:6000]
  result["candidateOnly"]=True
 except Exception as e:result["error"]=str(e)
 return result
def archive(item):
 ident=item
 result={"identifier":ident}
 try:
  status,s=get("https://archive.org/metadata/"+urllib.parse.quote(ident))
  doc=json.loads(s); md=doc.get("metadata",{})
  result["metadata"]={k:md.get(k) for k in ("title","creator","description","licenseurl")}
  result["files"]=[{k:f.get(k) for k in ("name","size","length","md5","sha1","format","source")} for f in doc.get("files",[]) if f.get("name","").lower().endswith((".mp3",".ogg",".m4a")) and (re.search(r"(^|[^0-9])0?24([^0-9]|$)",f["name"]) or any(w in f["name"].lower() for w in ("noor","nur","النور")))]
  result["candidateOnly"]=True
 except Exception as e:result["error"]=str(e)
 return result
ids=["dhikr-alhuda-marwan-alakri-qaloon","001-al-fatihah_20230314_1034","MarwanAlakri","Marwann-Alakri","n2-mp-3_20230516nnnnnn"]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 web=list(pool.map(search,[(e,q) for e in ("google","bing") for q in QUERIES]))
 ar=list(pool.map(archive,ids))
result={"timestampUtc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"kind":"additional-independent-read-only-source-discovery","web":web,"archive":ar,"productionChanged":False,"canonicalTextChanged":False,"audioDownloaded":False,"candidateTitlesAreNotIdentityOrCompletenessProof":True}
dest=Path("ops/out/akri-independent-search-20261002-0448.json")
dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({"output":str(dest),"webRequests":len(web),"successfulWeb":sum(r.get("status")==200 for r in web),"archiveItems":len(ar),"candidateAudioFiles":sum(len(r.get("files",[])) for r in ar),"productionChanged":False},ensure_ascii=False))
