#!/bin/bash
# pool.sh — مُطلِقٌ بحصّة ≤4: يسحب من $S/pH4q.txt (name<TAB>json) ويتتبّع $S/pH4mine.txt
S=/tmp/claude-0/-home-user/06b0cdc4-1efe-58b9-bd35-06b0a18e1af5/scratchpad; B=$S/bH4
tot(){ $B/tot.sh; }
touch $S/pH4q.txt $S/pH4mine.txt
while :; do
  : > $S/pH4mine.new
  while read id; do [ -z "$id" ] && continue; st=$(gh api repos/mwqwf/rafiq-align-ci/actions/runs/$id --jq '.status+" "+(.conclusion//"")' 2>/dev/null) || { echo $id >> $S/pH4mine.new; continue; }
    case "$st" in completed*) echo "$(date -u +%H:%MZ) انتهت $id $st" >> $S/pH4pool.log;; *) echo $id >> $S/pH4mine.new;; esac; done < $S/pH4mine.txt
  mv $S/pH4mine.new $S/pH4mine.txt
  if [ -s $S/pH4q.txt ] && [ $(wc -l < $S/pH4mine.txt) -lt 4 ] && [ $(tot) -lt 20 ]; then
    line=$(head -1 $S/pH4q.txt); sed -i 1d $S/pH4q.txt
    name=$(echo "$line" | cut -f1); js=$(echo "$line" | cut -f2-)
    o=$($B/put.sh "$name" "$js" 2>/dev/null | head -1)
    WMAX=400 $B/wait.sh $o >/dev/null
    id=$($B/rd.sh $o 2>/dev/null | grep -oE 'runs/[0-9]+' | head -1 | cut -d/ -f2)
    echo "$(date -u +%H:%MZ) أُطلق $name -> $o -> ${id:-؟}" >> $S/pH4pool.log
    [ -n "$id" ] && echo $id >> $S/pH4mine.txt
    continue
  fi
  sleep 60
done
