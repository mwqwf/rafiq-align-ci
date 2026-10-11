#!/bin/bash
# wait.sh <مسار نسبي>... (مثلاً ops/out/x.txt) ينتظر ظهورها
cd /tmp/claude-0/-home-user/655bf1da-3ade-5c39-b73e-f25874555b84/scratchpad/wt_pE
for i in $(seq 1 ${WMAX:-50}); do git fetch -q origin main; ok=1; for o in "$@"; do git cat-file -e origin/main:$o 2>/dev/null || ok=0; done; [ $ok = 1 ] && { echo done; exit 0; }; sleep 15; done; echo timeout
