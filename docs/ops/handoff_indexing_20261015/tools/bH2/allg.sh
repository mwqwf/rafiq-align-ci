#!/bin/bash
# allg.sh <بادئة الوسم> — ينتظر اكتمال كلّ تشغيلات الوسوم المطابقة
S=/tmp/claude-0/-home-user/06b0cdc4-1efe-58b9-bd35-06b0a18e1af5/scratchpad
for id in $(grep "$1" $S/pH2pool.log | grep "أُطلق" | awk '{print $NF}'); do until [ "$(gh api repos/mwqwf/rafiq-align-ci/actions/runs/$id --jq .status)" = completed ]; do sleep 30; done; echo $id $(gh api repos/mwqwf/rafiq-align-ci/actions/runs/$id --jq .conclusion); done
