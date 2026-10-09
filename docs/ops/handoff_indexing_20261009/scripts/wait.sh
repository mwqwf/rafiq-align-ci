#!/bin/bash
# wait.sh <pattern-suffix...> ينتظر ظهور ملفات ops/out/<name>.txt على origin/main
cd /home/claude/rafiq-align-ci
for i in $(seq 1 360); do git fetch -q origin; ok=1; for o in "$@"; do git cat-file -e origin/main:ops/out/$o.txt 2>/dev/null || ok=0; done; [ $ok = 1 ] && break; sleep 10; done
git merge -q --no-edit origin/main >/dev/null 2>&1; echo done $ok
