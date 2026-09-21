#!/usr/bin/env bash
# 🎓📏 **طالبُ M3 يُدرَّب ويُقاس في الشوط نفسِه — ولا يخرج منه وزنٌ، بل رقمٌ.**
#
# ⛔ **العطبُ الذي وُجد له:** سلسلةُ التدريب تحتاج **حفظَ نقطةٍ بين الحلقات**، وهو محجوبٌ في
# جلسة الوكيل. ⇒ والمخرجُ ليس حفظاً بل **إلغاءَ الحاجة إليه**: ما نريده من الأوزان أرقامُها
# (‏PER · الحجمُ المكمَّم · تشتّتُ الطوابع)، وكلُّها تُقاس هنا، وتعود في `results/job_*.md`.
#
# ⛔ **وما لا يُدّعى:** ميزانيّةُ الشوط 120 دقيقة ⇒ الخطواتُ أقلُّ من 3200 المخطَّطة بكثير،
# **فالرقمُ يُنشر بعددِ خطواته لا بأنّه «الطالبُ النهائيّ»**. ⭐ **والحجمُ المكمَّم وحدَه
# لا يتعلّق بالتدريب** ⇒ **بوّابةُ حجم M3 (‏20–40 م.ب) تُجاب من هذا الشوط إجابةً نهائيّة**.
# ⛔ ولا تُدّعى بوّابةُ M3 الزمنيّةُ/البشريّة بحال: مساطرُنا قطعُ ناشرٍ لا وسمُ إنسانَين.
#
# البيئة: BUDGET_MIN (دقائقُ التدريب · افتراضاً 62) · MAXPER (آياتٌ لكلّ قارئ · افتراضاً 150)
set -uo pipefail
say() { echo "▸ $*"; }
die() { echo "⛔ إخفاقٌ مُعلَن: $*"; exit 1; }
T_START=$(date +%s)

[ -n "${QR_DIR:-}" ] || die "لا مستودعَ خاصّ"
cd "$QR_DIR" || die "cd"
PUB="https://pub-2c2e1dcd92e84a2898820dd38d3e09e6.r2.dev"
BUDGET_MIN=${BUDGET_MIN:-62}
MAXPER=${MAXPER:-150}
OUT=/tmp/out_student
say "المستودعُ الخاصّ: $(git log --oneline -1)"

say "① العُدّة"
pip install -q "torch>=2.2" --index-url https://download.pytorch.org/whl/cpu || die "torch"
pip install -q "transformers>=4.44,<5" soundfile || die "pip"

say "② الوسمُ (‏D-717)"
mkdir -p tools/tasmi_bench/work work/tasmi/lab
curl -sSL -A "$UA" "$PUB/tasmi/g2p_labels_2026-09-20.jsonl.gz" | gunzip > tools/tasmi_bench/work/g2p_labels.jsonl || die "وسم"
[ "$(wc -l < tools/tasmi_bench/work/g2p_labels.jsonl)" = "37416" ] || die "الوسمُ ليس ما قِيس عليه"
cp tools/tasmi_bench/work/g2p_labels.jsonl work/tasmi/lab/g2p_labels.jsonl

say "③ المعلّمُ وتهيئتُه (‏D-738)"
TAR="$PUB/finetune/ctc_r3/best.tar"
python3 tools/tasmi_phoneme/range_get.py --url "$TAR" --out /tmp/best.tar --end 755435007 --chunk 8388608 >/dev/null || die "range_get"
python3 tools/tasmi_phoneme/tar_pick.py --from-file /tmp/best.tar --url "$TAR" --verify 8 \
  --dest tools/tasmi_phoneme/work/out_ctc --want model.safetensors vocab.json >/dev/null || die "tar_pick"
rm -f /tmp/best.tar /tmp/best.tar.parts.json
python3 tools/tasmi_phoneme/teacher_config_fix.py >/dev/null || die "تهيئةُ المعلّم لا تطابق أوزانَه"

say "④ البيانات (‏قرّاءُ D-714 أنفسُهم · $MAXPER لكلّ قارئ بدل 400 — والفرقُ يُنشر)"
mkdir -p /tmp/data
python3 tools/finetune/prep.py --out /tmp/data --workers 8 --max-per-reciter "$MAXPER" --per-surah-cap 20 \
  --reciters warsh:basit_warsh,benkirane_warsh,deban_warsh,koshi_warsh,m_sayed_warsh \
             qalun:akri_qalun,dokali,huthaify_qalun,qeniwa_qalun,tareq_qalun \
             hafs:a_abdl,a_albadr,a_alqrafi,a_alshahhat,a_alhazmi 2>&1 | tail -3
ROWS=$(wc -l < /tmp/data/manifest.jsonl 2>/dev/null || echo 0)
[ "$ROWS" -ge 800 ] || die "المجموعةُ $ROWS صفّاً — ناقصةٌ فلا يُدرَّب عليها بلا إعلان"
say "المجموعة: $ROWS صفّاً"

say "⑤ معايرةُ السرعة — أربعون خطوةً تُقاس ثمّ تُحسب ميزانيّةُ الخطوات"
T0=$(date +%s)
python3 tools/tasmi_phoneme/ctc_train.py \
  --labels tools/tasmi_bench/work/g2p_labels.jsonl --items /tmp/data/manifest.jsonl \
  --wav-dir / --index core/quran/src/main/assets/quran/index.jz \
  --student-from tools/tasmi_phoneme/work/out_ctc \
  --student-hidden 384 --student-layers 8 --student-heads 8 \
  --steps 40 --bs 16 --lr 1e-4 --max-seconds 12 --eval-every 40 --log-every 20 \
  --holdout-reciters m_sayed_warsh,tareq_qalun,a_alhazmi --out "$OUT" 2>&1 | tail -8
[ "${PIPESTATUS[0]}" -eq 0 ] || die "المعايرةُ أخفقت"
T1=$(date +%s)
USED=$(( (T1 - T_START) / 60 ))
SPS=$(python3 -c "print(max(0.5,($T1-$T0)/40))")
STEPS=$(python3 -c "
import sys
sps=float('$SPS'); left=max(0,$BUDGET_MIN-$USED)*60
print(int(40 + max(0, left/sps)))")
say "⏱️ $SPS ث/خطوة بدفعة 16 · استُهلك $USED دقيقة ⇒ سقفُ هذا الشوط $STEPS خطوة"

say "⑥ التدريبُ إلى $STEPS ثمّ التكميم"
python3 tools/tasmi_phoneme/ctc_train.py \
  --labels tools/tasmi_bench/work/g2p_labels.jsonl --items /tmp/data/manifest.jsonl \
  --wav-dir / --index core/quran/src/main/assets/quran/index.jz \
  --student-from tools/tasmi_phoneme/work/out_ctc \
  --student-hidden 384 --student-layers 8 --student-heads 8 \
  --steps "$STEPS" --bs 16 --lr 1e-4 --max-seconds 12 --eval-every 200 --log-every 100 \
  --holdout-reciters m_sayed_warsh,tareq_qalun,a_alhazmi --resume --quantize \
  --out "$OUT" 2>&1 | tail -15
[ "${PIPESTATUS[0]}" -eq 0 ] || die "التدريبُ أخفق"
say "📄 الخلاصة:"; cat "$OUT/summary.json"; echo

say "⑦ مجموعةُ حدود الكلمة (‏العشرون سورةُ عينُها) ثمّ قياسُ الطوابع"
sudo apt-get install -y -qq ffmpeg >/dev/null 2>&1 || true
python3 tools/tasmi_phoneme/word_gold.py --pub qurancdn --out work/tasmi/gwF --workers 8 \
  --surahs 78,93,94,97,99,100,101,102,103,104,105,106,107,108,109,110,111,112,113,114 2>&1 | tail -2
python3 tools/tasmi_phoneme/measure_word_timing.py --gold work/tasmi/gwF/qurancdn \
  --model "$OUT" --labels work/tasmi/lab/g2p_labels.jsonl --boundary midpoint \
  --out /tmp/student_word_timing.json 2>&1 | tail -6
[ "${PIPESTATUS[0]}" -eq 0 ] || die "قياسُ الطوابع أخفق"

say "⑧ ⛔ والمقارنةُ على تقاطع الآيات وحدَه (‏D-741) — لا على مادّتَين"
python3 tools/tasmi_phoneme/timing_intersect.py \
  --a docs/qa/tasmi_2026-09-20/teacher_word_timing_D733.json \
  --b /tmp/student_word_timing.json --label-a "معلّم-D733" --label-b "طالب-$STEPS-خطوة" 2>&1 | tail -8

say "✅ تمّ — والرقمُ يُنشر بعددِ خطواته ($STEPS من 3200 المخطَّطة) ولا يُسمّى «الطالبَ النهائيّ»"
