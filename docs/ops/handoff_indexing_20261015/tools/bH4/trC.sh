#!/bin/bash
# trC.sh <اسم> <parent> <sha8 للأب> س:من-إلى,...
B=$(dirname $0); rw="$4"; sur=$(echo "$rw"|tr ',' '\n'|cut -d: -f1|paste -sd,)
$B/hs.sh "$1" "$2" hafs "https://server10.mp3quran.net/trabulsi/{s:03d}.mp3" "$sur" "$rw" "pH4 $1: مضغوطٌ بقياس السماع (فوق $3) — إعادة بنائه من مراسٍ مسموعة"
