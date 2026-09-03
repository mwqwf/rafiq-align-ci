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

# ⛔ القائمة لا تُقرأ من الحجم المركّب مباشرةً. عبر GCS FUSE يُخبَّأ حجمُ
#    الملف، فإن أُعيد رفعه بحجمٍ مختلف قرأت المهمةُ بإزاحةٍ من الكاش القديم
#    فبدأ أول سطر من **وسط** المعرّف. وهذا بعينه ما أنتج قارئاً اسمه «en» —
#    وهي آخر حرفين من «shaheen» — بفهرسٍ كامل 114 صحيح المحتوى، مرفوعاً
#    باسمٍ لا وجود له في أي كتالوج، ولا حارس يشتكي لأن كل شيء «نجح».
case "$LIST" in
  /mnt/*)
    _local="/tmp/$(basename "$LIST")"
    if cp -f "$LIST" "$_local" 2>/dev/null && [ -s "$_local" ]; then
      if [ -f "$LIST.sha" ]; then
        _want="$(cut -c1-64 < "$LIST.sha")"
        _got="$(sha256sum "$_local" | cut -c1-64)"
        if [ "$_want" != "$_got" ]; then
          echo "⛔ بصمة القائمة لا تطابق $LIST.sha — تُقرأ ثانيةً"
          sleep 5; cp -f "$LIST" "$_local" 2>/dev/null || true
          _got="$(sha256sum "$_local" | cut -c1-64)"
          [ "$_want" = "$_got" ] || { echo "⛔ القائمة فاسدة بعد الإعادة — تُوقف الشريحة"; exit 1; }
        fi
      fi
      LIST="$_local"
      echo "📋 القائمة نُسخت محلياً: $LIST ($(wc -l < "$LIST") سطر)"
    fi
    ;;
esac

# ⛔ حارسٌ ثلاثي على كل معرّف قبل أي عمل. المعرّف يصير **اسم الفهرس** على
#    R2، فمعرّفٌ مشوّه = فهرسٌ صحيح المحتوى منسوبٌ إلى قارئٍ لا وجود له، ولا
#    يكشفه شيءٌ لاحقاً. وقد أُمسك اثنان: «en» (اقتطاع) و«trabulsi» مسبوقاً
#    بـBOM كتبه PowerShell. فالشرطان: بايتٌ غير مسموح · وطولٌ أقصر من ثلاثة.
_guard_id() {
  case "$1" in
    *[!a-zA-Z0-9_-]*) echo "⛔ معرّف فيه بايت غير مسموح: [$1]"; return 1;;
  esac
  [ "${#1}" -ge 3 ] || { echo "⛔ معرّف أقصر من ثلاثة أحرف: [$1] — بصمة اقتطاع"; return 1; }
  return 0
}
# ⛔ حارسٌ رابع: **هل للمعرّف صفٌّ حرفيٌّ في القائمة أصلاً؟** حارس الطول (≥3)
#    لا يمسك `asm` من `qasm` ولا `ifai` من `mrifai`؛ وقد رُفع فهرسٌ كامل باسم
#    `en` (من `shaheen`) وكاد يُرفع `asm`. فما لا يطابق صفّاً في `$LIST` حرفياً
#    يوقف الشريحة بخطأ صريح، لأن وجوده أصلاً برهانُ تلفٍ في القراءة.
_guard_in_list() {
  awk -F'	' -v r="$1" '!/^#/ && $1==r {found=1; exit} END{exit found?0:1}' "$LIST"
}
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

# 📡 منارة التقدّم في الخلفية — «ما لا يُرى لا يُدار» (‏github-f4). لا تُفشل
# الشريحة بحال، وتموت بموت الصدفة أو بالسطر الأخير.
BEACON_PID=""
if [ -x "$ROOT/tools/ci_fleet/progress_beacon.sh" ] || [ -f "$ROOT/tools/ci_fleet/progress_beacon.sh" ]; then
  bash "$ROOT/tools/ci_fleet/progress_beacon.sh" "$ROOT/tools/alignment/work" &
  BEACON_PID=$!
fi
stop_beacon() { [ -n "${BEACON_PID:-}" ] && kill "$BEACON_PID" 2>/dev/null; return 0; }
trap stop_beacon EXIT

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
  # ⛔ السؤال قبل العمل: **هل أنجزه أحدٌ سلفاً؟** (أمر github-f4) — الجبهتان
  #    تعملان على القائمة نفسها من طرفيها، فالتكرار وارد. والجواب **من الدلو**
  #    لا من قائمةٍ محلية: القائمة لقطةٌ والدلو حالة.
  # ⛔ **وإعادةُ المحاذاة فعلٌ مقصودٌ لا تكرارٌ عابر** (‏D-178): حين يتغيّر
  #    **النموذج** أو الوصفة، الفهرسُ القائم **ليس منجَزاً بل منجَزٌ بعدّةٍ
  #    أخرى**. والحارسُ لا يفرّق بينهما، فيمنع الإصلاحَ كما يمنع التكرار
  #    — **حارسٌ يمنع الصواب**. ⇒ مفتاحٌ صريحٌ يُعلن القصد ولا يُفتح ثغرة:
  #    `FORCE_REALIGN=1` **يُطلبه المشغّلُ عمداً** ولا يقع سهواً.
  if [ "${FORCE_REALIGN:-0}" = "1" ]; then
    echo "🔁 $rid: إعادةُ محاذاةٍ مقصودة (FORCE_REALIGN=1) — حارسُ «منجَزٌ سلفاً» لا يسري"
  elif [ "$surahs" = "1-114" ]      && "$PY" "$ROOT/tools/ci_fleet/already_done.py" "$riwaya" "$rid"; then
    skip_count=$((skip_count + 1)); SKIPPED+=("$rid:منجَزٌ سلفاً"); return 0
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
  # ⛔ العزل الفوري كان يُضيّع عملاً تامّاً تقريباً: ستة قرّاء عندهم 642 سورة
  #    منجَزة لم تُرفع، وفيهم `trabulsi` بـ114/114 كاملة رُفض رفعُه لأن الفهرس
  #    بُني قبل أن تكتمل سورتان ولم يُعِد أحدٌ البناء. فتمريرةٌ ثانية أولاً —
  #    وهي رخيصة: `batch_run` لا يعيد سورةً لها json، فلا يُحسب إلا الفاشل.
  if [ "$rc" -ne 0 ]; then
    echo "🔁 $rid: rc=$rc ⇒ تمريرة ثانية على الفاشل وحده"
    rc=0
    "$PY" "$ROOT/tools/alignment/batch_run.py"           --reciter "$rid" --riwaya "$riwaya" --base "$base" --surahs "$surahs"           >> "$ROOT/logs-copy/$rid.log" 2>&1 || rc=$?
  fi
  # ⛔ وإن بقي الفشل فالعمل لا يُرمى: يُرفع جزئياً موسوماً بنقصه. و«جزئيٌّ
  #    مُعلَن» يصل المدقّق بحكمٍ عليه، أما المعزول فلا يصل أصلاً.
  if [ "$rc" -ne 0 ]; then
    _have=$(ls "$ROOT/tools/alignment/work/batch_$rid"/s*.json 2>/dev/null | wc -l)
    _have=$((_have + 0))
    if [ "$_have" -ge 100 ] && [ "$_have" -lt 114 ]; then
      echo "⚠️ $rid: rc=$rc بعد تمريرتين · $_have/114 ⇒ رفعٌ جزئي موسوم"
      "$PY" "$ROOT/tools/ci_fleet/stage_upload.py" --reciter "$rid"             --riwaya "$riwaya" --expect-surahs "1-$_have"             --log "$ROOT/logs-copy/$rid.log"         && { fail_count=$((fail_count + 1)); FAILED+=("$rid:partial=$_have"); return 0; }
    fi
    echo "❌ $rid: batch_run rc=$rc بعد تمريرتين ($_have/114) — يُعزل ويُواصَل"
    fail_count=$((fail_count + 1)); FAILED+=("$rid:batch_run=$rc"); return 0
  fi
  # عدّ الملفات بعد التوازي — الحارس اللاحق يفحصها، وهذا سطرٌ للسجل لا حكم.
  _have=$(ls "$ROOT/tools/alignment/work/batch_$rid"/s*.json 2>/dev/null | wc -l)
  _have=$((_have + 0))
  echo "  📄 ملفات السور: $_have/114"
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
  # ⛔ الرفض الصامت عند 111–113/114 (مقيس على 17 قارئاً): حين يعود `batch_run`
  #    بـ**صفر** والسور ناقصةٌ سورةً أو اثنتين، كان الرفع بـ`--expect-surahs 1-114`
  #    فيرفضه `stage_upload` («سور 113/114») ولا يسلك مسار الرفع الجزئي لأنّه كان
  #    مشروطاً بـrc≠ 0. والصواب أن **عدد السور الموجود فعلاً** هو ما يحدّد المسار:
  #    ≥ PARTIAL_MIN (110) ⇒ رفعٌ جزئي **موسوم** بـ`.partialN`، وما دونه رفضٌ مُعلن.
  _expect="$surahs"
  if [ "$surahs" = "1-114" ] && [ "$_have" -lt 114 ]; then
    if [ "$_have" -ge "${PARTIAL_MIN:-110}" ]; then
      echo "⚠️ $rid: rc=0 و$_have/114 ⇒ رفعٌ جزئي موسوم (لا رفض صامت)"
      _expect="1-$_have"
    else
      echo "🛑 $rid: نقصٌ كبير $_have/114 (< ${PARTIAL_MIN:-110}) — لا رفع، يُعزل ويُواصَل"
      fail_count=$((fail_count + 1)); FAILED+=("$rid:missing=$_have"); return 0
    fi
  fi
  "$PY" "$ROOT/tools/ci_fleet/stage_upload.py" --reciter "$rid" --riwaya "$riwaya"         --expect-surahs "$_expect" --log "$ROOT/logs-copy/$rid.log" || rc=$?
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

# ── التوزيع بالوزن لا بالقسمة الدورية ────────────────────────────────────
# ⛔ إذن github-f4 لجبهة CI وحدها؛ وقاعدة b9 («الترتيب هو القسمة، لا يُعاد
#    ترتيبه») تبقى نافذةً على شرائح الأسطول. وسببه قياس: حجم البقرة يتراوح
#    28م.ب–373م.ب بين القرّاء (‏13×)، و`i % SHARDS` توزيعٌ أعمى قد يجمع الثقال
#    في شريحةٍ واحدة — **وأبطأ شريحةٍ هي زمن الموجة كله**.
#    والحتمية محفوظة: كل شريحة تحسب التوزيع نفسه من الملف نفسه بلا تنسيق.
#    وعند غياب عمود الوزن يسقط `assign_shard.py` إلى `i % SHARDS` كما كان.
ASSIGN="$ROOT/tools/ci_fleet/assign_shard.py"
if [ -f "$ASSIGN" ]; then
  MINE="$("$PY" "$ASSIGN" "$LIST" "$SHARD" "$SHARDS")"
else
  MINE="$(awk -F'\t' -v s="$SHARD" -v n="$SHARDS" \
          '!/^#/ && NF>=4 { if (i % n == s) print $1"\t"$2"\t"$3"\t"$4; i++ }' "$LIST")"
fi
echo "قرّاء هذه الشريحة: $(printf '%s\n' "$MINE" | grep -c .)"
# ⛔ **بلا أنبوب**: `printf | while` يجعل الحلقة **صدفةً فرعية**، فتضيع
#    العدّادات ويصير `exit` خروجاً من الفرعية وحدها ⇒ الجرد يطبع أصفاراً
#    **والوظيفة تخضرّ على فشلٍ تامّ**. وقع فعلاً في `shard-5`: سقط بناء الفهرس
#    بـ`ModuleNotFoundError` وخرجت الشريحة **خضراء** بعد 89 دقيقة.
#    والعلاج إعادة توجيهٍ من ملف لا أنبوب.
printf '%s\n' "$MINE" > "$ROOT/logs-copy/.mine.tsv"
# ⛔ القائمة تُقرأ على **الواصف 3** لا على ستدين: الحلقة تشغّل `run_one`
#    وأبناءه (batch_run/whisper/ffmpeg) وهم يرثون ستدين، فيبتلع ابنٌ بايتاتٍ من
#    الصفّ التالي ⇒ قارئٌ يضيع أو يُقتطع اسمه (`asm` من `qasm`، `ifai` من `mrifai`).
#    واخترتُ الواصف 3 على `run_one < /dev/null` لأنّه يحمي القائمة **بنيوياً**
#    مهما تفرّع الشجر: `/dev/null` يعالج الاستدعاء الظاهر وحده، وأي أمرٍ يُضاف
#    لاحقاً داخل الحلقة يعود إلى العطب نفسه. ومع ذلك نجمع الاثنين (حزامٌ وحمّالة).
while IFS=$'	' read -r rid riwaya base prio <&3; do
  [ -n "${rid:-}" ] || continue
  _guard_id "$rid" || { echo "⛔ يُتخطّى صفٌّ معرّفه مريب"; continue; }
  _guard_in_list "$rid" || {
    echo "⛔ المعرّف [$rid] لا يطابق أي صفٍّ في $LIST — بصمةُ تلفٍ في القراءة؛ تُوقف الشريحة."
    summary; exit 1
  }
  run_one "$rid" "$riwaya" "$base" "1-114" < /dev/null || { echo "⛔ توقّف مبكر"; summary; exit 1; }
done 3< "$ROOT/logs-copy/.mine.tsv"
echo "SHARD_DONE $SHARD/$SHARDS"
summary
