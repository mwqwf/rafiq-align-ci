#!/bin/bash
# pK_put.sh <اسم> '<json>' ...
C=/tmp/claude-0/-home-user/655bf1da-3ade-5c39-b73e-f25874555b84/scratchpad/wt_pK
cd $C; t=$(date -u +%H%M); names=(); jsons=()
while [ $# -ge 2 ]; do n="$(date -u +%Y%m%d)_${t}_pK_$1"; names+=("$n"); jsons+=("$2"); echo "ops/out/$n.txt"; shift 2; done
for i in $(seq 1 40); do
  git fetch -q origin && git reset -q --hard origin/main
  ps=(); for j in "${!names[@]}"; do echo "${jsons[$j]}" > ops/commands/${names[$j]}.json; ps+=(ops/commands/${names[$j]}.json); done
  git add "${ps[@]}" && git commit -q -m "ops(pK): ${#ps[@]} أمراً ($t)

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01SQoynCHdh8JeGQW5FiQC2r" -- "${ps[@]}"
  git push -q origin HEAD:main 2>/dev/null && { echo "دُفع" >&2; exit 0; }
  sleep $((1+RANDOM%4))
done
echo "تعذّر الدفع" >&2
