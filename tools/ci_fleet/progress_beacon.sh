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
set -u

SHARD="${SHARD:-0}"
REPO="${GITHUB_REPOSITORY:-mwqwf/rafiq-align-ci}"
WORK="${1:-/root/QuranRafiq/tools/alignment/work}"
STEP="${PROGRESS_STEP:-10}"
BRANCH="progress/${SHARD}"
FILE="shard-${SHARD}.json"

command -v gh >/dev/null 2>&1 || exit 0
[ -n "${GH_TOKEN:-${GITHUB_TOKEN:-}}" ] || exit 0

# الفرع يُنشأ مرةً من رأس الفرع الافتراضي؛ ووجودُه سلفاً ليس خطأً.
base="$(gh api "repos/$REPO/git/ref/heads/main" --jq .object.sha 2>/dev/null || true)"
[ -n "$base" ] && gh api "repos/$REPO/git/refs" -f ref="refs/heads/$BRANCH" \
  -f sha="$base" >/dev/null 2>&1 || true

last=-1
while :; do
  n=$(ls "$WORK"/batch_*/s*.json 2>/dev/null | wc -l | tr -d ' ')
  n=${n:-0}
  if [ "$n" -ge $(( last + STEP )) ]; then
    last="$n"
    rid=$(ls -d "$WORK"/batch_* 2>/dev/null | head -1 | sed 's#.*/batch_##')
    body=$(printf '{"shard":%s,"surahs":%s,"reciter":"%s","at":"%s","run":"%s"}' \
           "$SHARD" "$n" "${rid:-?}" "$(date -u +%FT%TZ)" "${GITHUB_RUN_ID:-?}")
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
