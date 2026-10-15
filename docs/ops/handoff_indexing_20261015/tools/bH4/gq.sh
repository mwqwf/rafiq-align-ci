#!/bin/bash
# gq.sh <staging key> <riw/id> <tag> — يضع البوّابات الثمانية في طابوري
S=/tmp/claude-0/-home-user/06b0cdc4-1efe-58b9-bd35-06b0a18e1af5/scratchpad; K=$1; R=$2; t=$3
d(){ python3 -c 'import json,sys;print(json.dumps({"action":"dispatch","workflow":sys.argv[1],"inputs":json.loads(sys.argv[2])},ensure_ascii=False))' "$1" "$2"; }
{ printf "g${t}_opn\t%s\n" "$(d openers.yml "{\"only\":\"$K\"}")"
printf "g${t}_heard\t%s\n" "$(d heard_gate.yml "{\"only\":\"$K\",\"shards\":\"4\"}")"
printf "g${t}_cen\t%s\n" "$(d splice_census.yml "{\"only\":\"$K\",\"force\":\"true\",\"no_range\":\"true\",\"parallel_surahs\":\"false\"}")"
for i in 1 2 3 4; do printf "g${t}_s$i\t%s\n" "$(d audio_qa.yml "{\"only\":\"$K\",\"seed_salt\":\"pH4${t}$i\",\"job_minutes\":\"240\"}")"; done
printf "g${t}_diag\t%s\n" "$(d diagnosis.yml "{\"only\":\"$R\"}")"; } >> $S/pH4q.txt
