#!/bin/bash
# gates.sh <key> — البوّابات الكاملة لمرشّح (بنية·مطالع·إحصاء·تشخيص·سماع·تدقيق·4 ملوح)
W=/tmp/claude-0/-home-claude/73343a78-67de-5d83-95ae-5c563459823a/scratchpad/fixD
k=$1; riw=$(echo $k|cut -d/ -f2); fn=$(basename $k); r=${fn%%.*}; h=$(echo $fn|cut -d. -f2)
a=(g_${r}_struct "{\"action\":\"tool\",\"tool\":\"index_qa/run.py\",\"args\":[\"--struct-only\",\"$k\"]}"
 g_${r}_openers "{\"action\":\"dispatch\",\"workflow\":\"openers.yml\",\"inputs\":{\"only\":\"$k\"}}"
 g_${r}_census "{\"action\":\"dispatch\",\"workflow\":\"splice_census.yml\",\"inputs\":{\"only\":\"$k\",\"parallel_surahs\":\"true\"}}"
 g_${r}_diag "{\"action\":\"dispatch\",\"workflow\":\"diagnosis.yml\",\"inputs\":{\"only\":\"$riw/$r\"}}"
 g_${r}_heard "{\"action\":\"dispatch\",\"workflow\":\"heard_gate.yml\",\"inputs\":{\"only\":\"$k\",\"shards\":\"4\"}}"
 g_${r}_audit "{\"action\":\"tool\",\"tool\":\"index_qa/full_audit.py\",\"args\":[\"--only\",\"$k\",\"--no-public\",\"--out\",\"ops/out/fixD-audit-$r.$h.json\",\"--md\",\"ops/out/fixD-audit-$r.$h.md\"]}")
/tmp/claude-0/-home-claude/73343a78-67de-5d83-95ae-5c563459823a/scratchpad/fixD/put.sh "${a[@]}"
