#!/bin/bash
S=/tmp/claude-0/-home-user/655bf1da-3ade-5c39-b73e-f25874555b84/scratchpad
exec 9>$S/promote.lock; flock 9
R="ترقية kurdi بإسقاط س4 بإعلان للمستخدم (4:127 غائبة من صوت المصدر نفسه، فجوة وسطية، لا مصدر بديل)؛ اجتازت البنية والمطالع والأملاح الأربعة (0.38%) والإحصاء والسماع والتشخيص والتدقيق"
$S/pK_put.sh Q1 "{\"action\":\"tool\",\"tool\":\"index_qa/promote.py\",\"args\":[\"--unfreeze\",\"timings/hafs/kurdi.jz\",\"--reason\",\"$R\"]}" >/dev/null 2>&1
sleep 150
$S/pK_put.sh Q2 '{"action":"tool","tool":"index_qa/promote.py","args":["--only","timings-staging/hafs/kurdi.8dd3cf93.jz","--yes"]}' >/dev/null 2>&1
n=$(ls $S/wt_pK/ops/out 2>/dev/null|wc -l); sleep 5
cd $S/wt_pK; for i in $(seq 1 90); do git fetch -q; f=$(git ls-tree --name-only origin/main ops/out/|grep "_pK_Q2.txt"|tail -1); [ -n "$f" ] && break; sleep 10; done
git show origin/main:$f > $S/o_Q2.txt
$S/pK_put.sh Q3 '{"action":"tool","tool":"ci_fleet/refreeze.py","args":["timings/hafs/kurdi.jz","8dd3cf93","pK: تجميد بعد ترقية 8dd3cf93"]}' >/dev/null 2>&1
$S/pK_put.sh Qlive "{\"action\":\"tool\",\"tool\":\"index_qa/dump_state.py\",\"args\":[\"timings/manifest.json\",\"indexes\"]}" >/dev/null 2>&1
echo done > $S/o_prom_done
