#!/bin/bash
B=/tmp/claude-0/-home-user/06b0cdc4-1efe-58b9-bd35-06b0a18e1af5/scratchpad/b1; K=timings-staging/hafs/qurashi.6c6b99d1.jz; h=6c6b99d1
d(){ python3 -c 'import json,sys;print(json.dumps({"action":"dispatch","workflow":sys.argv[1],"inputs":json.loads(sys.argv[2])},ensure_ascii=False))' "$1" "$2"; }
$B/put.sh qs "$($B/mk index_qa/run.py --struct-only $K)" >/dev/null 2>&1
$B/wave.sh opn "$(d openers.yml "{\"only\":\"$K\"}")" hg "$(d heard_gate.yml "{\"only\":\"$K\",\"shards\":\"4\"}")" cen "$(d splice_census.yml "{\"only\":\"$K\",\"force\":\"true\",\"no_range\":\"true\",\"parallel_surahs\":\"false\"}")" s1 "$(d audio_qa.yml "{\"only\":\"$K\",\"seed_salt\":\"pH1q1\",\"job_minutes\":\"240\"}")"
$B/wave.sh s2 "$(d audio_qa.yml "{\"only\":\"$K\",\"seed_salt\":\"pH1q2\",\"job_minutes\":\"240\"}")" s3 "$(d audio_qa.yml "{\"only\":\"$K\",\"seed_salt\":\"pH1q3\",\"job_minutes\":\"240\"}")" s4 "$(d audio_qa.yml "{\"only\":\"$K\",\"seed_salt\":\"pH1q4\",\"job_minutes\":\"240\"}")" dg "$(d diagnosis.yml '{"only":"hafs/qurashi"}')"
echo GATES_DONE
