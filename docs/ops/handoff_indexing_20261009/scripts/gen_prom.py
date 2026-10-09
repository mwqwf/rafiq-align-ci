# gen_prom.py <hhmm> <staging key> <live sha8> <ملخّص> — أوامر الترقية P1..P4 في fixD_promote
import json,sys
hhmm,key,old,summ=sys.argv[1:5]
out="/tmp/claude-0/-home-claude/73343a78-67de-5d83-95ae-5c563459823a/scratchpad/fixD_promote"
riw,fn=key.split("/")[1],key.split("/")[2]; rid,sha8=fn.rsplit(".",2)[0],fn.rsplit(".",2)[1]
tgt=f"timings/{riw}/{rid}.jz"
reason=f"fixD: ترقيةُ {sha8} — {summ}؛ اجتاز البنية والمطالع بالشاهد الحتميّ والأملاح والإحصاء والتشخيص وبوّابة السماع وfull_audit"
c={"P1_unfreeze":{"action":"tool","tool":"index_qa/promote.py","args":["--unfreeze",tgt,"--reason",reason]},
   "P2_promote":{"action":"tool","tool":"index_qa/promote.py","args":["--only",key,"--yes"]},
   "P3_refreeze_new":{"action":"tool","tool":"ci_fleet/refreeze.py","args":[tgt,sha8,f"fixD: تجميد بعد ترقية {sha8}"]},
   "P4_refreeze_old":{"action":"tool","tool":"ci_fleet/refreeze.py","args":[tgt,old,f"fixD: إعادة تجميد المنشور {old} إن رُدّت الترقية — لا هدفَ مفتوح"]}}
for n,v in c.items(): json.dump(v,open(f"{out}/20261009_{hhmm}_fixD_{rid}_{n}.json","w"),ensure_ascii=False)
print("ok",rid,sha8,"old",old)
