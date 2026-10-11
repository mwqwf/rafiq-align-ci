#!/bin/bash
# fin.sh <key> <old sha8> "<ملخّص>" — النصف الثاني من go.sh: انتظار الموجة1 ثمّ الأحكام ثمّ الترقية
P=/tmp/claude-0/-home-user/655bf1da-3ade-5c39-b73e-f25874555b84/scratchpad/pF
k=$1; old=$2; summ=$3; fn=$(basename $k); r=${fn%%.*}; h=$(echo $fn|cut -d. -f2); L=$P/fin_$r.log
exec >$L 2>&1
for i in $(seq 1 400); do s=0; for st in in_progress queued; do n=$(gh api "repos/mwqwf/rafiq-align-ci/actions/runs?status=$st&per_page=100" --jq "[.workflow_runs[]|select(.display_title|contains(\"$h\"))]|length"); s=$((s+n)); done; [ $s = 0 ] && break; sleep 30; done
echo "موجة1 انتهت"
out=$(WMAX=60 $P/rv.sh $k); echo "$out" | cut -c1-500
echo "$out" | grep -q "cen.txt.*حارسُ الإحصاء: ✅" || { echo "⛔ إحصاء"; exit 2; }
echo "$out" | grep -q "heard.txt.*✅ يمرّ" || { echo "⛔ سماع"; exit 2; }
echo "$out" | grep -q "pool.txt.*مقبول" || { echo "⛔ ملوح"; exit 2; }
echo "$out" | grep -q '"lateConfirmed": \[\]\|"lateConfirmed": null' || { echo "⛔ مطالع"; exit 2; }
echo "$out" | grep -q '"swallowed": \[\]' || { echo "⛔ ابتلاع"; exit 2; }
echo "الأحكام ✅ → ترقية"
$P/prom.sh $k $old "$summ" | grep -E "الحيّ|↑ timings/|جُمّد|⛔"
echo "انتهى"
