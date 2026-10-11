#!/bin/bash
# pK_pin.sh <اسم> <مفتاح> <sha8> <سورة> <run> <pins> <سبب> -> يرفع ويطبع بصمة الناتج
S=/tmp/claude-0/-home-user/655bf1da-3ade-5c39-b73e-f25874555b84/scratchpad
j=$(python3 -c "import json,sys;print(json.dumps({'action':'tool','tool':'index_qa/pin_heard.py','args':['--key',sys.argv[1],'--sha',sys.argv[2],'--surah',sys.argv[3],'--run',sys.argv[4],'--pin',sys.argv[5],'--reason',sys.argv[6],'--yes']},ensure_ascii=False))" "$2" "$3" "$4" "$5" "$6" "$7")
o=$($S/pK_put.sh $1 "$j" 2>/dev/null); f=$(basename $o .txt)
$S/pK_rd.sh $f 50 | grep -E "إلى |⛔|↑|rc=" | cut -c1-250
