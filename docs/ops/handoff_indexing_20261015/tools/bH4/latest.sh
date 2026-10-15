#!/bin/bash
# latest.sh <since ISO> — يطبع مفاتيح trabulsi/mrifai الجديدة
B=$(dirname $0); cd $B/..
bH4/put.sh bwx "$(bH4/mk index_qa/bucket_watch.py --since $1)" >/dev/null 2>&1
n=$(ls wt_pH4/ops/commands | grep pH4_bwx | tail -1); n=${n%.json}
WMAX=60 bH4/wait.sh ops/out/$n.txt >/dev/null; bH4/rd.sh ops/out/$n.txt | grep -E "timings-staging"
