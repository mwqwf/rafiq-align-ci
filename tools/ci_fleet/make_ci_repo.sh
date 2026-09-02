#!/usr/bin/env bash
# يبني شجرة المستودع العام المؤقت `rafiq-align-ci` في مجلد خارج المشروع.
# ⛔ لا يُنشئ مستودعاً ولا يدفع ولا يلمس الشبكة — بناء ملفات فقط.
# الاستعمال: bash tools/ci_fleet/make_ci_repo.sh [مسار_الخرج_الفارغ]
#
# ⛔ ملاحظة تنفيذ: هذا السكربت يكتب في مجلد خارجي جديد ويرفض العمل على مجلد
#    موجود — عمداً. لا حذف جارف فيه ولا اقتراب من `secure/` أو مواد التوقيع.
set -euo pipefail
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="${1:-$SRC/../rafiq-align-ci}"

if [ -e "$OUT" ]; then
  echo "⛔ $OUT موجود. اختر مساراً جديداً — لا يحذف هذا السكربت شيئاً."
  exit 1
fi
mkdir -p "$OUT"

copy() { mkdir -p "$OUT/$(dirname "$1")"; cp -r "$SRC/$1" "$OUT/$1"; }

copy tools/alignment
copy tools/alignment_v2
copy tools/cloud/run_fleet.py
# ⛔ قائمة التجميد (D-058): `stage_upload.py` يقرؤها ليرفض المجمَّد ولو في staging.
copy tools/index_qa/frozen.txt
copy tools/ci_fleet
copy core/quran/src/main/assets/quran
mkdir -p "$OUT/.github/workflows"
cp "$SRC/tools/ci_fleet/workflows/align.yml" "$OUT/.github/workflows/align.yml"

# ── تنظيف نسخةٍ جديدة: مخلفات عملٍ جزئي وكاش بايثون فقط ──────────────────
for d in tools/alignment/work tools/alignment_v2/work tools/alignment_v2/out tools/ci_fleet/workflows; do
  [ -d "$OUT/$d" ] && rm -rf "${OUT:?}/$d"
done
find "$OUT" -name "__pycache__" -type d -prune -exec rm -rf {} +
find "$OUT" -name "*.pyc" -delete

cat > "$OUT/.gitignore" <<'G'
secure/
assets-archive/
tools/alignment/work/
tools/alignment_v2/work/
tools/alignment_v2/out/
__pycache__/
*.pyc
*.wav
*.mp3
G

cat > "$OUT/README.md" <<'R'
# rafiq-align-ci — مستودع حوسبة مؤقت

عدّة فهرسة محاذاة التلاوات، منسوخة من `QuranRafiq` لتشغيلها على عدّائي GitHub.

⛔ **مستودع حوسبة لا مستودع منتج.** لا يحوي أسراراً ولا صوتاً ولا مفاتيح، ولا
يُبنى منه شيء يُشحن. يُحذف بانتهاء الدفعة.

التشغيل: تبويب Actions ← `rafiq-align` ← Run workflow. **ابدأ بـ smoke = true.**

النصوص والأصول تحت رخصها الموثقة في `QuranRafiq/docs/DATA_LICENSE_REGISTRY.md`.
R

# ── حارس الخروج: لا يخرج سرٌّ ولا صوتٌ مع النسخة ─────────────────────────
# يبحث عن **قيمةٍ مُسنَدة** لا عن ذكر الاسم: `"secretAccessKey": "..."` — فذكرُ
# المفتاح في شفرةٍ تقرؤه أمرٌ سليم، وإسنادُ قيمةٍ له في ملفٍ عام هو التسرّب.
# ⛔ يستثني نفسه: هذا الملف يحوي نمط البحث حرفياً فيطابق ذاته (وقع فعلاً).
LEAK="$(grep -rlE '"(accessKeyId|secretAccessKey)"[[:space:]]*:[[:space:]]*"[^"]+"|BEGIN [A-Z ]*PRIVATE KEY' "$OUT" --exclude=make_ci_repo.sh || true)"
if [ -n "$LEAK" ]; then
  echo "⛔ توقّف: ما يشبه سرّاً في هذه الملفات — لا تدفع شيئاً:"; echo "$LEAK"; exit 1
fi
BIG="$(find "$OUT" \( -name '*.mp3' -o -name '*.wav' -o -name '*.jks' -o -name '*.keystore' -o -name '*.bin' \) || true)"
if [ -n "$BIG" ]; then
  echo "⛔ توقّف: صوت أو مفاتيح أو نماذج داخل الشجرة:"; echo "$BIG"; exit 1
fi

echo "✅ الشجرة جاهزة في: $OUT"
du -sh "$OUT"
echo "عدد الملفات: $(find "$OUT" -type f | wc -l)"
echo
echo "الخطوة التالية بيد المالك (انظر tools/ci_fleet/README.md §ما يحتاج المالك)."
