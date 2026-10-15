#!/bin/bash
# مشغّل janaini: ينتظر D30d ثم يطلق dualfix لـ40 فوق ناتجه (أو فوق a7ab537b إن فشلت) ثمّ بوّابة السماع
S=/tmp/claude-0/-home-user/06b0cdc4-1efe-58b9-bd35-06b0a18e1af5/scratchpad; B=$S/bH2
JU="https://archive.org/download/Al-Quran_Qaloon_tilawat_Aljanaini/{s:03d}.mp3"
fin(){ until grep -q "$1 ->" $S/pH2pool.log; do sleep 15; done; id=$(grep "$1 ->" $S/pH2pool.log|awk '{print $NF}'); until [ "$(gh api repos/mwqwf/rafiq-align-ci/actions/runs/$id --jq .status)" = completed ]; do sleep 20; done; gh api repos/mwqwf/rafiq-align-ci/actions/runs/$id --jq .conclusion; }
r=$(fin jan_D30d); base=timings-staging/qalun/janaini_qalun.a7ab537b.jz; echo "D30d $r" >> $S/jdrive.log
if [ "$r" = success ]; then base=$($B/cand.sh qalun/janaini_qalun 2026-10-14T10:00:00Z); echo "base=$base" >> $S/jdrive.log; fi
$B/df.sh jan_D40 $base qalun "$JU" 40:23-27,40:35-39
r=$(fin jan_D40); echo "D40 $r" >> $S/jdrive.log
if [ "$r" = success ]; then base=$($B/cand.sh qalun/janaini_qalun 2026-10-14T10:00:00Z); echo "base=$base" >> $S/jdrive.log; fi
d(){ python3 -c 'import json,sys;print(json.dumps({"action":"dispatch","workflow":sys.argv[1],"inputs":json.loads(sys.argv[2])},ensure_ascii=False))' "$1" "$2"; }
for t in heard opn cen; do case $t in heard) w=heard_gate.yml; i="{\"only\":\"$base\",\"shards\":\"4\"}";; opn) w=openers.yml; i="{\"only\":\"$base\"}";; cen) w=splice_census.yml; i="{\"only\":\"$base\",\"force\":\"true\",\"no_range\":\"true\",\"parallel_surahs\":\"false\"}";; esac; printf "gjZ_$t\t%s\n" "$(d $w "$i")" >> $S/pH2q.txt; done
echo "GATES base=$base" >> $S/jdrive.log
