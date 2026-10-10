#!/bin/bash
# op.sh <key> — حكم المطالع
P=/tmp/claude-0/-home-user/655bf1da-3ade-5c39-b73e-f25874555b84/scratchpad/pE
k=$1; fn=$(basename $k); r=${fn%%.*}; flat=$(echo $k|tr / _)
$P/put.sh o_$r "{\"action\":\"tool\",\"tool\":\"index_qa/dump_state.py\",\"args\":[\"state/$flat.openers.json\",\"verdict\",\"sha256\",\"late\",\"lateConfirmed\",\"swallowed\",\"fatal\"]}" 2>/dev/null|head -1
