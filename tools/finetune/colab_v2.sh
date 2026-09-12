#!/usr/bin/env bash
# 🎓 **الجولةُ الثانية `tuned-v2` بتسويءِ التدريب (D-270)** — خليّةُ كولاب سطرٌ واحد:
#
#   !curl -sSL -A Mozilla -o /content/run.sh "https://pub-2c2e1dcd92e84a2898820dd38d3e09e6.r2.dev/finetune/colab_v2.sh?t=$(date +%s)" \
#     && PUT_LAST='…' PUT_BEST='…' PUT_GGML='…' PUT_LOG='…' bash /content/run.sh
#
#   (روابطُ PUT من `python tools/finetune/sign_put.py` على جهاز المالك — مفتاحٌ واحدٌ لكلٍّ، بلا سرّ.)
#
# ⭐ **المعماريّةُ الجديدة (2026-09-11) — لا درايف ولا بناءٌ على كولاب:**
#   ضاعت خمسُ جولاتٍ لأنّ كولاب المجّانيّ كان يبني البياناتِ بنفسه (ساعةٌ على معالجَين ضعيفَين ومصحفٌ كاملٌ
#   لكلِّ قارئ) ثم يموت، ودرايفُ لا يُركَّب بلا نقرةٍ يدويّة. فصار كلُّ ثقيلٍ خارجَ كولاب:
#   ١) **البياناتُ تُبنى في GitHub Actions** (‏`.github/workflows/finetune-prep.yml`، أربعُ مهامَّ متوازية على شبكة
#      GitHub) وتُرفع إلى R2 أجزاءً `finetune/data_v2/g*.tar` — مرّةً واحدة.
#   ٢) **كولاب ينزّل ويدرّب فقط:** دقائقُ للتنزيل ثم ~25 دقيقة تدريب على T4 (قياسُ v1: 1852 خطوة في 24 د).
#   ٣) **نقطةُ الحفظ الكاملة تُرفع إلى R2** كلَّ 300 خطوة برابط PUT موقّع، وتُستأنف من R2 عند كلِّ تشغيل
#      ⇒ انقطاعُ كولاب يكلّف دقائقَ، وأيُّ متصفّحٍ يعيد التشغيلَ من حيث وقف.
#   ٤) **التحويلُ إلى ggml q8_0 في بايثون** (‏`quantize_q8.py`، مُبرهَنٌ 0.0059٪ فرقاً عن quantize الأصلي)
#      بلا بناءِ whisper.cpp — ويُرفع الناتجُ إلى R2 ليُقاس على المحاكي.
#
# ⛔ **ولا يُحكم على هذا النموذج بالدقّة وحدَها**: بوّابةُ الحكم زوجٌ — الدقّةُ ترتفع **والاتّهامُ الكاذبُ لا يرتفع**.
set -euo pipefail

PUB=https://pub-2c2e1dcd92e84a2898820dd38d3e09e6.r2.dev
UA="Mozilla/5.0 (QuranRafiq finetune)"              # r2.dev يردّ 403 على وكلاءَ افتراضيّين
TAG=${TAG:-v2}                                        # v3: TAG=v3 EXTRA='--target norm --no-trim' (بادئة R2 مستقلّة out_$TAG)
EXTRA=${EXTRA:-}                                      # وسائطُ إضافية تُمرَّر إلى train.py كما هي
W=${W:-/content/ft}; DATA=$W/data; OUT=$W/out_$TAG
PARTS=${PARTS:-"g0 g1 g2 g3"}
AUG=${AUG:-0.5}; EPOCHS=${EPOCHS:-2.0}; SAVE_EVERY=${SAVE_EVERY:-300}; EVAL_EVERY=${EVAL_EVERY:-400}
mkdir -p "$W" "$DATA" "$OUT"
ts() { date -u +%H:%M:%S; }

echo "▶ $(date -u) — tuned-$TAG · aug=$AUG · epochs=$EPOCHS · extra=[$EXTRA]"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader \
  || { echo "⛔ لا معالجَ رسوميّ — Runtime ▸ Change runtime type ▸ T4 ثم أعد التشغيل"; exit 2; }
python3 -c "import soundfile" 2>/dev/null || pip install -q soundfile

# ── ١) العدّة (أحدثُ نسخةٍ من R2 دائماً) ────────────────────────────────────────
for f in train.py quantize_q8.py; do
  curl -sSL -A "$UA" -o "$W/$f" "$PUB/finetune/$f?t=$(date +%s)"
done

# ── ٢) البياناتُ من R2 (مبنيّةٌ في GitHub Actions) — كلُّ جزءٍ مرّةً واحدة ─────────
for p in $PARTS; do
  [ -f "$DATA/.done_$p" ] && { echo "$(ts) 📦 $p موجود"; continue; }
  echo "$(ts) ⬇️ $p.tar …"
  curl -sSL -f -A "$UA" -o "$W/$p.tar" "$PUB/finetune/data_v2/$p.tar" \
    || { echo "⛔ الجزءُ $p غيرُ موجودٍ على R2 — لم تكتمل مهمّةُ البناء؟ (gh run list -w finetune-prep)"; exit 3; }
  tar -xf "$W/$p.tar" -C "$DATA" && rm -f "$W/$p.tar" && touch "$DATA/.done_$p"
  # 🔎 D-294: تدقيقُ العناوين إن وُجد (تصفيةُ v4 بـ--min-match تقرأ <data>/<part>/audit.json)
  curl -sSL -f -A "$UA" -o "$DATA/$p/audit.json" "$PUB/finetune/data_v2/$p.audit.json?t=$(date +%s)" 2>/dev/null && echo "$(ts) 🔎 $p: تدقيقُ العناوين موجود" || true
  curl -sSL -f -A "$UA" -o "$DATA/$p/audit.json" "$PUB/finetune/data_v2/$p.audit.json?t=$(date +%s)" 2>/dev/null && echo "$(ts) 🔎 $p: تدقيقُ العناوين موجود" || true
  echo "$(ts) 📦 $p: $(wc -l < "$DATA/$p/manifest.jsonl") مقطعاً"
done
cat "$DATA"/g*/manifest.jsonl > "$DATA/manifest.jsonl"
echo "$(ts) 📚 المجموعة: $(wc -l < "$DATA/manifest.jsonl") مقطعاً · $(du -sh "$DATA" | cut -f1)"

# ── ٣) الاستئنافُ من R2 إن وُجدت نقطةُ حفظٍ سابقة ─────────────────────────────────
RESUME=""
if [ -d "$OUT/last" ] && [ -f "$OUT/last/state.pt" ]; then
  RESUME="--resume $OUT/last"; echo "$(ts) 🔁 استئنافٌ من نقطةٍ محليّة"
elif curl -sSL -f -A "$UA" -o "$W/last.tar" "$PUB/finetune/out_$TAG/last.tar?t=$(date +%s)"; then
  tar -xf "$W/last.tar" -C "$OUT" && rm -f "$W/last.tar"
  [ -f "$OUT/last/state.pt" ] && { RESUME="--resume $OUT/last"; echo "$(ts) 🔁 استئنافٌ من نقطة R2 ($(du -sh "$OUT/last" | cut -f1))"; }
else
  echo "$(ts) 🆕 لا نقطةَ سابقة — جولةٌ من البداية"
fi

# ── ٤) التدريب ──────────────────────────────────────────────────────────────────
PUT_LAST="${PUT_LAST:-}" PUT_BEST="${PUT_BEST:-}" python3 "$W/train.py" \
  --data "$DATA" --out "$OUT" --aug-p "$AUG" --epochs "$EPOCHS" \
  --save-every "$SAVE_EVERY" --eval-every "$EVAL_EVERY" $RESUME $EXTRA 2>&1 | tee -a "$W/train_$TAG.log"

# ── ٥) التحويلُ إلى ggml q8_0 (بايثون خالص) والرفع ────────────────────────────────
SRC="$OUT/best"; [ -d "$SRC" ] || { SRC="$OUT/final"; echo "⚠️ لا best (لم يتحسّن WER المحجوز) — أحوّل final"; }
cd "$W"
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
mkdir -p "$W/ggml"
python3 whisper.cpp/models/convert-h5-to-ggml.py "$SRC" "$W/whisper" "$W/ggml" | tail -2
python3 "$W/quantize_q8.py" "$W/ggml/ggml-model.bin" "$W/ggml/ggml-q8_0.bin"
ls -l "$W/ggml"
[ -n "${PUT_GGML:-}" ] && curl -sS -f -X PUT -T "$W/ggml/ggml-q8_0.bin" "$PUT_GGML" && echo "☁️ ggml-q8_0.bin مرفوع"
[ -n "${PUT_LOG:-}" ]  && curl -sS -f -X PUT -T "$OUT/train_log.jsonl" "$PUT_LOG" && echo "☁️ train_log.jsonl مرفوع"

echo "✅ $(date -u) — انتهت الجولة. آخرُ تقييم:"
grep -E "eval|DONE" "$W/train_$TAG.log" | tail -4
echo "⛔ ولا يُشحن حتى يُقاس على المحاكي بالبوّابتين: الدقّةُ ترتفع والاتّهامُ الكاذبُ لا يرتفع."
