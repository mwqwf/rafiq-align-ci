#!/bin/bash
# wave.sh name1 json1 name2 json2 ... — ينتظر أسطولاً <20 ثمّ يدفع الموجة، ثمّ ينتظر الأجوبة ويطبع روابط التشغيلات، ثمّ ينتظر انتهاءها
B=$(dirname $0)
tot(){ c=$(date -u -d '-24 hours' +%Y-%m-%dT%H:%M:%SZ); t=0; for s in in_progress queued pending; do n=$(gh api "repos/mwqwf/rafiq-align-ci/actions/runs?status=$s&per_page=100" --jq "[.workflow_runs[]|select(.created_at>\"$c\")]|length" 2>/dev/null||echo 99); t=$((t+n)); done; echo $t; }
n=$(( $# / 2 ))
while [ $(tot) -ge 20 ]; do sleep 60; done
outs=$($B/put.sh "$@" 2>/dev/null)
echo "$outs"
WMAX=400 $B/wait.sh $outs >/dev/null
ids=""; for o in $outs; do id=$($B/rd.sh $o 2>/dev/null | grep -oE 'runs/[0-9]+' | head -1 | cut -d/ -f2); echo "$o -> $id"; ids="$ids $id"; done
for id in $ids; do while :; do st=$(gh api repos/mwqwf/rafiq-align-ci/actions/runs/$id --jq '.status+" "+(.conclusion//"")' 2>/dev/null); case "$st" in completed*) echo "$id $st"; break;; esac; sleep 60; done; done
