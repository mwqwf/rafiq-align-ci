#!/usr/bin/env python3
# chain.py <name> <rows.txt> <parent_key> <riw> <url> <live8> <batches-json> [start_idx]
# يطلق دفعات ctc_splice heard تسلسلاً، كلٌّ فوق ناتج سابقتها، ويطبع مفتاح الناتج.
import sys,json,subprocess,time,re,datetime,os
S="/tmp/claude-0/-home-user/06b0cdc4-1efe-58b9-bd35-06b0a18e1af5/scratchpad"; B=S+"/b1"
name,rows,parent,riw,url,live8,bj=sys.argv[1:8]; batches=json.loads(open(bj).read())
rid=parent.split("/")[-1].split(".")[0]
def sh(c): return subprocess.run(c,shell=True,capture_output=True,text=True).stdout
def log(m): open(f"{S}/{name}_chain.log","a").write(f"{datetime.datetime.utcnow():%H:%MZ} {m}\n")
for i,surs in enumerate(batches):
    tag=f"{name}B{i+1}"
    resume=os.environ.get("RESUME_RUN") if i==0 else None
    while not resume:
        c=datetime.datetime.utcnow()-datetime.timedelta(hours=24); tot=0
        for s_ in ("in_progress","queued","pending"):
            try: tot+=int(sh(f"gh api 'repos/mwqwf/rafiq-align-ci/actions/runs?status={s_}&per_page=1' --jq .total_count").strip() or 99)
            except: tot+=99
        if tot<20: break
        time.sleep(60)
    cmd=sh(f"python3 {B}/gen.py {rows} {parent} {riw} '{url}' {tag} {','.join(map(str,surs))} {live8}")
    t0=datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    if resume: t0=os.environ["RESUME_T0"]; m=re.match(r"(\d+)",resume); o=None
    else:
        o=sh(f"{B}/put.sh {tag} '{cmd.strip()}' 2>/dev/null").split()[0]
        sh(f"WMAX=400 {B}/wait.sh {o}")
        m=re.search(r"runs/(\d+)",sh(f"{B}/rd.sh {o}"))
    if not m: log(f"{tag} لا رقم تشغيل: {sh(f'{B}/rd.sh {o} | head -5')}"); sys.exit(2)
    run=m[1]; open(f"{S}/pH1mine.txt","a").write(run+"\n"); log(f"{tag} أُطلق {run} فوق {parent}")
    while True:
        st=sh(f"gh api repos/mwqwf/rafiq-align-ci/actions/runs/{run} --jq '.status+\" \"+(.conclusion//\"\")'").strip()
        if st.startswith("completed"): break
        time.sleep(60)
    log(f"{tag} انتهى {st}")
    bo=sh(f"{B}/put.sh {tag}bw '{json.dumps({'action':'tool','tool':'index_qa/bucket_watch.py','args':['--since',t0]})}' 2>/dev/null").split()[0]
    sh(f"WMAX=60 {B}/wait.sh {bo}"); out=sh(f"{B}/rd.sh {bo}")
    ks=re.findall(rf"timings-staging/{riw}/{rid}\.[0-9a-f]{{8}}\.jz",out)
    if not ks:
        log(f"{tag} لا مفتاح جديد ({st}) surahs={surs}")
        if os.environ.get("SKIPFAIL"): continue
        sys.exit(3)
    parent=ks[-1]; log(f"{tag} ⇒ {parent}")
log("CHAIN_DONE "+parent)
