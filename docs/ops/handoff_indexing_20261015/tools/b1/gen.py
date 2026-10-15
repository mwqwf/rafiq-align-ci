import re,json,sys
S="/tmp/claude-0/-home-user/06b0cdc4-1efe-58b9-bd35-06b0a18e1af5/scratchpad"
# gen.py rows.txt parent riw url tag surahs(comma) -> JSON dispatch
rows,parent,riw,url,tag,surs=sys.argv[1:7]; surs=[int(x) for x in surs.split(",")]
cur=None;d={};N={}
for l in open(rows):
    m=re.match(r"── س(\d+) · آيات (\d+)",l)
    if m: cur=int(m[1]);N[cur]=int(m[2]);d[cur]=[];continue
    m=re.match(r"\s+(\d+):(\d+)\t.*\tdev$",l)
    if m and cur: d[cur].append(int(m[2]))
import os
pcs=[]
for s in surs:
    if os.environ.get('FULL'): pcs.append(f'{s}:1-{N[s]}'); continue
    a=sorted(d[s]); groups=[[a[0]]]
    for x in a[1:]:
        if x-groups[-1][-1]<=3: groups[-1].append(x)
        else: groups.append([x])
    for g in groups: pcs.append(f"{s}:{max(1,g[0]-1)}-{min(N[s],g[-1]+1)}")
if os.environ.get('RES'):
    R=json.load(open(os.environ['RES'])); sel=set(surs)
    pcs=[x for x in R['pcs'] if int(x.split(':')[0]) in sel]
live=sys.argv[7] if len(sys.argv)>7 else ""
print(json.dumps({"action":"dispatch","workflow":"ctc_splice.yml","inputs":{"parent":parent,"riwaya":riw,"url_template":url,"surahs":",".join(map(str,surs)),"mode":"heard","rewindow":",".join(pcs),"reason":f"pH1 {tag}: سورٌ منحرفةٌ بقياس السماع على الحيّ {live} — إعادة بنائها من مراسٍ مسموعة"}},ensure_ascii=False))
