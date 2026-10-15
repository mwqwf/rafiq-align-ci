#!/bin/bash
# sp.sh <name> <parent sha8> <surahs> <reason>
B=$(dirname $0)
python3 -c 'import json,sys;print(json.dumps({"action":"dispatch","workflow":"ctc_splice.yml","inputs":{"parent":"timings-staging/qalun/maroush_qalun.%s.jz"%sys.argv[1],"url_template":"https://archive.org/download/Kamal-Almaroush-Qalon/{s:03d}.mp3","riwaya":"qalun","surahs":sys.argv[2],"mode":"dualfix","base_key":"timings-staging/qalun/maroush_qalun.3d4e8af3.jz","reason":sys.argv[3]}},ensure_ascii=False))' "$2" "$3" "$4"
