#!/bin/bash
t=0; for s in in_progress queued pending; do n=$(gh api "repos/mwqwf/rafiq-align-ci/actions/runs?status=$s&per_page=1" --jq .total_count 2>/dev/null||echo 99); t=$((t+n)); done; echo $t
