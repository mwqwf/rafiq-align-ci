#!/bin/bash
# runw.sh <وسم> — ينتظر إطلاق ثمّ اكتمال التشغيلة ويطبع النتيجة
S=/tmp/claude-0/-home-user/06b0cdc4-1efe-58b9-bd35-06b0a18e1af5/scratchpad
until grep -q "$1 ->" $S/pH2pool.log; do sleep 20; done; id=$(grep "$1 ->" $S/pH2pool.log|awk '{print $NF}')
until gh api repos/mwqwf/rafiq-align-ci/actions/runs/$id --jq .status|grep -q completed; do sleep 20; done
echo $1 $id $(gh api repos/mwqwf/rafiq-align-ci/actions/runs/$id --jq .conclusion)
