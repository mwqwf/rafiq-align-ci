#!/bin/bash
# gates.sh <sha8> — كلّ بوّابات مرشّح مروش على موجتين ≤4
B=$(dirname $0); R=$1; h=$2; K=timings-staging/$R.$h.jz; P=pC3${R##*/}
d(){ python3 -c 'import json,sys;print(json.dumps({"action":"dispatch","workflow":sys.argv[1],"inputs":json.loads(sys.argv[2])},ensure_ascii=False))' "$1" "$2"; }
$B/wave.sh g${P}${h}_opn "$(d openers.yml "{\"only\":\"$K\"}")" g${P}${h}_heard "$(d heard_gate.yml "{\"only\":\"$K\",\"shards\":\"4\"}")" g${P}${h}_cen "$(d splice_census.yml "{\"only\":\"$K\",\"force\":\"true\",\"no_range\":\"true\",\"parallel_surahs\":\"false\"}")" g${P}${h}_s1 "$(d audio_qa.yml "{\"only\":\"$K\",\"seed_salt\":\"${P:0:6}${h:0:4}1\",\"job_minutes\":\"240\"}")"
$B/wave.sh g${P}${h}_s2 "$(d audio_qa.yml "{\"only\":\"$K\",\"seed_salt\":\"${P:0:6}${h:0:4}2\",\"job_minutes\":\"240\"}")" g${P}${h}_s3 "$(d audio_qa.yml "{\"only\":\"$K\",\"seed_salt\":\"${P:0:6}${h:0:4}3\",\"job_minutes\":\"240\"}")" g${P}${h}_s4 "$(d audio_qa.yml "{\"only\":\"$K\",\"seed_salt\":\"${P:0:6}${h:0:4}4\",\"job_minutes\":\"240\"}")" g${P}${h}_diag "$(d diagnosis.yml "{\"only\":\"$R\"}")"
echo GATES_DONE
