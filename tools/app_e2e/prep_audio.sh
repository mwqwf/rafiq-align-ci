#!/usr/bin/env bash
# 🎧 يحضّر تسجيلاتِ السيناريوهات (16k أحاديّ s16) من مصادرَ عامّةٍ منشورة — لا صوتَ مستخدم.
set -euo pipefail
mkdir -p e2e && cd e2e
UA="Mozilla/5.0 (QuranRafiq app e2e)"
get(){ curl -sSLf --retry 4 --retry-delay 5 --retry-all-errors -A "$UA" -o "$1" "$2"; }
get h22.mp3 https://everyayah.com/data/Husary_128kbps/018022.mp3
get h23.mp3 https://everyayah.com/data/Husary_128kbps/018023.mp3
get bas.mp3 https://everyayah.com/data/Husary_128kbps/001001.mp3
get q.jz "https://pub-2c2e1dcd92e84a2898820dd38d3e09e6.r2.dev/timings/qalun/husary_qalun.jz"
get q018.mp3 https://server13.mp3quran.net/husr/Rewayat-Qalon-A-n-Nafi/018.mp3
W(){ ffmpeg -loglevel error -y "$@" -ac 1 -ar 16000 -c:a pcm_s16le; }
W -i h22.mp3 hafs_start.wav
D=$(ffprobe -v error -show_entries format=duration -of csv=p=0 h22.mp3)
MID=$(python3 -c "print(round(float('$D')*0.45,2))")
ffmpeg -loglevel error -y -ss "$MID" -i h22.mp3 -i h23.mp3 -filter_complex "[0:a][1:a]concat=n=2:v=0:a=1" -ac 1 -ar 16000 -c:a pcm_s16le hafs_mid.wav
ffmpeg -loglevel error -y -i bas.mp3 -i h22.mp3 -filter_complex "[0:a][1:a]concat=n=2:v=0:a=1" -ac 1 -ar 16000 -c:a pcm_s16le hafs_basmala.wav
read S E < <(python3 - <<'PY'
import gzip, zlib, json
b = open("q.jz", "rb").read()
try: t = gzip.decompress(b)
except Exception: t = zlib.decompress(b)
e = {x["ayahId"]: x for x in json.loads(t)["entries"]}
print(e["18:22"]["startMs"] / 1000, e["18:23"]["endMs"] / 1000)
PY
)
ffmpeg -loglevel error -y -ss "$S" -to "$E" -i q018.mp3 -ac 1 -ar 16000 -c:a pcm_s16le qalun_start.wav
for f in *.wav; do echo "$f $(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f")"; done
