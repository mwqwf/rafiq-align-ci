#!/bin/bash
# hsx.sh <name> <parent> <riw=hafs> <urlt> <L|A> <surahs> <liveSha>
B=$(dirname $0); rw=$($B/gen.sh $5 $6)
$B/hs.sh "$1" "$2" hafs "$4" "$6" "$rw" "pH4 $1: مضغوط بقياس السماع على الحيّ $7 — إعادة بنائه من مراسٍ مسموعة"
