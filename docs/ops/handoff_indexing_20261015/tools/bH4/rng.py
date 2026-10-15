import sys,re,json
cur=None;D={}
for l in sys.stdin:
    m=re.match(r'── س(\d+) · آيات (\d+)',l)
    if m: cur=int(m[1]);D[cur]=[int(m[2]),None];continue
    m=re.match(r'\s+(\d+):(\d+)\tpub=',l)
    if m and cur and D[cur][1] is None: D[cur][1]=int(m[2])
print(json.dumps({s:f"{s}:{max(1,v[1]-3)}-{v[0]}" for s,v in D.items()}))
