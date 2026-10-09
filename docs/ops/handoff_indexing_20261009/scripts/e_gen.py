import json,re,sys,time
S='/tmp/claude-0/-home-claude/73343a78-67de-5d83-95ae-5c563459823a/scratchpad'
W=S+'/wtE'
plan=json.load(open(S+'/e_plan.json'))
tmpl={}
for l in open(W+'/ops/out/20261009_1400_fixE_src_all.txt',encoding='utf-8'):
    m=re.match(r'✅ (\w+)/(\w+)\t(\S+)',l)
    if m: tmpl[m.group(2)]=m.group(3)
def hb(rid,surahs=None,tag='hb'):
    o=[p for p in plan if p['rid']==rid][0]
    ss=surahs or o['surahs']
    t=time.strftime('%Y%m%d_%H%M',time.gmtime())
    f=f"{W}/ops/commands/{t}_fixE_{tag}_{rid}.json"
    json.dump({"action":"dispatch","workflow":"heard_batch.yml","inputs":{"parent":o['key'],"url_template":tmpl[rid],"riwaya":o['riw'],"surahs":",".join(map(str,ss)),"shards":"6","reason":f"fixE (proofZ): كبس مرشّح بمسح المدد في {rid} — السور {len(ss)} تُقاس بخريطة السماع قبل أن تُمسّ"}},open(f,'w'),ensure_ascii=False)
    return f
if __name__=='__main__':
    for r in sys.argv[1:]: print(hb(r))
