#!/bin/bash
# gates.sh <sha8> — كلّ بوّابات مرشّح مروش على موجتين ≤4
B=$(dirname $0); h=$1; K=timings-staging/qalun/maroush_qalun.$h.jz
d(){ python3 -c 'import json,sys;print(json.dumps({"action":"dispatch","workflow":sys.argv[1],"inputs":json.loads(sys.argv[2])},ensure_ascii=False))' "$1" "$2"; }
$B/wave.sh g${h}_opn "$(d openers.yml "{\"only\":\"$K\"}")" g${h}_heard "$(d heard_gate.yml "{\"only\":\"$K\",\"shards\":\"4\"}")" g${h}_cen "$(d splice_census.yml "{\"only\":\"$K\",\"force\":\"true\",\"no_range\":\"true\",\"parallel_surahs\":\"false\"}")" g${h}_s1 "$(d audio_qa.yml "{\"only\":\"$K\",\"seed_salt\":\"pC3${h:0:4}1\",\"job_minutes\":\"240\"}")"
$B/wave.sh g${h}_s2 "$(d audio_qa.yml "{\"only\":\"$K\",\"seed_salt\":\"pC3${h:0:4}2\",\"job_minutes\":\"240\"}")" g${h}_s3 "$(d audio_qa.yml "{\"only\":\"$K\",\"seed_salt\":\"pC3${h:0:4}3\",\"job_minutes\":\"240\"}")" g${h}_s4 "$(d audio_qa.yml "{\"only\":\"$K\",\"seed_salt\":\"pC3${h:0:4}4\",\"job_minutes\":\"240\"}")" g${h}_diag "$(d diagnosis.yml '{"only":"qalun/maroush_qalun"}')"
echo GATES_DONE
