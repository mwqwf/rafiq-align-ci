#!/bin/bash
# ينتظر حتى سطر جديد في سجلّ أيّ منفّذ (أو 2 ساعة) ثمّ يطبعه ويخرج
L=/tmp/claude-0/-home-user/655bf1da-3ade-5c39-b73e-f25874555b84/scratchpad/ledger
for i in $(seq 1 120); do out=""
 for f in $L/p?.md; do [ -f "$f" ] || continue; n=$(wc -l < "$f"); k=$(basename $f); o=$(grep "^$k " $L/.seen | cut -d' ' -f2); o=${o:-0}
  if [ "$n" -gt "$o" ]; then out+=$(tail -n $((n-o)) "$f" | grep -v '^|' | sed "s/^/[$k] /" | cut -c1-260 | head -6)$'\n'; sed -i "/^$k /d" $L/.seen; echo "$k $n" >> $L/.seen; fi; done
 [ -n "$out" ] && { echo "$out"; exit 0; }; sleep 60; done; echo "لا جديد خلال ساعتين"
