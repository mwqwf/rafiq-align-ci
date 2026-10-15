#!/usr/bin/env python3
# chain.py <tag> <riw> <rid> <url> <startKey> <steps.json> — يشغّل خطوات ctc_splice متسلسلةً (كلٌّ فوق ناتج السابقة)
# steps: [{"mode":"heard|dualfix","surahs":"2","rewindow":"..."}...]
import json,subprocess,sys,time,re,datetime,os
H=os.path.dirname(os.path.abspath(__file__))
tag,riw,rid,url,key,steps=sys.argv[1:7]; steps=json.load(open(steps))
log=open(f"{H}/chain_{tag}.log","a")
def L(*a):
    print(datetime.datetime.utcnow().strftime("%H:%MZ"),*a,file=log,flush=True)
def sh(c,**k): return subprocess.run(c,shell=True,capture_output=True,text=True,**k)
def put(name,js):
    r=sh(f"{H}/put.sh {name} '{js}'"); return r.stdout.strip().splitlines()[0]
def waitf(o,mx=60): sh(f"WMAX={mx} {H}/wait.sh {o}")
def runid(o):
    r=sh(f"{H}/rd.sh {o}").stdout; m=re.search(r"runs/(\d+)",r); return m.group(1) if m else None
def fleet():
    c=(datetime.datetime.utcnow()-datetime.timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ"); t=0
    for s in ("in_progress","queued","pending"):
        r=sh(f"gh api 'repos/mwqwf/rafiq-align-ci/actions/runs?status={s}&per_page=100' --jq '[.workflow_runs[]|select(.created_at>\"{c}\")]|length'").stdout.strip()
        t+=int(r or 99)
    return t
for n,st in enumerate(steps,1):
    for attempt in (1,2):
        t0=datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        inp={"parent":key,"url_template":url,"riwaya":riw,"surahs":st["surahs"],"mode":st["mode"],"rewindow":st["rewindow"],"reason":f"pH3 {tag} خطوة {n}: {st['mode']} س{st['surahs']} فوق {key.split('.')[-2]}"}
        if st["mode"]=="dualfix": inp["base_key"]=key
        while fleet()>=20: time.sleep(60)
        js=json.dumps({"action":"dispatch","workflow":"ctc_splice.yml","inputs":inp},ensure_ascii=False)
        o=put(f"{tag}_c{n}",js.replace("'","’")); waitf(o,400); rid_=runid(o); L("أُطلقت",n,st["mode"],st["surahs"],rid_)
        while True:
            r=sh(f"gh api repos/mwqwf/rafiq-align-ci/actions/runs/{rid_} --jq '.status+\" \"+(.conclusion//\"\")'").stdout.strip()
            if r.startswith("completed"): break
            time.sleep(45)
        L("انتهت",rid_,r)
        if "success" not in r:
            if attempt==1: L("إعادة محاولة بعد فشل"); continue
            L("⛔ توقّفت السلسلة عند الخطوة",n); sys.exit(1)
        bw=put(f"{tag}_w{n}",json.dumps({"action":"tool","tool":"index_qa/bucket_watch.py","args":["--since",t0,"--max","60"]})); waitf(bw,60)
        out=sh(f"{H}/rd.sh {bw}").stdout
        cands=re.findall(rf"timings-staging/{riw}/{rid}\.([0-9a-f]{{8}})\.jz",out)
        if not cands: L("⛔ لا مرشّح جديد",n); sys.exit(2)
        key=f"timings-staging/{riw}/{rid}.{cands[-1]}.jz"; L("مرشّح",n,key); break
L("اكتملت السلسلة",key)
