#!/usr/bin/env bash
# 🔁 تحويلُ نموذج HF مضبوطٍ إلى ggml ثم q8_0 — بايثون خالص بلا بناءِ whisper.cpp (‏`quantize_q8.py` مُبرهَن 0.0059٪).
#   bash tools/finetune/to_ggml.sh <مجلّد HF (best/final)> <مجلّد المخرَج> [مجلّد عمل للاستنساخ]
# يُستعمل من CI (‏finetune-train-cpu.yml) ومن أيّ جهاز فيه torch+transformers. الناتج: <out>/ggml-q8_0.bin
set -euo pipefail
SRC=${1:?مجلّد HF}; OUT=${2:?مجلّد المخرَج}; W=${3:-$(pwd)}
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$OUT" "$W"; cd "$W"
[ -d whisper.cpp ] || git clone -q --depth 1 https://github.com/ggml-org/whisper.cpp
[ -d whisper ]     || git clone -q --depth 1 https://github.com/openai/whisper
# convert-h5-to-ggml يقرأ vocab.json/added_tokens.json (المعجم البطيء) — save_pretrained الحديث يكتب tokenizer.json فقط
python3 - "$SRC" <<'PY'
import json, sys
from transformers import AutoTokenizer
src = sys.argv[1]; t = AutoTokenizer.from_pretrained(src)
v = t.get_vocab(); added = t.get_added_vocab(); base = {k: i for k, i in v.items() if k not in added}
json.dump(base, open(f"{src}/vocab.json", "w"), ensure_ascii=False); json.dump(added, open(f"{src}/added_tokens.json", "w"), ensure_ascii=False)
print("vocab", len(base), "added", len(added))
PY
python3 whisper.cpp/models/convert-h5-to-ggml.py "$SRC" "$W/whisper" "$OUT" | tail -2
python3 "$HERE/quantize_q8.py" "$OUT/ggml-model.bin" "$OUT/ggml-q8_0.bin"
ls -l "$OUT"
