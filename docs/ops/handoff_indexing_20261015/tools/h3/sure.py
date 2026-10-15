import re,sys
cur=None;mx={};cnt={}
for l in open(sys.argv[1]).read().splitlines():
    m=re.match(r"── س(\d+)",l)
    if m: cur=int(m.group(1));continue
    m=re.match(r"\s+\d+:(\d+)\t.*dev=(-?\d+)\t.*dev$",l)
    if m and cur:
        d=abs(int(m.group(2)));mx[cur]=max(mx.get(cur,0),d);cnt[cur]=cnt.get(cur,0)+1
print(",".join(str(s) for s in sorted(mx) if mx[s]>60000))
