#!/bin/bash
# dfM.sh <اسم> <parent> <base> <sha8> rewindow
B=$(dirname $0); rw="$5"; sur=$(echo "$rw"|tr ',' '\n'|cut -d: -f1|sort -un|paste -sd,)
j=$(python3 -c 'import json,sys;a=sys.argv;print(json.dumps({"action":"dispatch","workflow":"ctc_splice.yml","inputs":{"parent":a[1],"riwaya":"hafs","url_template":a[6],"surahs":a[2],"mode":"dualfix","base_key":a[3],"rewindow":a[4],"reason":"pH4 "+a[5]+": تصحيحُ حدودٍ متبقّية بعد heard (فوق "+a[7]+")"}},ensure_ascii=False))' "$2" "$sur" "$3" "$rw" "$1" "$6" "$4")
$B/put.sh "$1" "$j"
