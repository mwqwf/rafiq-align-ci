#!/bin/bash
# w1.sh <key> — إحصاء(متوازٍ)·تشخيص·سماع·تدقيق
k=$1; riw=$(echo $k|cut -d/ -f2); fn=$(basename $k); r=${fn%%.*}; h=$(echo $fn|cut -d. -f2)
P=${PAR:-true}
/tmp/claude-0/-home-user/655bf1da-3ade-5c39-b73e-f25874555b84/scratchpad/pF/put.sh \
 g_${r}_census "{\"action\":\"dispatch\",\"workflow\":\"splice_census.yml\",\"inputs\":{\"only\":\"$k\",\"parallel_surahs\":\"$P\"}}" \
 g_${r}_diag "{\"action\":\"dispatch\",\"workflow\":\"diagnosis.yml\",\"inputs\":{\"only\":\"$riw/$r\"}}" \
 g_${r}_heard "{\"action\":\"dispatch\",\"workflow\":\"heard_gate.yml\",\"inputs\":{\"only\":\"$k\",\"shards\":\"4\"}}" \
 g_${r}_audit "{\"action\":\"tool\",\"tool\":\"index_qa/full_audit.py\",\"args\":[\"--only\",\"$k\",\"--no-public\",\"--out\",\"ops/out/pF-audit-$r.$h.json\",\"--md\",\"ops/out/pF-audit-$r.$h.md\"]}"
