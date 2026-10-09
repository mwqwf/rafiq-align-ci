#!/bin/bash
# الاستعمال: pushcmds.sh <مجلّد> "<رسالة>"  — يدفع أوامر المجلّد ولا ينقلها إلا بعد التحقق من وصولها
set -u
D=$1; MSG=$2; S=/tmp/claude-0/-home-claude/73343a78-67de-5d83-95ae-5c563459823a/scratchpad
cd /home/claude/rafiq-align-ci || exit 1
files=$(ls $D/*.json 2>/dev/null) || { echo "لا أوامر"; exit 1; }
timeout 30 git fetch -q origin main; git merge -q --no-edit origin/main
cp $files ops/commands/ || exit 1
git add ops/commands
git commit -q -m "$MSG

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_019yrNdEUvc7CLqZmoXxz6v9" -- ops/commands
for i in 1 2 3 4 5 6 7 8; do timeout 40 git push -q origin HEAD:main 2>/dev/null && break; sleep $((2*i)); timeout 30 git fetch -q origin main; git merge -q --no-edit origin/main; done
for k in 1 2 3; do timeout 30 git fetch -q origin main 2>/dev/null && break; sleep 3; done
ok=1; for f in $files; do git cat-file -e origin/main:ops/commands/$(basename $f) 2>/dev/null || { echo "لم يصل: $(basename $f)"; ok=0; }; done
[ $ok = 1 ] && { mkdir -p $S/pushed; mv $files $S/pushed/; echo "دُفع $(echo $files|wc -w)"; }
