#!/bin/bash
# put.sh <name> '<json>' ... — أوامر fixD من نسختي الخاصة؛ كلّ محاولة تبدأ من origin/main نظيفاً
C=/tmp/claude-0/-home-claude/73343a78-67de-5d83-95ae-5c563459823a/scratchpad/fixD/clone
cd $C
t=$(date -u +%H%M); names=(); jsons=(); outs=()
while [ $# -ge 2 ]; do n="$(date -u +%Y%m%d)_${t}_fixD_$1"; names+=("$n"); jsons+=("$2"); echo "ops/out/$n.txt"; shift 2; done
for i in $(seq 1 40); do
  git fetch -q origin && git reset -q --hard origin/main
  ps=(); for j in "${!names[@]}"; do echo "${jsons[$j]}" > ops/commands/${names[$j]}.json; ps+=(ops/commands/${names[$j]}.json); done
  git add "${ps[@]}" && git commit -q -m "ops(fixD): ${#ps[@]} أمراً ($t)

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_019yrNdEUvc7CLqZmoXxz6v9" -- "${ps[@]}"
  git push -q origin HEAD:main 2>/dev/null && { echo "دُفع" >&2; exit 0; }
  sleep $((1+RANDOM%4))
done
echo "تعذّر الدفع" >&2
