import sys,re
cur=None;D={}
for l in sys.stdin:
    m=re.match(r'── س(\d+) · آيات (\d+).*منحرفة (\d+)',l)
    if m: cur=int(m[1]);D[cur]=[];continue
    m=re.match(r'س(\d+): (.*)',l)
    if m: D[int(m[1])]=m[2];continue
    m=re.match(r'\s+(\d+):(\d+)\tpub=(\d+)\theard=(\d+)\tq=([\d.]+)\tdev=(-?\d+)',l)
    if m and cur: D[cur].append((int(m[2]),round(int(m[6])/1000,1)))
for s,r in sorted(D.items()):
    print(s, r if isinstance(r,str) else (len(r),r[:14]))
