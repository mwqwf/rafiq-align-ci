#!/bin/bash
# rs.sh <نمط> — حالة التشغيلات بالعنوان
gh api "repos/mwqwf/rafiq-align-ci/actions/runs?per_page=100" --jq ".workflow_runs[]|select(.display_title|test(\"$1\"))|[.id,.status,.conclusion,.display_title[0:90]]|@tsv"
