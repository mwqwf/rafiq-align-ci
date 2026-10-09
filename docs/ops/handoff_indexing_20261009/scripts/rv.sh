#!/bin/bash
# rv.sh <key> — يطلب أحكام مرشّح ثمّ ينتظرها ويطبعها مختصرة (من نسختي الخاصة)
D=/tmp/claude-0/-home-claude/73343a78-67de-5d83-95ae-5c563459823a/scratchpad/fixD
C=$D/clone; cd $C
k=$1; fn=$(basename $k); r=${fn%%.*}; flat=$(echo $k|tr / _)
d(){ echo "{\"action\":\"tool\",\"tool\":\"index_qa/dump_state.py\",\"args\":[\"state/$flat.$1\",\"verdict\",\"severeRate\",\"sha256\",\"late\",\"lateConfirmed\",\"swallowed\",\"fatal\",\"lateCtcPrecision\"]}"; }
a=(v_${r}_cen "{\"action\":\"tool\",\"tool\":\"index_qa/census_gate_check.py\",\"args\":[\"$k\"]}" v_${r}_heard "{\"action\":\"tool\",\"tool\":\"index_qa/heard_gate.py\",\"args\":[\"$k\"]}" v_${r}_op "$(d openers.json)" v_${r}_pool "{\"action\":\"tool\",\"tool\":\"index_qa/pool_probe.py\",\"args\":[\"$k\"]}")
outs=$($D/put.sh "${a[@]}" 2>/dev/null)
for i in $(seq 1 120); do git fetch -q origin; ok=1; for o in $outs; do git cat-file -e origin/main:$o 2>/dev/null || ok=0; done; [ $ok = 1 ] && break; sleep 10; done
echo "== $k"; for o in $outs; do echo "-- $(basename $o): $(git show origin/main:$o 2>/dev/null | grep -vE '^\s*$|^#' | grep -E '⇒|"(late|lateConfirmed|swallowed|lateCtcPrecision|fatal)"|■' | tr -d '\n' | cut -c1-500)"; done
