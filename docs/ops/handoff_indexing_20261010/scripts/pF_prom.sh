#!/bin/bash
# prom.sh <staging key> <old sha8> "<ملخّص>" — الرباعيّة P1–P4 تحت القفل المشترك
S=/tmp/claude-0/-home-user/655bf1da-3ade-5c39-b73e-f25874555b84/scratchpad
P=$S/pF; k=$1; old=$2; summ=$3
riw=$(echo $k|cut -d/ -f2); fn=$(basename $k); rid=${fn%%.*}; sha8=$(echo $fn|cut -d. -f2); tgt=timings/$riw/$rid.jz
exec 9>$S/promote.lock; flock 9
reason="pF: ترقيةُ $sha8 — $summ؛ اجتاز البنية والمطالع والأملاح الأربعة والإحصاء والتشخيص وبوّابة السماع والتدقيق"
j(){ python3 -c "import json,sys;print(json.dumps(json.loads(sys.argv[1]),ensure_ascii=False))" "$1"; }
mk(){ python3 - "$@" <<'PY'
import json,sys
print(json.dumps({"action":"tool","tool":sys.argv[1],"args":sys.argv[2:]},ensure_ascii=False))
PY
}
# تأكيد المنشور الحيّ
o=$($P/put.sh pre_$rid "$(mk index_qa/dump_state.py timings/manifest.json indexes)" 2>/dev/null | head -1)
WMAX=40 $P/wait.sh $o >/dev/null
live=$($P/rd.sh $o | python3 -c "
import sys,json
t=sys.stdin.read();d=json.loads(t[t.index('{'):])
print([i['sha256'][:8] for i in d['indexes'] if i['reciterId']=='$rid' and i['riwaya']=='$riw'][0])")
echo "الحيّ=$live المتوقَّع=$old"; [ "$live" = "$old" ] || { echo "⛔ الأصل تبدّل — توقّف"; exit 3; }
o1=$($P/put.sh P1_$rid "$(mk index_qa/promote.py --unfreeze $tgt --reason "$reason")" 2>/dev/null | head -1)
WMAX=60 $P/wait.sh $o1 >/dev/null; $P/rd.sh $o1 | grep -E "رُفع|⛔" | cut -c1-120
o2=$($P/put.sh P2_$rid "$(mk index_qa/promote.py --only $k --yes)" 2>/dev/null | head -1)
WMAX=60 $P/wait.sh $o2 >/dev/null
o3=$($P/put.sh P3_$rid "$(mk ci_fleet/refreeze.py $tgt $sha8 "pF: تجميد بعد ترقية $sha8")" 2>/dev/null | head -1)
WMAX=60 $P/wait.sh $o3 >/dev/null
o4=$($P/put.sh P4_$rid "$(mk ci_fleet/refreeze.py $tgt $old "pF: إعادة تجميد $old إن رُدّت الترقية — لا هدفَ مفتوح")" 2>/dev/null | head -1)
WMAX=60 $P/wait.sh $o4 >/dev/null
for f in $o2 $o3 $o4; do echo "-- $f"; $P/rd.sh $f | grep -vE "^\s*$|الذاكرة المحليّة" | tail -6 | cut -c1-260; done
