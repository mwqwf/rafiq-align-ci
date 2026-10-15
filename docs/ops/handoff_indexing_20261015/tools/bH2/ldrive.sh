#!/bin/bash
S=/tmp/claude-0/-home-user/06b0cdc4-1efe-58b9-bd35-06b0a18e1af5/scratchpad; B=$S/bH2
LU="https://pub-2c2e1dcd92e84a2898820dd38d3e09e6.r2.dev/audio/warsh/laghdaf_shinqiti/{s:03d}.mp3"
fin(){ until grep -q "$1 ->" $S/pH2pool.log; do sleep 15; done; id=$(grep "$1 ->" $S/pH2pool.log|awk '{print $NF}'); until [ "$(gh api repos/mwqwf/rafiq-align-ci/actions/runs/$id --jq .status)" = completed ]; do sleep 20; done; gh api repos/mwqwf/rafiq-align-ci/actions/runs/$id --jq .conclusion; }
base=timings-staging/warsh/laghdaf_shinqiti.1a82f874.jz
for p in "35:35:10-14" "39:39:5-9,39:20-24,39:47-51,39:71-75" "42:42:34-38"; do
  s=${p%%:*}; rest=${p#*:}; rw=${rest#*:}; [ "$s" = 35 ] && rw="35:10-14"; [ "$s" = 42 ] && rw="42:34-38"; [ "$s" = 39 ] && rw="39:5-9,39:20-24,39:47-51,39:71-75"
  t=lag_E$s; since=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  $B/df.sh $t $base warsh "$LU" "$rw"
  r=$(fin $t); echo "$t $r" >> $S/ldrive.log
  if [ "$r" = success ]; then n=$($B/cand.sh warsh/laghdaf_shinqiti $since); [ -n "$n" ] && base=$n; fi
  echo "base=$base" >> $S/ldrive.log
done
echo DONE >> $S/ldrive.log
