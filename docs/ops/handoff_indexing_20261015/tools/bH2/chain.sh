#!/bin/bash
# chain.sh <وسم> <مفتاح الحيّ timings/..> <riw> <urlt> <سور مفصولة> <حجم الدفعة> — heard نافذة كاملة متسلسلة
S=/tmp/claude-0/-home-user/06b0cdc4-1efe-58b9-bd35-06b0a18e1af5/scratchpad; B=$S/bH2
tag=$1; base=$2; riw=$3; urlt=$4; list=$5; bs=${6:-5}
cnt="1:7,2:286,3:200,4:176,5:120,6:165,7:206,8:75,9:129,10:109,11:123,12:111,13:43,14:52,15:99,16:128,17:111,18:110,19:98,20:135,21:112,22:78,23:118,24:64,25:77,26:227,27:93,28:88,29:69,30:60,31:34,32:30,33:73,34:54,35:45,36:83,37:182,38:88,39:75,40:85,41:54,42:53,43:89,44:59,45:37,46:35,47:38,48:29,49:18,50:45,51:60,52:49,53:62,54:55,55:78,56:96,57:29,58:22,59:24,60:13,61:14,62:11,63:11,64:18,65:12,66:12,67:30,68:52,69:52,70:44,71:28,72:28,73:20,74:56,75:40,76:31,77:50,78:40,79:46,80:42,81:29,82:19,83:36,84:25,85:22,86:17,87:19,88:26,89:30,90:20,91:15,92:21,93:11,94:8,95:8,96:19,97:5,98:8,99:8,100:11,101:11,102:8,103:3,104:9,105:5,106:4,107:7,108:3,109:6,110:3,111:5,112:4,113:5,114:6"
fin(){ until grep -q "$1 ->" $S/pH2pool.log; do sleep 20; done; id=$(grep "$1 ->" $S/pH2pool.log|awk '{print $NF}'); until [ "$(gh api repos/mwqwf/rafiq-align-ci/actions/runs/$id --jq .status)" = completed ]; do sleep 30; done; gh api repos/mwqwf/rafiq-align-ci/actions/runs/$id --jq .conclusion; }
IFS=, read -ra A <<< "$list"; i=0; b=0; cur=$base
while [ $i -lt ${#A[@]} ]; do
  grp=("${A[@]:$i:$bs}"); sur=$(IFS=,; echo "${grp[*]}")
  rw=$(python3 -c "
import sys
c=dict(x.split(':') for x in '$cnt'.split(','))
print(','.join(f'{s}:1-{c[s]}' for s in '$sur'.split(',')))")
  b=$((b+1)); n=${tag}_B$b; since=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  python3 -c 'import json,sys;a=sys.argv;print(json.dumps({"action":"dispatch","workflow":"ctc_splice.yml","inputs":{"parent":a[1],"riwaya":a[2],"url_template":a[3],"surahs":a[4],"mode":"heard","rewindow":a[5],"reason":"pH2 "+a[6]+": مضغوطٌ بقياس السماع (heard نافذة السورة كاملة)"}},ensure_ascii=False))' "$cur" "$riw" "$urlt" "$sur" "$rw" "$n" | awk -v n="$n" '{print n"\t"$0}' >> $S/pH2q.txt
  r=$(fin $n); echo "$n [$sur] $r" >> $S/chain_$tag.log
  if [ "$r" = success ]; then x=$($B/cand.sh $(echo $base | sed -E 's#timings(-staging)?/([a-z]+)/([a-z_]+)\..*#\2/\3#') $since); [ -n "$x" ] && cur=$x; fi
  echo "cur=$cur" >> $S/chain_$tag.log
  i=$((i+bs))
done
echo "DONE final=$cur" >> $S/chain_$tag.log
