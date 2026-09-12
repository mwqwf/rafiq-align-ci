#!/usr/bin/env bash
# 🎓 تحويل نموذج HF المضبوط إلى ggml q8_0 (whisper.cpp) وقياسه على عيّنة G1 (202 آية) مقابل النموذج المشحون.
# الاستعمال: bash convert_and_bench.sh /content/out/best /content/ggml [PUT_URL_q8] [PUT_URL_hyps]
set -euo pipefail
SRC=${1:-/content/out/best}; OUT=${2:-/content/ggml}; PUT_Q8=${3:-}; PUT_HYPS=${4:-}
PUB=https://pub-2c2e1dcd92e84a2898820dd38d3e09e6.r2.dev
mkdir -p "$OUT"; cd /content
[ -d whisper.cpp ] || git clone --depth 1 https://github.com/ggml-org/whisper.cpp
[ -d whisper ] || git clone --depth 1 https://github.com/openai/whisper
cd whisper.cpp
[ -x build/bin/whisper-quantize ] || (cmake -B build -DCMAKE_BUILD_TYPE=Release -DWHISPER_BUILD_EXAMPLES=ON -DWHISPER_BUILD_TESTS=OFF >/dev/null && cmake --build build --config Release -j2 >/dev/null)
ls build/bin | head
# convert-h5-to-ggml يقرأ vocab.json/added_tokens.json (المعجم البطيء) — save_pretrained الحديث يكتب tokenizer.json فقط
python3 - <<PY
import json
from transformers import AutoTokenizer
t = AutoTokenizer.from_pretrained("$SRC")
v = t.get_vocab(); added = t.get_added_vocab()
base = {k: i for k, i in v.items() if k not in added}
json.dump(base, open("$SRC/vocab.json", "w"), ensure_ascii=False)
json.dump(added, open("$SRC/added_tokens.json", "w"), ensure_ascii=False)
print("vocab", len(base), "added", len(added))
PY
python3 models/convert-h5-to-ggml.py "$SRC" /content/whisper "$OUT"
./build/bin/whisper-quantize "$OUT/ggml-model.bin" "$OUT/ggml-q8_0.bin" q8_0
ls -l "$OUT"
# النموذج المشحون للمقارنة
[ -f "$OUT/shipped-q8_0.bin" ] || curl -sSL -o "$OUT/shipped-q8_0.bin" "$PUB/models/whisper-tiny-ar-quran/ggml-q8_0.bin"
# عدّة البنشمارك (مرآة المحرك)
mkdir -p /content/bench && cd /content/bench
for f in sample.json scorer.py score.py remote_whisper.py make_public_job.py misaligned.json; do curl -sSL -o "$f" "$PUB/tools-snapshots/finetune/bench/$f"; done
mkdir -p work && cp misaligned.json work/
# r2.dev يردّ 403 على وكيل بايثون الافتراضي (نفس درس prep.py) — وكيلٌ عامّ لكل النداءات
python3 - <<PY
s = open("remote_whisper.py", encoding="utf-8").read()
if "install_opener" not in s:
    s = s.replace("import urllib.request", "import urllib.request
_op = urllib.request.build_opener(); _op.addheaders = [('User-Agent', 'Mozilla/5.0 (QuranRafiq bench)')]; urllib.request.install_opener(_op)", 1)
    open("remote_whisper.py", "w", encoding="utf-8").write(s)
print("UA patched:", "install_opener" in s)
PY
python3 make_public_job.py sample.json work/job.json
export WHISPER_CLI=/content/whisper.cpp/build/bin/whisper-cli
run_bench () {  # model hyps
  sed -e "s#^WHISPER = .*#WHISPER = \"$WHISPER_CLI\"#" -e "s#^MODEL = .*#MODEL = \"$1\"#" remote_whisper.py > rw.py
  python3 rw.py --job work/job.json --out "$2" --windowed --threads 2 --model "$1" | tail -2
}
run_bench "$OUT/shipped-q8_0.bin" work/hyps_shipped.json
run_bench "$OUT/ggml-q8_0.bin" work/hyps_tuned.json
python3 score.py --hyps work/hyps_shipped.json --compare work/hyps_tuned.json --cfg proposed --exclude-misaligned | tee work/bench_result.txt
[ -n "$PUT_Q8" ] && curl -sS -X PUT -T "$OUT/ggml-q8_0.bin" "$PUT_Q8" && echo "uploaded q8"
[ -n "$PUT_HYPS" ] && (tar --warning=no-file-changed -czf /content/bench.tgz work || true) && curl -sS -X PUT -T /content/bench.tgz "$PUT_HYPS" && echo "uploaded bench"
echo ALL_DONE
