#!/usr/bin/env bash
# سائق الشريحة داخل عدّاء GitHub.
# ⛔ لا يعدّل حرفاً من tools/alignment أو tools/cloud — يستهلكها كما هي.
set -euo pipefail

ROOT="/root/QuranRafiq"
PY="$ROOT/.venv/bin/python"
LIST="${LIST:-$ROOT/tools/ci_fleet/reciters_ci.tsv}"
SHARD="${SHARD:-0}"; SHARDS="${SHARDS:-1}"; JOBS="${JOBS:-2}"
export ALIGN_REFINE=1          # ⛔ الجيل الثاني إلزامي (بدونه فهارس Gen-1)
# مقابض العدة (‏b9 أضافها في 6105745 بعد قياس 8e) — نستعملها ولا نعدّل العدة.
# ⛔ قيمتاهما **قرار المشرف** لا قرار هذا السكربت: تُضبطان في `env` الخاص
#    بالـworkflow (‏WHISPER_THREADS=1 · WHISPER_AC=0). هنا نمرّرهما فقط، وإن
#    غابتا أخذت العدة افتراضها (4 و512).
export WHISPER_THREADS="${WHISPER_THREADS:-4}" WHISPER_AC="${WHISPER_AC:-512}"
echo "وصفة whisper: -t $WHISPER_THREADS · -ac ${WHISPER_AC:-(مُسقط)} · JOBS=$JOBS"
mkdir -p "$ROOT/logs-copy"

run_one() {          # $1=reciterId $2=riwaya $3=baseUrl $4=surahs
  local rid="$1" riwaya="$2" base="$3" surahs="$4"
  echo "▶ $rid ($riwaya) سور=$surahs"
  "$PY" "$ROOT/tools/alignment/batch_run.py" \
        --reciter "$rid" --riwaya "$riwaya" --base "$base" --surahs "$surahs" \
        2>&1 | tee "$ROOT/logs-copy/$rid.log"
  "$PY" "$ROOT/tools/ci_fleet/stage_upload.py" --reciter "$rid" --riwaya "$riwaya" \
        --expect-surahs "$surahs" --log "$ROOT/logs-copy/$rid.log"
}

if [ "${SMOKE:-false}" = "true" ]; then
  # ── تجربة قصيرة قبل أي تعميم: قارئ واحد وسورة واحدة قصيرة ──────────────
  rid="${SMOKE_RECITER:-}"
  if [ -z "$rid" ]; then rid="$(awk -F'\t' '!/^#/ && NF>=4 {print $1; exit}' "$LIST")"; fi
  line="$(awk -F'\t' -v r="$rid" '!/^#/ && $1==r {print; exit}' "$LIST")"
  [ -n "$line" ] || { echo "⛔ لا سطر للقارئ $rid في $LIST"; exit 1; }
  run_one "$rid" "$(echo "$line" | cut -f2)" "$(echo "$line" | cut -f3)" "${SMOKE_SURAHS:-108}"
  exit 0
fi

# ── التوزيع بالقارئ، بنفس قاعدة run_fleet.py حرفياً: i % SHARDS == SHARD ──
# (‏b9: «مصفوفتك 0..19 بـSHARDS=20 تعمل كما هي بلا تعديل سطر».)
i=0
while IFS=$'\t' read -r rid riwaya base prio rest; do
  case "$rid" in ''|'#'*) continue;; esac
  [ -n "${prio:-}" ] || continue
  if [ $(( i % SHARDS )) -eq "$SHARD" ]; then
    run_one "$rid" "$riwaya" "$base" "1-114" || echo "❌ $rid سقط — تُكمَل الشريحة"
  fi
  i=$(( i + 1 ))
done < "$LIST"
echo "SHARD_DONE $SHARD/$SHARDS"
