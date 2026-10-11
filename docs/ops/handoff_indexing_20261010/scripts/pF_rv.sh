#!/bin/bash
# rv.sh <key> — يطلب أحكام مرشّح (إحصاء·سماع·مطالع·تجميع الملوح) وينتظرها ويطبعها
P=/tmp/claude-0/-home-user/655bf1da-3ade-5c39-b73e-f25874555b84/scratchpad/pF
k=$1; fn=$(basename $k); r=${fn%%.*}; flat=$(echo $k|tr / _)
d(){ echo "{\"action\":\"tool\",\"tool\":\"index_qa/dump_state.py\",\"args\":[\"state/$flat.$1\",\"verdict\",\"severeRate\",\"sha256\",\"late\",\"lateConfirmed\",\"swallowed\",\"fatal\",\"lateCtcPrecision\"]}"; }
outs=$($P/put.sh v_${r}_cen "{\"action\":\"tool\",\"tool\":\"index_qa/census_gate_check.py\",\"args\":[\"$k\"]}" v_${r}_heard "{\"action\":\"tool\",\"tool\":\"index_qa/heard_gate.py\",\"args\":[\"$k\"]}" v_${r}_op "$(d openers.json)" v_${r}_pool "{\"action\":\"tool\",\"tool\":\"index_qa/pool_probe.py\",\"args\":[\"$k\"]}" 2>/dev/null)
WMAX=${WMAX:-40} $P/wait.sh $outs >/dev/null
cd /tmp/claude-0/-home-user/655bf1da-3ade-5c39-b73e-f25874555b84/scratchpad/wt_pF
echo "== $k"; for o in $outs; do echo "-- $(basename $o): $(git show origin/main:$o 2>/dev/null | grep -vE '^\s*$|^#' | grep -E '⇒|"(late|lateConfirmed|swallowed|lateCtcPrecision|fatal)"|■|✅|⛔|جسيم|حكم' | tr -d '\n' | cut -c1-600)"; done
