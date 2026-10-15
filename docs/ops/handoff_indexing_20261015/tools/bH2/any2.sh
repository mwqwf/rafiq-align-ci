#!/bin/bash
# any2.sh id1 id2 — يخرج متى اكتملت إحداهما (≤115ث)
timeout 115 bash -c 'until [ "$(gh api repos/mwqwf/rafiq-align-ci/actions/runs/$0 --jq .status)" = completed ] || [ "$(gh api repos/mwqwf/rafiq-align-ci/actions/runs/$1 --jq .status)" = completed ]; do sleep 20; done' $1 $2
for i in $1 $2; do echo $i $(gh api repos/mwqwf/rafiq-align-ci/actions/runs/$i --jq '.status+" "+(.conclusion//"")'); done
