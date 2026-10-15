#!/bin/bash
# lane.sh <parent key> <surah>... — dualfix متسلسل لكلّ سورة؛ عند ناتجٍ جديدٍ يطلق حكم السماع
B=$(dirname $0); par=$1; shift
for s in "$@"; do
  t0=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  $B/put.sh ln$s "$(python3 $B/mkj.py $par $s)" >/dev/null 2>&1
  f=ops/out/$(ls -t $B/../wt_pC3/ops/commands | grep "_ln$s.json" | head -1 | sed 's/json$/txt/'); WMAX=120 $B/wait.sh $f >/dev/null
  id=$($B/rd.sh $f | grep -oE 'runs/[0-9]+' | head -1 | cut -d/ -f2)
  while [ "$(gh api repos/mwqwf/rafiq-align-ci/actions/runs/$id --jq .status 2>/dev/null)" != completed ]; do sleep 45; done
  concl=$(gh api repos/mwqwf/rafiq-align-ci/actions/runs/$id --jq .conclusion)
  $B/put.sh bl$s "$($B/mk index_qa/bucket_watch.py --since $t0)" >/dev/null 2>&1
  g=ops/out/$(ls -t $B/../wt_pC3/ops/commands | grep "_bl$s.json" | head -1 | sed 's/json$/txt/'); WMAX=120 $B/wait.sh $g >/dev/null
  new=$($B/rd.sh $g | grep -oE 'maroush_qalun\.[0-9a-f]{8}' | tail -1 | cut -d. -f2)
  echo "$(date -u +%H:%MZ) س$s run=$id $concl ناتج=${new:-لا شيء}"
  [ -n "$new" ] && $B/hg.sh $new >/dev/null 2>&1
done
echo LANE_DONE
