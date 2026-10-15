#!/bin/bash
# pool.sh — مُطلِقٌ بحصّة ≤4: يسحب من $S/q.txt (name<TAB>json) ويتتبّع $S/mine.txt
S=/tmp/claude-0/-home-user/06b0cdc4-1efe-58b9-bd35-06b0a18e1af5/scratchpad; B=$S/b
source <(sed -n 4p $B/wave.sh)
touch $S/q.txt $S/mine.txt
while :; do
  : > $S/mine.new
  while read id; do [ -z "$id" ] && continue; st=$(gh api repos/mwqwf/rafiq-align-ci/actions/runs/$id --jq '.status+" "+(.conclusion//"")' 2>/dev/null) || { echo $id >> $S/mine.new; continue; }
    case "$st" in completed*) echo "$(date -u +%H:%MZ) انتهت $id $st" >> $S/pool.log;; *) echo $id >> $S/mine.new;; esac; done < $S/mine.txt
  mv $S/mine.new $S/mine.txt
  if [ -s $S/q.txt ] && [ $(wc -l < $S/mine.txt) -lt 4 ] && [ $(tot) -lt 20 ]; then
    line=$(head -1 $S/q.txt); sed -i 1d $S/q.txt
    name=$(echo "$line" | cut -f1); js=$(echo "$line" | cut -f2-)
    o=$($B/put.sh "$name" "$js" 2>/dev/null | head -1)
    WMAX=400 $B/wait.sh $o >/dev/null
    id=$($B/rd.sh $o 2>/dev/null | grep -oE 'runs/[0-9]+' | head -1 | cut -d/ -f2)
    echo "$(date -u +%H:%MZ) أُطلق $name -> $o -> ${id:-؟}" >> $S/pool.log
    [ -n "$id" ] && echo $id >> $S/mine.txt
    continue
  fi
  sleep 60
done
