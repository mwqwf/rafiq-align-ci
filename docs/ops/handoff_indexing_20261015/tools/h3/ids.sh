#!/bin/bash
# ids.sh <tag> — يجمع معرّفات التشغيلات لأوامر ${tag}* الأحدث إلى $H/<tag>_ids.txt
H=$(dirname $0); cd $H/../wt_pH3; git fetch -q origin main 2>/dev/null; : > $H/$1_ids.txt
for p in $(git ls-tree origin/main --name-only ops/out/ | grep -E "pH3_$1(sh|op|cn|s1|s2|s3|s4|dg)\.txt"); do n=$(basename $p .txt | sed 's/.*pH3_//'); id=$(git show origin/main:$p | grep -oE 'runs/[0-9]+' | head -1 | cut -d/ -f2); [ -n "$id" ] && echo "$n:$id" >> $H/$1_ids.txt; done; cat $H/$1_ids.txt | tr '\n' ' '
