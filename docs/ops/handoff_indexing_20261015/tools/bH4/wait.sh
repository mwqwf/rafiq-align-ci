#!/bin/bash
# wait.sh <مسار نسبي>... (مثلاً ops/out/x.txt) ينتظر ظهورها
cd /tmp/claude-0/-home-user/06b0cdc4-1efe-58b9-bd35-06b0a18e1af5/scratchpad/wt_pH4
for i in $(seq 1 ${WMAX:-50}); do git fetch -q origin main; ok=1; for o in "$@"; do git cat-file -e origin/main:$o 2>/dev/null || ok=0; done; [ $ok = 1 ] && { echo done; exit 0; }; sleep 15; done; echo timeout
