#!/bin/bash
# hz.sh <وسم> — ينتظر حكم heard_gate لتشغيلة الوسم ويطبعه مختصراً
S=/tmp/claude-0/-home-user/06b0cdc4-1efe-58b9-bd35-06b0a18e1af5/scratchpad; cd $S/wt_pH2
until grep -q "$1 ->" $S/pH2pool.log; do sleep 15; done; id=$(grep "$1 ->" $S/pH2pool.log|awk '{print $NF}')
until git fetch -q origin main 2>/dev/null; git cat-file -e origin/main:ops/out/heard-gate/$id.txt 2>/dev/null; do sleep 20; done
git show origin/main:ops/out/heard-gate/$id.txt | cut -c1-200 | grep -E "^■|^   س.*⛔|^   ⇒"
