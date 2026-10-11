#!/bin/bash
cd /tmp/claude-0/-home-user/655bf1da-3ade-5c39-b73e-f25874555b84/scratchpad/wt_pK
for i in $(seq 1 ${2:-50}); do git fetch -q origin; git cat-file -e origin/main:ops/out/$1.txt 2>/dev/null && { git show origin/main:ops/out/$1.txt; exit 0; }; sleep 10; done; echo notyet
