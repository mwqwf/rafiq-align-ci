#!/bin/bash
# عدّ تشغيلاتي الجارية: عناوين تحوي بصمات مرشّحيّ أو معرّفات الخطة
PAT=$(cat /tmp/claude-0/-home-user/655bf1da-3ade-5c39-b73e-f25874555b84/scratchpad/pE/pat.txt)
n=0; tot=0
for s in in_progress queued pending; do
 gh api "repos/mwqwf/rafiq-align-ci/actions/runs?status=$s&per_page=100" --jq '.workflow_runs[]|[.name,.display_title[:110],.status]|@tsv' > /tmp/mine_$$.txt
 tot=$((tot+$(wc -l </tmp/mine_$$.txt))); grep -E "$PAT" /tmp/mine_$$.txt | grep -v "^heard-pub" | cut -c1-110; n=$((n+$(grep -E "$PAT" /tmp/mine_$$.txt | grep -vc "^heard-pub")))
done; rm -f /tmp/mine_$$.txt; echo "مجموعي=$n  الكلّي=$tot"
