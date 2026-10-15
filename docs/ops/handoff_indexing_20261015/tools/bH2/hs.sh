#!/bin/bash
# hs.sh <name> <parent> <riw> <urlt> <surahs> <rewindow> <reason> — ctc_splice بوضع heard
B=$(dirname $0)
j=$(python3 -c 'import json,sys;a=sys.argv;print(json.dumps({"action":"dispatch","workflow":"ctc_splice.yml","inputs":{"parent":a[1],"riwaya":a[2],"url_template":a[3],"surahs":a[4],"mode":"heard","rewindow":a[5],"reason":a[6]}},ensure_ascii=False))' "$2" "$3" "$4" "$5" "$6" "$7")
$B/put.sh "$1" "$j"
