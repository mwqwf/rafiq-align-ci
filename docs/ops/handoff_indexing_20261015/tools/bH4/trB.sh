#!/bin/bash
# trB.sh <اسم> س:من-إلى,... — rewindow على المدى المعطوب
B=$(dirname $0); rw="$2"; sur=$(echo "$rw"|tr ',' '\n'|cut -d: -f1|paste -sd,)
$B/hs.sh "$1" timings/hafs/trabulsi.jz hafs "https://server10.mp3quran.net/trabulsi/{s:03d}.mp3" "$sur" "$rw" "pH4 $1: مضغوطٌ بقياس السماع على الحيّ 0683796a — إعادة بنائه من مراسٍ مسموعة"
