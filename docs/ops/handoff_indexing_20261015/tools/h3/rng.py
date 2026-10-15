import re,sys
# rng.py <rows file> <surahs,...> => s:a-b لكلّ سورة (أوّل آية منحرفة −1 حتى آخر السورة)
rows=open(sys.argv[1]).read(); want=[int(x) for x in sys.argv[2].split(',')]
cur=None; first={}; n={}
for l in rows.splitlines():
    m=re.match(r"── س(\d+) · آيات (\d+)",l)
    if m: cur=int(m.group(1)); n[cur]=int(m.group(2)); continue
    m=re.match(r"\s+(\d+):(\d+)\t.*\tdev$",l)
    if m and cur: first.setdefault(int(m.group(1)),int(m.group(2)))
print(",".join(f"{s}:{max(1,first[s]-1)}-{n[s]}" for s in want if s in first))
