#!/bin/bash
# الاستعمال: runbatch.sh <مجلد الأوامر> <الوسم> <وصف>
S=/tmp/claude-0/-home-claude/73343a78-67de-5d83-95ae-5c563459823a/scratchpad; R=$1; T=$2; M=$3
ids=$(ls $R | grep -E "_P[1-4]_" | sed -E "s/^[0-9]+_[^_]+_${T}_(.*)_P[1-4]_.*/\1/" | sort -u)
set -- $ids; n=0
while [ $# -gt 0 ]; do
  n=$((n+1)); d=$S/${T}b_$n; mkdir -p $d
  for k in 1; do [ $# -gt 0 ] || break; mv $R/*_${T}_${1}_P[1-4]_*.json $d/; shift; done
  echo "=== دفعة $n: $(ls $d | sed -E "s/.*${T}_(.*)_P1.*/\1/;t;d" | tr '\n' ' ')"
  $S/p2step.sh $d "$M (دفعة $n)" > $S/${T}b_$n.log 2>&1
  grep -E "جُمّد|الهدف مجمَّد|مجمَّدٌ أصلاً" $S/${T}b_$n.log | cut -c1-110
done
