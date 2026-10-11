#!/bin/bash
S=/tmp/claude-0/-home-user/655bf1da-3ade-5c39-b73e-f25874555b84/scratchpad
cd $S/proofZ
while true; do
  pgrep -f "^python3 driver.py" >/dev/null || (MAX_MINE=4 SHARDS=3 nohup python3 driver.py >> driver.log 2>&1 &)
  git -C clone fetch -q origin main
  python3 defects.py >/dev/null 2>&1
  n=$(git -C clone ls-tree --name-only origin/main state-heard/ 2>/dev/null | wc -l)
  runs=$(git -C clone ls-tree --name-only origin/main ops/out/heard-pub/ | wc -l)
  {
   echo "# حالة pZ ($(date -u +%FT%H:%MZ))"
   echo "- خرائط state-heard في main: $n ملفاً (الهدف 180)؛ سجلات heard_pub: $runs"
   echo "- الطابور المتبقي: $(python3 -c "import json;s=json.load(open('driver_state.json'));print(len(s['queue']),'منتظر،',len(s['dispatched']),'جارٍ،',len(s['done']),'منجز')")"
   echo "- السائق: $(pgrep -f '^python3 driver.py'|head -1)"
   tail -3 driver.log
  } > $S/ledger/pZ_state.md
  { echo "# انحرافات > 1.5ث مثبتة بالسماع (pZ) — للمصلح"; echo "الصيغة: القارئ · السور/الآيات · الانحراف · ملف ops/out الدالّ (الجدول التفصيلي في proofZ_defects.md)"; echo; sed -n '/^| الفهرس/,/^$/p' $S/proofZ_defects.md; } > $S/ledger/pZ_defects.md
  sleep 1800
done
