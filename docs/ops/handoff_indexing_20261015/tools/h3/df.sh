#!/bin/bash
# df.sh <name> <parent-key> <riw> <url> <surah> <rewindow> <reason>
python3 -c 'import json,sys;print(json.dumps({"action":"dispatch","workflow":"ctc_splice.yml","inputs":{"parent":sys.argv[2],"url_template":sys.argv[4],"riwaya":sys.argv[3],"surahs":sys.argv[5],"mode":"dualfix","base_key":sys.argv[2],"rewindow":sys.argv[6],"reason":sys.argv[7]}},ensure_ascii=False))' "$@"
