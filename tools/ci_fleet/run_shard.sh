#!/usr/bin/env bash
# سائق الشريحة داخل عدّاء GitHub.
# ⛔ لا يعدّل حرفاً من tools/alignment أو tools/cloud — يستهلكها كما هي.
#
# ⛔ مبدأ حاكم بعد سقوط smoke ‏33581431477: **سقوط قارئٍ واحد لا يُسقط الشريحة.**
#    شريحةٌ فيها 2–3 قراء، وأول قارئٍ رديء كان سيُهدر المهمة كلها — وفي التشغيل
#    الكامل عشرين مهمة. فكل قارئ يُعزل، ويُحصى، ويُطبع جردٌ في النهاية.
set -uo pipefail          # ⛔ بلا -e عمداً: العزل مقصود لا مصادفة

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
# برهانٌ في السجل الحيّ أن المتغيّرات تصل العملية الابنة فعلاً لا الـworkflow وحده:
env | grep -E "^(ALIGN_REFINE|WHISPER_THREADS|WHISPER_AC)=" | sed "s/^/بيئة العامل: /"
mkdir -p "$ROOT/logs-copy"

# ⛔ الروايات التي تقبلها `batch_run.py --riwaya`. كانت ثلاثاً في `main` فأسقطت
#    أول smoke على `soufi_sousi` (‏invalid choice) — وتبيّن أن العيب أصاب
#    الخوادم الخمسة أيضاً لا جبهتنا وحدها (‏github-b9)، وأُصلح في `8202d40`:
#    الست مدعومة والعدّ يبقى KUFI الافتراضي للجميع. ومن لم يُدعم بعدُ يُتخطّى
#    بإعلانٍ صريح — ⛔ ولا يُحذف سطره من القائمة كي لا يُزاح ترتيب القسمة.
SUPPORTED_RIWAYAT="hafs warsh qalun douri sousi shuba"

ok_count=0; fail_count=0; skip_count=0; checked_refine=0
declare -a FAILED=() SKIPPED=()

supported() {
  case " $SUPPORTED_RIWAYAT " in *" $1 "*) return 0;; *) return 1;; esac
}

run_one() {          # $1=reciterId $2=riwaya $3=baseUrl $4=surahs
  local rid="$1" riwaya="$2" base="$3" surahs="$4" rc=0
  if ! supported "$riwaya"; then
    echo "⏭ $rid: الرواية '$riwaya' لا تقبلها العدة بعد — تُتخطّى بإعلان صريح"
    skip_count=$((skip_count + 1)); SKIPPED+=("$rid:$riwaya"); return 0
  fi
  echo "▶ $rid ($riwaya) سور=$surahs"
  # ⛔ التوازي هنا لا في العدة (عيبٌ قاتل كشفه github-f4): `batch_run.py`
  #    **تسلسليّ بلا توازٍ داخلي** — فحصتُه: صفر Thread/Pool/multiprocessing،
  #    و`JOBS` كان يُطبَع ولا يُستعمل. ⇒ عدّاءٌ بأربع أنوية يعمل بنواةٍ واحدة،
  #    والقارئ 5–6 ساعات فيقتله سقف الست ⇒ **صفر قارئ مكتمل**.
  #    العلاج: JOBS عمليات `batch_run` متوازية، كلٌّ على **حزمة سورٍ** خاصة،
  #    على مجلد الدفعة نفسه (الملفات لكل سورة فالحزم متباينة لا تتصادم).
  #    ⛔ والقسمة بمجموع الآي لا بعدد السور — أبطأُ حزمةٍ هي زمن القارئ كله.
  if [ "$surahs" = "1-114" ] && [ "${JOBS:-1}" -gt 1 ]; then
    local packs pids=() k=0
    packs="$("$PY" "$ROOT/tools/ci_fleet/make_bins.py" "$JOBS")" || packs=""
    if [ -n "$packs" ]; then
      for pack in $packs; do
        k=$((k + 1))
        "$PY" "$ROOT/tools/alignment/batch_run.py" \
              --reciter "$rid" --riwaya "$riwaya" --base "$base" --surahs "$pack" \
              > "$ROOT/logs-copy/$rid.part$k.log" 2>&1 &
        pids+=($!)
      done
      echo "  ⇉ $k حزمة متوازية (بمجموع الآي)"
      for p in "${pids[@]}"; do wait "$p" || rc=$?; done
      cat "$ROOT/logs-copy/$rid".part*.log > "$ROOT/logs-copy/$rid.log" 2>/dev/null
      # ⛔ تمريرة ختامية إلزامية: كل عملية بَنَت فهرس حزمتها وحدها. هذه تبني
      #    الفهرس الكامل، ولا تُعيد تفريغ شيء (‏batch_run لا يعيد سورةً لها json).
      "$PY" "$ROOT/tools/alignment/batch_run.py" \
            --reciter "$rid" --riwaya "$riwaya" --base "$base" --surahs "1-114" \
            >> "$ROOT/logs-copy/$rid.log" 2>&1 || rc=$?
    fi
  fi
  if [ "$rc" -eq 0 ] && [ ! -s "$ROOT/logs-copy/$rid.log" ]; then
    "$PY" "$ROOT/tools/alignment/batch_run.py" \
          --reciter "$rid" --riwaya "$riwaya" --base "$base" --surahs "$surahs" \
          > "$ROOT/logs-copy/$rid.log" 2>&1 || rc=$?
  fi
  tail -n 40 "$ROOT/logs-copy/$rid.log"
  if [ "$rc" -ne 0 ]; then
    echo "❌ $rid: batch_run rc=$rc — يُعزل ويُواصَل"
    fail_count=$((fail_count + 1)); FAILED+=("$rid:batch_run=$rc"); return 0
  fi
  # عدّ الملفات بعد التوازي — الحارس اللاحق يفحصها، وهذا سطرٌ للسجل لا حكم.
  echo "  📄 ملفات السور: $(ls "$ROOT/tools/alignment/work/batch_$rid"/s*.json 2>/dev/null | wc -l)/114"
  # ⛔ حارس الإقلاع (اقتراح github-7d، كلفته ثانيتان): فحصي في بناء الصورة يثبت
  #    أن وحدة `refine` **تُستورَد**، ولا يثبت أنها **نفَذت** — وهذان أمران
  #    مختلفان، وشاهدهما الحيّ `tareq_qalun` (‏refineVersion=none · medTargeted=0
  #    مع 1205 مداخل MED). فإن خرج أول فهرسٍ في الشريحة بلا صقل **وفيه MED**،
  #    تُوقَف الشريحة كلها بدل أن تُهدر ست ساعات في إنتاج جيلٍ أول.
  if [ "$checked_refine" = "0" ]; then
    checked_refine=1
    _idx="$ROOT/tools/alignment/work/timings_${riwaya}_${rid}.jz"
    if [ -f "$_idx" ]; then
      "$PY" "$ROOT/tools/ci_fleet/refine_probe.py" "$_idx"         || { echo "⛔ الشريحة تُوقَف: الصقل لا يعمل"; return 1; }
    fi
  fi
  "$PY" "$ROOT/tools/ci_fleet/stage_upload.py" --reciter "$rid" --riwaya "$riwaya" \
        --expect-surahs "$surahs" --log "$ROOT/logs-copy/$rid.log" || rc=$?
  if [ "${rc:-0}" -ne 0 ]; then
    echo "🛑 $rid: لم يُرفع (حارس أو خطأ) rc=$rc — يُعزل ويُواصَل"
    fail_count=$((fail_count + 1)); FAILED+=("$rid:upload=$rc"); return 0
  fi
  ok_count=$((ok_count + 1))
}

summary() {
  echo "──────── جرد الشريحة $SHARD/$SHARDS ────────"
  echo "نجح: $ok_count · سقط: $fail_count · تُخطّي: $skip_count"
  [ "${#FAILED[@]}"  -gt 0 ] && printf '  ❌ %s\n' "${FAILED[@]}"
  [ "${#SKIPPED[@]}" -gt 0 ] && printf '  ⏭ %s\n' "${SKIPPED[@]}"
  # ⛔ الشريحة تفشل **فقط** إن لم ينجح فيها شيء ولم يكن الباقي تخطّياً مفهوماً —
  #    فالنجاح الجزئي مخرَجٌ نافع لا فشل، والسجل يحمل التفصيل.
  if [ "$ok_count" -eq 0 ] && [ "$fail_count" -gt 0 ]; then
    echo "⛔ الشريحة بلا أي نجاح — تُعلَن فاشلة"; return 1
  fi
  return 0
}

if [ "${SMOKE:-false}" = "true" ]; then
  # ── تجربة قصيرة قبل أي تعميم: قارئ واحد وسورة واحدة قصيرة ──────────────
  rid="${SMOKE_RECITER:-}"
  if [ -z "$rid" ]; then
    # ⛔ أول قارئ **برواية مدعومة** لا أول سطر: أول سطر في القائمة الحيّة
    #    (‏soufi_sousi) رواية غير مقبولة فأسقط أول smoke في السطر الأول.
    rid="$(awk -F'\t' -v s=" $SUPPORTED_RIWAYAT " \
           '!/^#/ && NF>=4 && index(s, " " $2 " ") {print $1; exit}' "$LIST")"
  fi
  line="$(awk -F'\t' -v r="$rid" '!/^#/ && $1==r {print; exit}' "$LIST")"
  [ -n "$line" ] || { echo "⛔ لا سطر للقارئ $rid في $LIST"; exit 1; }
  run_one "$rid" "$(echo "$line" | cut -f2)" "$(echo "$line" | cut -f3)" "${SMOKE_SURAHS:-108}"
  summary; exit $?
fi

# ── التوزيع بالقارئ، بنفس قاعدة run_fleet.py حرفياً: i % SHARDS == SHARD ──
# (‏b9: «مصفوفتك 0..19 بـSHARDS=20 تعمل كما هي بلا تعديل سطر».)
i=0
while IFS=$'\t' read -r rid riwaya base prio rest; do
  case "$rid" in ''|'#'*) continue;; esac
  [ -n "${prio:-}" ] || continue
  if [ $(( i % SHARDS )) -eq "$SHARD" ]; then
    run_one "$rid" "$riwaya" "$base" "1-114" || { echo "⛔ توقّف مبكر"; summary; exit 1; }
  fi
  i=$(( i + 1 ))
done < "$LIST"
echo "SHARD_DONE $SHARD/$SHARDS"
summary
