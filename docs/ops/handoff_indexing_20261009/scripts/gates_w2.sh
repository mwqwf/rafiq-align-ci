#!/bin/bash
# gates.sh <key> — البوّابات الكاملة لمرشّح (بنية·مطالع·إحصاء·تشخيص·سماع·تدقيق·4 ملوح)
W=/tmp/claude-0/-home-claude/73343a78-67de-5d83-95ae-5c563459823a/scratchpad/fixD
k=$1; riw=$(echo $k|cut -d/ -f2); fn=$(basename $k); r=${fn%%.*}; h=$(echo $fn|cut -d. -f2)
a=()
for i in ${SALTS:-1 2 3 4}; do a+=(g_${r}_s$i "{\"action\":\"dispatch\",\"workflow\":\"audio_qa.yml\",\"inputs\":{\"only\":\"$k\",\"seed_salt\":\"fixD${h:0:4}$i\",\"job_minutes\":\"240\"}}"); done
/tmp/claude-0/-home-claude/73343a78-67de-5d83-95ae-5c563459823a/scratchpad/fixD/put.sh "${a[@]}"
