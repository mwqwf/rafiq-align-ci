"""Read-only reconciliation of delivered packages against actual public indexes."""
import concurrent.futures,gzip,hashlib,json,sys,urllib.request
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ci_fleet'))
from emit_probe_map import payload_lines
BASE='https://pub-2c2e1dcd92e84a2898820dd38d3e09e6.r2.dev/'
def get(key):
 with urllib.request.urlopen(urllib.request.Request(BASE+key,headers={'User-Agent':'QuranRafiq-catalog-reconciliation/1'}),timeout=120) as r:
  b=r.read(8*1024*1024+1)
  if len(b)>8*1024*1024:raise ValueError('oversized public object')
  if r.headers.get('Content-Length') and len(b)!=int(r.headers['Content-Length']):raise ValueError('incomplete public object')
  return b
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 inputs={k:get(k) for k in ('timings/manifest.json','packages/catalog.json','catalog/reciters.json')}
 manifest,packages,reciters=[json.loads(inputs[k]) for k in inputs]
 rows=manifest['indexes'];ps=packages['packages']
 if len(rows)!=180 or not ps:raise ValueError('unexpected population; no empty success')
 pmap={p['files'][0]['key']:p for p in ps if p.get('kind')=='timing_index' and len(p.get('files',[]))==1}
 if len(pmap)!=sum(p.get('kind')=='timing_index' for p in ps):raise ValueError('duplicate or malformed timing package')
 cmap={f"timings/{r['id']}/{x['id']}.jz":x for r in reciters['riwayat'] for x in r['reciters']}
 def check(m):
  key=f"timings/{m['riwaya']}/{m['reciterId']}.jz";b=get(key);idx=json.loads(gzip.decompress(b));actual=sha(b)
  if idx['riwaya']!=m['riwaya'] or idx['reciterId']!=m['reciterId']:raise ValueError('identity mismatch '+key)
  p=pmap.get(key);f=p['files'][0] if p else {};c=cmap.get(key,{})
  return {'key':key,'liveSha256':actual,'liveBytes':len(b),'entries':len(idx['entries']),'missing':(idx.get('missing')or{}).get('count'),'manifestMatches':m.get('sha256')==actual,'packagePresent':bool(p),'packageSha256':f.get('sha256'),'packageMatches':f.get('sha256')==actual and f.get('bytes')==len(b),'previousPackageCertified':(p or {}).get('quality',{}).get('ayahCertified'),'reciterCertified':c.get('ayahCertified'),'reciterCoverage':c.get('ayahCoverage')}
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(check,rows))
 report={'schema':1,'readOnly':True,'productionChanged':False,'inputsSha256':{k:sha(b) for k,b in inputs.items()},'indexes':results,'stalePackages':[r['key'] for r in results if not r['packageMatches']],'manifestMismatch':[r['key'] for r in results if not r['manifestMatches']],'previouslyCertifiedNowUncertified':[r['key'] for r in results if r['previousPackageCertified'] and not r['reciterCertified']],'packageWithoutLiveIndex':sorted(set(pmap)-{r['key'] for r in results})}
 for line in payload_lines(report,'PUBLIC_CATALOG_RECONCILE'):print(line,flush=True)
if __name__=='__main__':main()
