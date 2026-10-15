#!/bin/bash
# hs.sh <name> <parent> <riw> <url> <surahs> <rewindow> <reason> — ctc_splice بوضع heard
python3 -c 'import json,sys;print(json.dumps({"action":"dispatch","workflow":"ctc_splice.yml","inputs":{"parent":sys.argv[1],"url_template":sys.argv[3],"riwaya":sys.argv[2],"surahs":sys.argv[4],"mode":"heard","rewindow":sys.argv[5],"reason":sys.argv[6]}},ensure_ascii=False))' "${@:2}"
