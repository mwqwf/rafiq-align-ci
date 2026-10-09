#!/bin/bash
# حلقة دفعٍ مستمرّة: كلّ 10 دقائق تأخذ الرباعيّات الكاملة من مجلّدات المنفّذين،
# وتطابق أصلها (P4) بالمانيفست الحيّ، فتدفع المطابق على دفعات ثلاثيّة وتعزل المتقادم.
S=/tmp/claude-0/-home-claude/73343a78-67de-5d83-95ae-5c563459823a/scratchpad; G=/home/claude/rafiq-align-ci
SRC="$S/fixY_promote:fixY $S/fixW_promote/ready:fixW $S/fixD_promote:fixD $S/fixE_promote:fixE"
mkdir -p $S/held_stale
while true; do
  have=0
  for p in $SRC; do d=${p%%:*}; ls $d/*_P4_*.json >/dev/null 2>&1 && have=1; done
  if [ $have = 1 ]; then
    cd $G; n=20261009_$(date -u +%H%M%S)_mgr_manifest
    echo '{"action":"tool","tool":"index_qa/dump_state.py","args":["timings/manifest.json","indexes"]}' > ops/commands/$n.json
    git add ops/commands/$n.json; git commit -q -m "ops: تصدير المانيفست الحيّ قبل دفعة ترقيات" -- ops/commands/$n.json
    for i in 1 2 3 4 5; do timeout 60 git push -q origin HEAD:main 2>/dev/null && break; timeout 60 git fetch -q origin main; git merge -q --no-edit origin/main; sleep $((2**i)); done
    for i in $(seq 1 40); do timeout 60 git pull -q --no-rebase origin main >/dev/null 2>&1; [ -f ops/out/$n.txt ] && break; sleep 20; done
    if [ -f ops/out/$n.txt ]; then
      tail -n +2 ops/out/$n.txt > $S/manifest_cur.json
      for p in $SRC; do d=${p%%:*}; T=${p##*:}; Q=$S/q_$T; mkdir -p $Q
        for f4 in $d/*_P4_*.json; do [ -f "$f4" ] || continue
          id=$(basename $f4 | sed -E "s/^[0-9]+_[^_]+_${T}_(.*)_P4_.*/\1/"); pre=$(basename $f4 | sed -E 's/_P4_.*//')
          ls $d/${pre}_P[123]_*.json >/dev/null 2>&1 || continue
          [ $(ls $d/${pre}_P[1-4]_*.json | wc -l) = 4 ] || continue
          ok=$(python3 -c "
import json,sys;a=json.load(open('$f4'))['args'];k=a[0].replace('timings/','').replace('.jz','')
m={f\"{i['riwaya']}/{i['reciterId']}\":i['sha256'] for i in json.load(open('$S/manifest_cur.json'))['indexes']}
print('1' if m.get(k,'').startswith(a[1]) else '0')")
          if [ "$ok" = 1 ]; then mv $d/${pre}_P[1-4]_*.json $Q/; else mv $d/${pre}_P[1-4]_*.json $S/held_stale/; echo "$(date -u +%H:%M) متقادم: $T $id"; fi
        done
        ls $Q/*.json >/dev/null 2>&1 && $S/runbatch.sh $Q $T "ops: ترقية إصلاحات $T بعد البوّابات ومطابقة الأصل للمنشور الحيّ"
      done
    fi
  fi
  sleep 600
done
