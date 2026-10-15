#!/bin/bash
# allw.sh <ملف ids "n:id n:id"> — يخرج حين تنتهي كلّها
for i in $(seq 1 ${WN:-56}); do d=0;n=0; for x in $(cat $1); do id=${x#*:}; [ -z "$id" ] && continue; n=$((n+1)); gh api repos/mwqwf/rafiq-align-ci/actions/runs/$id --jq .status 2>/dev/null | grep -q completed && d=$((d+1)); done; [ $d -ge $n ] && break; sleep 10; done; echo $d/$n; date -u
