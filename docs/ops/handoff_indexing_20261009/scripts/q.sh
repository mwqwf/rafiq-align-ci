#!/bin/bash
for s in in_progress queued pending; do echo -n "$s: "; gh api "repos/mwqwf/rafiq-align-ci/actions/runs?status=$s&per_page=100" --jq '.total_count'; done
