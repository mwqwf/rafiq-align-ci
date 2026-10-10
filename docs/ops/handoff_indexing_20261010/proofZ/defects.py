import re, subprocess, collections, datetime
C="/tmp/claude-0/-home-user/655bf1da-3ade-5c39-b73e-f25874555b84/scratchpad/proofZ/clone"
OUT="/tmp/claude-0/-home-user/655bf1da-3ade-5c39-b73e-f25874555b84/scratchpad/proofZ_defects.md"
def g(*a): return subprocess.run(["git",*a],cwd=C,capture_output=True,text=True).stdout
g("fetch","-q","origin","main")
files=[f for f in g("ls-tree","--name-only","origin/main","ops/out/heard-pub/").split() ]
per=collections.OrderedDict()
for f in sorted(files):
    t=g("show","origin/main:"+f); run=f.split("/")[-1][:-4]
    m=re.search(r"# heard_pub \d+ · (\S+)",t)
    if not m: continue
    key=m.group(1); d=per.setdefault(key,{"runs":[], "sur":{}, "tot":None})
    d["runs"].append(run)
    for s,n,ay,ms in re.findall(r"س(\d+): انحراف (\d+) \(أقصاها (\d+): ([+-][\d.]+)ث\)",t):
        d["sur"][int(s)]=(int(n),int(ay),float(ms))
    mm=re.search(r"⇒ مقيس (\d+) · منحرف (\d+) · غير مقيس (\d+)",t)
    if mm: d["tot"]=(d["tot"] or (0,0,0)); d["tot"]=tuple(a+int(b) for a,b in zip(d["tot"],mm.groups()))
L=["# عيوب مثبتة بخريطة السماع (proofZ)","",
 f"آخر تحديث {datetime.datetime.utcnow():%Y-%m-%d %H:%MZ}. المعيار: بدء الآية المنشور يخالف أول حرف مسموع (CTC float32، جودة المرساة ≥ 0.5) بأكثر من 1500م.ث ولا أداء مكرر قريباً (تعريف heard_gate نفسه). الدليل: سجل heard_pub لكل تشغيلة في `ops/out/heard-pub/<run>.txt` وخريطة الدلو `state-heard/timings_<رواية>_<قارئ>.jz.json`.",
 "التصنيف: انحراف أقصى فوق 60ث = عيب شبه مؤكد (لا يفسره خطأ قياس بهامش ثوانٍ)؛ بين 1.5 و60ث يحتاج سماعاً عيّنياً.","",
 "| الفهرس | تشغيلات | مقيس | منحرف | غير مقيس | سور منحرفة | أشد انحراف (سورة:آية) |","|---|---|---:|---:|---:|---:|---|"]
rows=[]
for k,d in per.items():
    if not d["tot"] or d["tot"][1]==0: continue
    w=max(d["sur"].items(),key=lambda x:abs(x[1][2]))
    rows.append((d["tot"][1],k,d,w))
for n,k,d,w in sorted(rows,reverse=True):
    L.append(f"| {k} | {','.join(d['runs'])} | {d['tot'][0]} | {d['tot'][1]} | {d['tot'][2]} | {len(d['sur'])} | {w[0]}:{w[1][1]} ({w[1][2]:+.1f}ث) |")
L+=["","## تفصيل السور (أشد آية في كل سورة)",""]
for n,k,d,w in sorted(rows,reverse=True):
    L.append(f"### {k}")
    L.append("، ".join(f"س{s}: {v[0]} آية (أقصاها {v[1]} {v[2]:+.1f}ث)" for s,v in sorted(d["sur"].items())))
    L.append("")
open(OUT,"w").write("\n".join(L))
print(len(rows),"فهرساً منحرفاً")
import os
sec="/tmp/claude-0/-home-user/655bf1da-3ade-5c39-b73e-f25874555b84/scratchpad/proofZ_sweep_section.md"
if os.path.exists(sec):
    open(OUT,"a").write("\n"+open(sec).read())
