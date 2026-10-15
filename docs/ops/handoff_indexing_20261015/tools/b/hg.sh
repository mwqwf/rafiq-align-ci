#!/bin/bash
# hg.sh <sha8> — يطلق بوّابة السماع + البنية دون انتظار
B=$(dirname $0); h=$1; K=timings-staging/qalun/maroush_qalun.$h.jz
d(){ python3 -c 'import json,sys;print(json.dumps({"action":"dispatch","workflow":sys.argv[1],"inputs":json.loads(sys.argv[2])},ensure_ascii=False))' "$1" "$2"; }
$B/put.sh hg_$h "$(d heard_gate.yml "{\"only\":\"$K\",\"shards\":\"4\"}")"
