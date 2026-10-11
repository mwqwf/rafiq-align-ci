gh api "repos/mwqwf/rafiq-align-ci/actions/runs?per_page=100" --jq '.workflow_runs[]|select(.display_title|test("${P:-97a6c86a}"))|[.status,.conclusion,.display_title[0:70]]|@tsv'
