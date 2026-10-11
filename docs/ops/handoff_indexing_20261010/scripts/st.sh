#!/bin/bash
# st.sh — موجز حالة خطوط go الأحدث من ساعتين
cd /tmp/claude-0/-home-user/655bf1da-3ade-5c39-b73e-f25874555b84/scratchpad/pE
for f in $(find . -name 'go_*.log' -mmin -300 | sort); do r=${f#./go_}; r=${r%.log}; t=$(grep -E "^انتهى|^⛔" $f | head -1); p=$(grep -c "↑ timings/[a-z]*/$r" $f); echo "$r | $(tail -n1 $f | cut -c1-40) | promoted=$p $t"; done
