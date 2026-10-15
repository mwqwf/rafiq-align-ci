import sys,re,subprocess
f,surahs=sys.argv[1],set(sys.argv[2].split(','))
by={}
for l in open(f,encoding='utf-8'):
    m=re.match(r'\s+(\d+):(\d+)\t',l)
    if m and m.group(1) in surahs: by.setdefault(m.group(1),[]).append(int(m.group(2)))
out=[]
for s,a in by.items():
    a=sorted(set(a)); st=pr=a[0]
    for x in a[1:]+[None]:
        if x is not None and x==pr+1: pr=x; continue
        out.append(f"{s}:{st}-{pr}"); 
        if x is not None: st=pr=x
print(",".join(out))
