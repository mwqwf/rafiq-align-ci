#!/bin/bash
# anyw.sh — ينتظر انتهاء أيّ تشغيلة من المعرّفات في $H/watch.txt (سطر: id وسم) ويطبعها ثمّ يحذفها
H=$(dirname $0)
for i in $(seq 1 ${WMAX:-800}); do
  for lg in w13; do for id in $(grep -oE -- '-> [0-9]+' $H/$lg.log | cut -c4-); do grep -q "^$id " $H/watch.txt $H/seen.txt 2>/dev/null || echo "$id $lg" >> $H/watch.txt; done; done
  while read id n; do st=$(gh api repos/mwqwf/rafiq-align-ci/actions/runs/$id --jq '.status+" "+(.conclusion//"")' 2>/dev/null); case "$st" in completed*) echo "$id $n $st"; echo "$id $n" >> $H/seen.txt; grep -v "^$id " $H/watch.txt > $H/watch.tmp; mv $H/watch.tmp $H/watch.txt; exit 0;; esac; done < $H/watch.txt
  sleep 30; done; echo timeout
