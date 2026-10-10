#!/bin/bash
# go.sh <staging key> <old sha8> "<ملخّص>" — خطّ كامل: بنية → مطالع+ملوح → موجة1 → أحكام → ترقية
P=/tmp/claude-0/-home-user/655bf1da-3ade-5c39-b73e-f25874555b84/scratchpad/pE
k=$1; old=$2; summ=$3; fn=$(basename $k); r=${fn%%.*}; h=$(echo $fn|cut -d. -f2); L=$P/go_$r.log
exec >$L 2>&1
idle(){ for i in $(seq 1 400); do n=$(gh api "repos/mwqwf/rafiq-align-ci/actions/runs?status=in_progress&per_page=100" --jq "[.workflow_runs[]|select(.display_title|contains(\"$h\"))]|length"; gh api "repos/mwqwf/rafiq-align-ci/actions/runs?status=queued&per_page=100" --jq "[.workflow_runs[]|select(.display_title|contains(\"$h\"))]|length"); s=$(echo $n|tr ' ' '+'); [ $((s)) = 0 ] && return; sleep 30; done; }
o=$($P/put.sh s_$r "{\"action\":\"tool\",\"tool\":\"index_qa/run.py\",\"args\":[\"--struct-only\",\"$k\"]}"|head -1); WMAX=60 $P/wait.sh $o >/dev/null
$P/rd.sh $o | grep -q "بنيوياً سليم" || { echo "⛔ بنية"; exit 1; }
echo "بنية ✅"
op=$($P/put.sh op0_$r "{\"action\":\"dispatch\",\"workflow\":\"openers.yml\",\"inputs\":{\"only\":\"$k\"}}"|head -1)
so=$($P/w2.sh $k "1 2 3 4" 2>/dev/null|grep ops/out); WMAX=80 $P/wait.sh $op $so >/dev/null; sleep 60; idle
echo "مطالع+ملوح انتهت"
wo=$(PAR=${PAR:-false} $P/w1.sh $k 2>/dev/null|grep ops/out); WMAX=120 $P/wait.sh $wo >/dev/null; sleep 60; idle
echo "موجة1 انتهت"
out=$(WMAX=60 $P/rv.sh $k); echo "$out" | cut -c1-400
echo "$out" | grep -q "cen.txt.*حارسُ الإحصاء: ✅" || { echo "⛔ إحصاء"; exit 2; }
echo "$out" | grep -q "heard.txt.*✅ يمرّ" || { echo "⛔ سماع"; exit 2; }
echo "$out" | grep -q "pool.txt.*مقبول" || { echo "⛔ ملوح"; exit 2; }
echo "$out" | grep -q '"lateConfirmed": \[\]\|"lateConfirmed": null' || { echo "⛔ مطالع"; exit 2; }
echo "$out" | grep -q '"swallowed": \[\]' || { echo "⛔ ابتلاع"; exit 2; }
echo "الأحكام ✅ → ترقية"
$P/prom.sh $k $old "$summ" | grep -E "الحيّ|↑ timings/|جُمّد|⛔"
echo "انتهى"
