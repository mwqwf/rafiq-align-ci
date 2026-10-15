#!/bin/bash
# wany.sh — ينتظر انتهاء أيّ تشغيلة في runs.txt ويطبعها ويحذفها
H=$(dirname $0)
for i in $(seq 1 ${WMAX:-170}); do
  while read id n; do st=$(gh api repos/mwqwf/rafiq-align-ci/actions/runs/$id --jq '.status+" "+(.conclusion//"")' 2>/dev/null); case "$st" in completed*) echo "$id $n $st"; grep -v "^$id " $H/runs.txt > $H/r.tmp; mv $H/r.tmp $H/runs.txt; exit 0;; esac; done < $H/runs.txt
  sleep 120; done; echo timeout
