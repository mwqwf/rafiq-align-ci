#!/bin/bash
# wr.sh id... — ينتظر حتى تنتهي أيٌّ منها ويطبع حالاتها
while :; do d=0; out=""; for id in "$@"; do st=$(gh api repos/mwqwf/rafiq-align-ci/actions/runs/$id --jq '.status+" "+(.conclusion//"")' 2>/dev/null); out="$out\n$id $st"; case "$st" in completed*) d=1;; esac; done; [ $d = 1 ] && { echo -e "$out"; exit 0; }; sleep 90; done
