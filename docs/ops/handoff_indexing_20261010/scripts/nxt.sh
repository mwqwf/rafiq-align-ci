#!/bin/bash
# nxt.sh <rid> <ملخّص> — ينتظر دفعة hb ثمّ يطلق go.sh على مرشّحها
P=/tmp/claude-0/-home-user/655bf1da-3ade-5c39-b73e-f25874555b84/scratchpad/pE; W=$P/../wt_pE; r=$1; summ=$2
exec >$P/nxt_$r.log 2>&1
for i in $(seq 1 60); do git -C $W fetch -q origin main 2>/dev/null; f=$(git -C $W ls-tree --name-only origin/main ops/out/ | grep "pE_hb_$r.txt" | tail -1); [ -n "$f" ] && break; sleep 15; done
id=$(git -C $W show origin/main:$f | tail -1 | grep -o '[0-9]*$'); echo run=$id
for i in $(seq 1 400); do [ "$(gh run view $id -R mwqwf/rafiq-align-ci --json status --jq .status)" = completed ] && break; sleep 30; done
log=$(gh run view $id -R mwqwf/rafiq-align-ci --log 2>/dev/null)
key=$(echo "$log" | grep -o 'إلى timings-staging/[^ ]*\.jz' | tail -1 | sed 's/^إلى //')
[ -n "$key" ] || { echo "⛔ لا مرشّح: $(echo "$log" | grep -E 'لا سورةَ|⛔ الأصلُ|⛔' | grep -v '36;1m' | tail -2 | cut -c60-300)"; exit 1; }
old=$(echo "$log" | grep -o 'parentSha256": "[0-9a-f]\{8\}' | tail -1 | grep -o '[0-9a-f]\{8\}$')
echo key=$key old=$old
exec $P/go.sh $key $old "$summ"
