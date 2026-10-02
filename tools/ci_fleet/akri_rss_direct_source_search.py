#!/usr/bin/env python3
"""Read-only source discovery through RSS and directly documented publishers."""
import base64, concurrent.futures, datetime, html, json, re, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from pathlib import Path
UA={"User-Agent":"Mozilla/5.0"}
def get(url):
 with urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=30) as r:return r.status,r.read(3000000).decode("utf8","replace")
queries=["مروان العكري النور","مروان العكري سورة النور كاملة","Marwan Alakri An Nur","مروان العكري النور soundcloud","مروان العكري النور 2024"]
def rss(q):
 out={"query":q,"engine":"bing-rss"}
 try:
  status,s=get("https://www.bing.com/search?format=rss&q="+urllib.parse.quote(q))
  out["status"]=status
  root=ET.fromstring(s);out["results"]=[{"title":x.findtext("title"),"url":x.findtext("link"),"description":x.findtext("description")} for x in root.findall(".//item")]
 except Exception as e:out["error"]=str(e)
 return out
urls=["https://www.youtube.com/watch?v=KzuP7DQkXdI","https://www.youtube.com/watch?v=wrwvoeI81Q4","https://soundcloud.com/search/sounds?q="+urllib.parse.quote("مروان العكري النور")]
def direct(url):
 out={"url":url,"candidateOnly":True}
 try:
  status,s=get(url);out["status"]=status
  out["title"]=html.unescape((re.search(r"<title>(.*?)</title>",s,re.S)or re.match(r"(.*)",""))[1])
  out["lengthSeconds"]=re.findall(r'"lengthSeconds"\\s*:\\s*"([0-9]+)"',s)[:4]
  out["tracks"]=sorted(set(re.findall(r'https://soundcloud.com/[a-zA-Z0-9_/-]+',s)))[:50]
  if "youtube.com" in url:
   try:
    _,o=get("https://www.youtube.com/oembed?format=json&url="+urllib.parse.quote(url))
    out["publisherMetadata"]=json.loads(o)
   except Exception as e:out["publisherMetadataError"]=str(e)
  plain=re.sub(r"<(script|style)\\b.*?</\\1>","",s,flags=re.S|re.I)
  out["textExcerpt"]=html.unescape(re.sub(r"<[^>]+>"," ",plain))[:2500]
 except Exception as e:out["error"]=str(e)
 return out
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 web=list(pool.map(rss,queries)); publishers=list(pool.map(direct,urls))
out={"timestampUtc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"kind":"rss-and-direct-source-research","search":web,"publishers":publishers,"candidateOnly":True,"canonicalTextChanged":False,"productionChanged":False,"audioDownloaded":False,"previousWebHttp200WasNotSearchEvidence":"Google returned a JavaScript redirect page and Bing links required redirect decoding; no complete-source absence inferred."}
dest=Path("ops/out/akri-rss-direct-search-20261002.json");dest.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({"output":str(dest),"rssRequests":len(web),"parsedRss":sum("results" in x for x in web),"directPublishers":len(publishers)},ensure_ascii=False))
