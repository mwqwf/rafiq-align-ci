#!/bin/bash
# hg.sh <وسم الطابور> — ينتظر أن يُطلق ثمّ يطبع حكم heard_gate المختصر
S=/tmp/claude-0/-home-user/06b0cdc4-1efe-58b9-bd35-06b0a18e1af5/scratchpad; cd $S/wt_pH2
id=""; until [ -n "$id" ]; do id=$(grep "$1 ->" $S/pH2pool.log | awk '{print $NF}' | tr -d '\r' | tail -1); [ -n "$id" ] || sleep 20; done
until git fetch -q origin main 2>/dev/null; git cat-file -e origin/main:ops/out/heard-gate/$id.txt 2>/dev/null; do sleep 20; done
git show origin/main:ops/out/heard-gate/$id.txt | cut -c1-230 | grep -E "■|س[0-9]+: ⛔|⇒"
