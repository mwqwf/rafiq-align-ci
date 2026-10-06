"""Read-only complete source-identity scan; no audio, promotion or bucket writes."""
import argparse,datetime,gzip,hashlib,io,json,re,time
from pathlib import Path
import promote as P

MAX_INDEX_BYTES=2*1024*1024
MAX_JSON_BYTES=32*1024*1024

def read_object(client,bucket,key,limit):
    response=client.get_object(Bucket=bucket,Key=key);body=response['Body']
    try:data=body.read(limit+1)
    finally:body.close()
    if len(data)>limit:raise ValueError('object exceeds bounded read')
    return data,response.get('ETag')

def check_index(key,raw,cat):
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:decoded=stream.read(MAX_JSON_BYTES+1)
    if len(decoded)>MAX_JSON_BYTES:raise ValueError('decoded index exceeds bound')
    idx=json.loads(decoded);riwaya,rid=key.split('/')[1:];rid=rid[:-3]
    if (idx.get('riwaya'),idx.get('reciterId'))!=(riwaya,rid):raise ValueError('key/index identity mismatch')
    if not cat.get(riwaya):raise ValueError('riwaya catalog unavailable')
    rows=idx.get('entries')
    if not isinstance(rows,list):raise ValueError('entries unavailable')
    refs=P.catalog_source_refs(idx)
    errors=[]
    if any(not isinstance(e.get('fileRef'),str) or not e['fileRef'].startswith(('https://','http://')) for e in rows):errors.append('non-http or missing audio reference')
    why=P.catalog_gate(idx,cat)
    if why:errors.append(why)
    return {'key':key,'sha256':hashlib.sha256(raw).hexdigest(),'entriesScanned':len(rows),'surahsScanned':len(refs),'declaredAlternateSurahs':sorted((idx.get('sourceBySurah') or {}),key=int),'ok':not errors,'errors':errors}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);a=ap.parse_args()
    out=(P.ROOT/a.out).resolve();allowed=(P.ROOT/'ops/out').resolve()
    if out.parent!=allowed or out.suffix!='.json' or out.exists():raise SystemExit('new ops/out JSON required')
    client,bucket=P.s3();start=time.monotonic()
    raw,cat_etag=read_object(client,bucket,P.CATALOG_KEY,4*1024*1024);data=json.loads(raw)
    cat={r['id']:{x['id']:x for x in r.get('reciters',[])} for r in data.get('riwayat',[])}
    if not cat:raise SystemExit('catalog unavailable; no identity success inferred')
    keys=[]
    for page in client.get_paginator('list_objects_v2').paginate(Bucket=bucket,Prefix='timings/'):
        keys.extend(x['Key'] for x in page.get('Contents',[]) if re.fullmatch(r'timings/[a-z_]+/[A-Za-z0-9_]+\.jz',x['Key']))
        if len(keys)>240:raise SystemExit('index population exceeds bound')
    if len(keys)!=180 or len(set(keys))!=180:raise SystemExit('expected exactly180 current indexes')
    report={'kind':'complete-catalog-source-identity-audit','timestampUtc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'catalogSha256':hashlib.sha256(raw).hexdigest(),'catalogReadEtag':cat_etag,'sourceRegistrySha256':hashlib.sha256(P.SOURCE_OVERRIDES.read_bytes()).hexdigest(),'sourceScanVersion':1,'readOnly':True,'audioMeasured':False,'qualityClaim':False,'rows':[],'errors':[]}
    etags={}
    for key in sorted(keys):
        if time.monotonic()-start>1200:raise SystemExit('bounded audit deadline reached')
        try:
            raw,etag=read_object(client,bucket,key,MAX_INDEX_BYTES);etags[key]=etag
            row=check_index(key,raw,cat)
        except Exception as exc:row={'key':key,'ok':False,'errors':[type(exc).__name__]}
        report['rows'].append(row)
    if client.head_object(Bucket=bucket,Key=P.CATALOG_KEY).get('ETag')!=cat_etag:report['errors'].append('catalog changed during audit')
    for row in report['rows']:
        key=row['key']
        if key in etags and client.head_object(Bucket=bucket,Key=key).get('ETag')!=etags[key]:row['ok']=False;row['errors'].append('index changed during audit')
    report['summary']={'indexes':len(report['rows']),'passed':sum(r['ok'] for r in report['rows']),'failed':sum(not r['ok'] for r in report['rows']),'entriesScanned':sum(r.get('entriesScanned',0) for r in report['rows'])}
    report['ready']=not report['errors'] and not report['summary']['failed'];report['elapsedSeconds']=round(time.monotonic()-start,2)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'path':a.out,'ready':report['ready'],'summary':report['summary']},ensure_ascii=False))
    return 0 if report['ready'] else 2

if __name__=='__main__':raise SystemExit(main())
