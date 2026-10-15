#!/bin/bash
# df.sh <اسم> <مفتاح staging> <riw> <urlt> <rewindow> — dualfix مفرد
S=/tmp/claude-0/-home-user/06b0cdc4-1efe-58b9-bd35-06b0a18e1af5/scratchpad
sur=$(echo "$5"|tr ',' '\n'|cut -d: -f1|sort -un|paste -sd,)
python3 -c 'import json,sys;a=sys.argv;print(json.dumps({"action":"dispatch","workflow":"ctc_splice.yml","inputs":{"parent":a[1],"riwaya":a[2],"url_template":a[3],"surahs":a[4],"mode":"dualfix","base_key":a[1],"rewindow":a[5],"reason":"pH2 "+a[6]+": تصحيحُ حدودٍ متبقّية بعد heard (dualfix مفرد)"}},ensure_ascii=False))' "$2" "$3" "$4" "$sur" "$5" "$1" | awk -v n="$1" '{print n"\t"$0}' >> $S/pH2q.txt
