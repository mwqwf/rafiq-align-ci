#!/usr/bin/env bash
# 📡 منارة تقدّم الشريحة — «ما لا يُرى لا يُدار» (أمر github-f4، 2026-09-02).
#
# ⛔ سبب وجودها مقيس: وقفنا ساعتين أمام 20/20 «قيد التنفيذ» بلا أي شاهدٍ على
#    ما يجري داخل العدّاء، لأن `gh` لا ينزّل سجلّ مهمةٍ قبل انتهائها — فلم
#    نعرف أنّ الموجة الأولى عقيمة إلا بعد ساعةٍ وربع من الحوسبة الضائعة.
#
# تُشغَّل في الخلفية من `run_shard.sh`، وتدفع ملفاً صغيراً إلى فرع
# `progress/<shard>` كلما تقدّم العدد **عشر سور**.
#
# ⛔ ثلاثة قيود في تصميمها، وكلها مقصودة:
#  1. **لا تُفشل الشريحة بحال.** كل فشلٍ فيها يُبتلع: منارةٌ تُسقط عملاً حقيقياً
#     أسوأ من عمًى. ولذلك `|| true` على كل نداء شبكة، وخروجها صامت.
#  2. **فرعٌ لكل شريحة** لا فرعٌ مشترك: عشرون كاتباً على مرجعٍ واحد يتزاحمون
#     على `sha` فتفشل أكثر الدفعات بلا فائدة.
#  3. **عتبةُ عشر سور لا مؤقّتٌ ثابت:** تُقاس بالعمل المنجَز لا بمرور الوقت،
#     فلا تُغرق المستودع بدفعاتٍ لا جديد فيها حين تبطؤ الشريحة.
#
# ⛔⛔ وثلاثةُ أعطابٍ قِيست فيها 2026-09-12 وأُصلحت هنا — **منارةٌ تكذب أسوأ من
#     عمًى**، لأنّ العمى يُسأل عنه والكذبَ يُبنى عليه قرار:
#  أ. **الاسمُ كان `ls -d batch_* | head -1`** ⇒ أوّلُ مجلّدٍ **أبجديّاً** لا
#     القارئُ المكلَّف. ومع استعادةِ كاشٍ لشريحةٍ أخرى (وهو الأصلُ بعد إصلاح
#     `ckey`) تظهر مجلّداتُ غيرِه ⇒ منارةُ الخانة 0 قالت `h_saleh` وهي
#     `noah_warsh`. **والعلاج: أحدثُ مجلّدٍ زمناً من قرّاء الشريحة وحدَهم.**
#  ب. **العدُّ كان يجمع `batch_*/s*.json` كلَّها** ⇒ مخلَّفاتُ الكاش المستعاد
#     تُضخّم الرقم (‏قيل 228 سورةً والحقيقةُ أقلُّ بكثير)، **وتُسمِّم العتبةَ
#     نفسَها**: `last` يقفز فلا تنبض المنارةُ ثانيةً. **والعلاج: لا يُعَدُّ إلا
#     ما أنتجه قرّاءُ هذه الشريحة.**
#  ج. **موجتان فيهما شاردةُ 0 تكتبان على `shard-0.json` نفسِه** فيغلب آخرُ
#     كاتب. **والعلاج: رقمُ التشغيل في اسم الملفّ لا في فرعٍ جديد** — فالقيد 2
#     يبقى كما هو، وتبقى المنارتان مرئيّتين معاً.
set -u

SHARD="${SHARD:-0}"
REPO="${GITHUB_REPOSITORY:-mwqwf/rafiq-align-ci}"
WORK="${1:-/root/QuranRafiq/tools/alignment/work}"
STEP="${PROGRESS_STEP:-10}"
RUN="${GITHUB_RUN_ID:-0}"
BRANCH="progress/${SHARD}"
FILE="shard-${SHARD}-${RUN}.json"

command -v gh >/dev/null 2>&1 || exit 0
[ -n "${GH_TOKEN:-${GITHUB_TOKEN:-}}" ] || exit 0

# الفرع يُنشأ مرةً من رأس الفرع الافتراضي؛ ووجودُه سلفاً ليس خطأً.
base="$(gh api "repos/$REPO/git/ref/heads/main" --jq .object.sha 2>/dev/null || true)"
[ -n "$base" ] && gh api "repos/$REPO/git/refs" -f ref="refs/heads/$BRANCH" \
  -f sha="$base" >/dev/null 2>&1 || true

# 🎯 قرّاءُ هذه الشريحة وحدَهم — يُحسبون مرّةً بـ`assign_shard.py` نفسِه الذي
#    يقسم العمل (‏لا بتخمينٍ من المجلّدات)، فيصير العدُّ والاسمُ صادقَين ولو
#    استُعيد كاشُ غيرِها. ⛔ وكلُّ تعثّرٍ هنا يسقط إلى السلوك القديم صامتاً:
#    منارةٌ ناقصةُ الدقّة خيرٌ من شريحةٍ ساقطة (‏القيد 1).
ROOT="${WORK%/tools/alignment/work}"
MINE=""
if [ -n "${LIST:-}" ] && [ -f "${LIST:-}" ] && [ -f "$ROOT/tools/ci_fleet/assign_shard.py" ]; then
  MINE="$(python3 "$ROOT/tools/ci_fleet/assign_shard.py" \
          "$LIST" "$SHARD" "${SHARDS:-1}" 2>/dev/null | cut -f1 || true)"
fi
# ⛔ `if` لا `[ … ] && …` — الثانيةُ تُرجع 1 عند فشل الشرط (‏درسُ خطوة `ckey`).
if [ -n "$MINE" ]; then
  printf '📡 منارة: قرّاءُ الشريحة %s ⇐ %s\n' "$SHARD" "$(printf '%s' "$MINE" | tr '\n' ' ')"
fi

last=-1
while :; do
  if [ -n "$MINE" ]; then
    # العدُّ: مجموعُ ما أنتجه قرّاءُ هذه الشريحة — يبقى تصاعديّاً عبرهم
    # جميعاً فلا تنكسر عتبةُ العشر حين ينتقل السائقُ من قارئٍ إلى تاليه.
    n=0
    for r in $MINE; do
      c=$(ls "$WORK/batch_$r"/s*.json 2>/dev/null | wc -l | tr -d ' ')
      n=$(( n + ${c:-0} ))
    done
    # الاسمُ: صاحبُ أحدثِ مجلّدٍ زمناً — ومجلّدُ القارئ يُلمَس كلّما كُتبت فيه
    # سورة، فأحدثُها زمناً هو الذي يعمل الآن.
    rid=$(for r in $MINE; do
            d="$WORK/batch_$r"
            [ -d "$d" ] && printf '%s\t%s\n' "$(stat -c %Y "$d" 2>/dev/null || echo 0)" "$r"
          done | sort -rn | head -1 | cut -f2)
  else
    n=$(ls "$WORK"/batch_*/s*.json 2>/dev/null | wc -l | tr -d ' ')
    rid=$(ls -d "$WORK"/batch_* 2>/dev/null | head -1 | sed 's#.*/batch_##')
  fi
  n=${n:-0}
  if [ "$n" -ge $(( last + STEP )) ]; then
    last="$n"
    body=$(printf '{"shard":%s,"surahs":%s,"reciter":"%s","at":"%s","run":"%s"}' \
           "$SHARD" "$n" "${rid:-?}" "$(date -u +%FT%TZ)" "$RUN")
    sha=$(gh api "repos/$REPO/contents/$FILE?ref=$BRANCH" --jq .sha 2>/dev/null || true)
    if [ -n "$sha" ]; then
      gh api -X PUT "repos/$REPO/contents/$FILE" -f message="progress shard $SHARD: $n سورة" \
        -f content="$(printf '%s' "$body" | base64 -w0)" -f branch="$BRANCH" -f sha="$sha" \
        >/dev/null 2>&1 || true
    else
      gh api -X PUT "repos/$REPO/contents/$FILE" -f message="progress shard $SHARD: $n سورة" \
        -f content="$(printf '%s' "$body" | base64 -w0)" -f branch="$BRANCH" \
        >/dev/null 2>&1 || true
    fi
    echo "📡 منارة: $n سورة (شريحة $SHARD)"
  fi
  sleep 60
done
