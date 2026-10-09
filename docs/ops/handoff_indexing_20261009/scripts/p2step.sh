#!/bin/bash
# الاستعمال: p2step.sh <مجلّد الأوامر> "<وصف>" — يدفع P1 ثمّ ينتظر أجوبتها ثمّ يدفع الباقي ويطبع النتائج
S=/tmp/claude-0/-home-claude/73343a78-67de-5d83-95ae-5c563459823a/scratchpad
exec 8>$S/p2step.lock; flock 8
D=$1; M=$2; T=$(mktemp -d -p $S stepXXXX); mkdir $T/a $T/b
mv $D/*_P1[._]*json $T/a/; mv $D/*.json $T/b/
[ -z "$(ls $T/a)" ] && { echo "⛔ لا أوامر P1 — توقّف"; mv $T/b/*.json $D/; exit 1; }
L1=$(cd $T/a; ls | sed 's/\.json$//'); L4=$(cd $T/b; ls | grep _P4[._] | sed 's/\.json$//'); L2=$(cd $T/b; ls | grep _P2[._] | sed 's/\.json$//')
$S/pushcmds.sh $T/a "ops: فكّ تجميد — $M" | tail -1
cd /home/claude/rafiq-align-ci
w(){ for i in $(seq 1 400); do timeout 40 git pull -q --no-rebase origin main >/dev/null 2>&1; ok=1; for f in $1; do [ -f ops/out/$f.txt ] || ok=0; done; [ $ok = 1 ] && return; sleep 20; done; echo "⏳ انتهت المهلة"; exit 2; }
w "$L1"; for f in $L1; do grep -h "رُفع\|⛔" ops/out/$f.txt | cut -c1-80; done
$S/pushcmds.sh $T/b "ops: ترقية — $M" | tail -1
w "$L4"; for f in $L2; do echo "$f"; grep -hE "جُمّد|⛔" ops/out/$f.txt | sort -u | cut -c1-200; done; for f in $L4; do tail -1 ops/out/$f.txt | cut -c1-100; done
