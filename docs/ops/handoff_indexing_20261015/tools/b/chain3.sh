#!/bin/bash
# chain.sh <parent sha8> <surah:ranges|surah> ... — سلسلة ctc_splice متسلسلة؛ تطبع sha الناتج بعد كلّ حلقة
S=/tmp/claude-0/-home-user/06b0cdc4-1efe-58b9-bd35-06b0a18e1af5/scratchpad; B=$S/b
par=$1; shift
mk(){ python3 - "$@" <<'PY'
import json,sys
print(json.dumps({"action":"tool","tool":sys.argv[1],"args":sys.argv[2:]},ensure_ascii=False))
PY
}
while [ $# -gt 0 ]; do
  item=$1; shift
  s=${item%%=*}; rw=""; [ "$item" != "$s" ] && rw=${item#*=}
  t0=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  J=$(python3 -c '
import json,sys
i={"parent":"timings-staging/qalun/maroush_qalun.%s.jz"%sys.argv[1],"url_template":"https://archive.org/download/Kamal-Almaroush-Qalon/{s:03d}.mp3","riwaya":"qalun","surahs":sys.argv[2],"mode":"dualfix","base_key":"timings-staging/qalun/maroush_qalun.3d4e8af3.jz","reason":"pC3: سلسلة مروش — سورة %s فوق %s"%(sys.argv[2],sys.argv[1])}
if sys.argv[3]: i["rewindow"]=sys.argv[3]
print(json.dumps({"action":"dispatch","workflow":"ctc_splice.yml","inputs":i},ensure_ascii=False))' "$par" "$s" "$rw")
  o=$($B/put.sh ch$s "$J" 2>/dev/null|head -1); WMAX=400 $B/wait.sh $o >/dev/null
  id=$($B/rd.sh $o | grep -oE 'runs/[0-9]+'|head -1|cut -d/ -f2); echo "$(date -u +%H:%MZ) $s على $par -> run $id"
  t1=$(date +%s)
  while :; do st=$(gh api repos/mwqwf/rafiq-align-ci/actions/runs/$id --jq '.status+" "+(.conclusion//"")' 2>/dev/null); case "$st" in completed*) break;; pending*|queued*) if [ $(( $(date +%s)-t1 )) -gt 1500 ]; then echo "$(date -u +%H:%MZ) عالقة $id ($st) ⇒ إلغاء وإعادة"; gh run cancel $id --repo mwqwf/rafiq-align-ci >/dev/null 2>&1; sleep 20; set -- "$item" "$@"; STUCK=1; break; fi;; *) t1=$(date +%s);; esac; sleep 45; done
  [ -n "$STUCK" ] && { STUCK=""; continue; }
  echo "$(date -u +%H:%MZ) انتهت $id $st"
  w=$(date -u +%H%M%S)
  o=$($B/put.sh bwc$s "$(mk index_qa/bucket_watch.py --since $t0)" 2>/dev/null|head -1); WMAX=80 $B/wait.sh $o >/dev/null
  new=$($B/rd.sh $o | grep -oE 'maroush_qalun\.[0-9a-f]{8}'|tail -1|cut -d. -f2)
  echo "الناتج: ${new:-لا شيء}"; [ -n "$new" ] && [ "$new" != "$par" ] && $B/hg.sh $new >/dev/null 2>&1; [ -n "$new" ] && [ "$new" != "$par" ] || { echo "⛔ توقّفت السلسلة عند $s"; exit 1; }
  par=$new
done
echo "CHAIN_DONE $par"
