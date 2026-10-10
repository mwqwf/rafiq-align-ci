#!/bin/bash
# w2.sh <key> [أرقام الملوح] — ملوح الصوت
k=$1; fn=$(basename $k); r=${fn%%.*}; h=$(echo $fn|cut -d. -f2); a=()
for i in ${2:-1 2 3 4}; do a+=(g_${r}_s$i "{\"action\":\"dispatch\",\"workflow\":\"audio_qa.yml\",\"inputs\":{\"only\":\"$k\",\"seed_salt\":\"pE${h:0:4}$i\",\"job_minutes\":\"240\"}}"); done
/tmp/claude-0/-home-user/655bf1da-3ade-5c39-b73e-f25874555b84/scratchpad/pE/put.sh "${a[@]}"
