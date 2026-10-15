#!/bin/bash
# cand.sh <riw/id بادئة مثل qalun/janaini_qalun> <since ISO> — يطبع آخر مفتاح staging
B=/tmp/claude-0/-home-user/06b0cdc4-1efe-58b9-bd35-06b0a18e1af5/scratchpad/bH2
o=$($B/put.sh bwc "$($B/mk index_qa/bucket_watch.py --since $2)" 2>/dev/null|head -1); WMAX=60 $B/wait.sh $o >/dev/null; $B/rd.sh $o 2>&1 | grep "$1" | tail -1 | grep -oE 'timings-staging/[^ ]+'
