#!/bin/bash
# anydone.sh id... — يخرج عند اكتمال أيٍّ منها
for i in $(seq 1 ${N:-18}); do for id in "$@"; do st=$(gh api repos/mwqwf/rafiq-align-ci/actions/runs/$id --jq '.status+" "+(.conclusion//"")' 2>/dev/null); case "$st" in completed*) echo "$id $st $(date -u +%H:%MZ)"; exit 0;; esac; done; sleep 30; done; echo wait; for id in "$@"; do echo $id $(gh api repos/mwqwf/rafiq-align-ci/actions/runs/$id --jq .status); done
