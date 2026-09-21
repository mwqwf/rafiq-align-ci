#!/usr/bin/env bash
# 🎓🔬 **مسبارُ طالبِ M3 على عدّاءٍ مجّانيّ — تفتيشٌ قبل تدريب** (‏2026-09-21 · D-736).
#
# ⛔ **العطبُ الذي وُجد له:** دفترُ Kaggle استنسخ مستودعاً **خاصّاً** فوقف على سؤال اعتمادٍ
# أبداً (‏سجلٌّ ساكتٌ · مخرَجٌ صفر · 100 دقيقةِ GPU في الفراغ). وهنا **لا استنساخَ بكلمة سرّ**:
# `agent-job` يستنسخ `QuranRafiq` بمفتاح قراءةٍ مقيّدٍ يملكه المالك سلفاً في هذا المستودع.
#
# ⛔ **وهذا الشوطُ لا يدّعي تدريباً**: يقيس **ثانيةً لكلّ خطوة** على هذا العدّاء كي تُحسب
# سلسلةُ الأشواط **بقياسٍ لا بتقدير** (سقفُ الشوط 120 دقيقة)، ويثبت أنّ كلّ حلقةٍ تعمل:
# الوسمُ · أوزانُ المعلّم · البيانات · خطوةُ تدريبٍ حقيقيّة. وكلُّ حلقةٍ تسقط **معلِنةً**.
set -uo pipefail
say() { echo "▸ $*"; }
die() { echo "⛔ إخفاقٌ مُعلَن: $*"; exit 1; }

[ -n "${QR_DIR:-}" ] || die "لا مستودعَ خاصّ (لا مفتاح قراءة) ⇒ لا شيءَ يُقاس — ولا يُدّعى نجاح"
cd "$QR_DIR" || die "تعذّر الدخول إلى $QR_DIR"
say "المستودعُ الخاصّ: $(git log --oneline -1)"
PUB="https://pub-2c2e1dcd92e84a2898820dd38d3e09e6.r2.dev"

say "① العُدّة"
pip install -q "torch>=2.2" --index-url https://download.pytorch.org/whl/cpu || die "torch"
pip install -q "transformers>=4.44,<5" soundfile || die "transformers"
python3 -c "import torch,transformers;print('torch',torch.__version__,'tf',transformers.__version__)" || die "استيراد"

say "② الوسمُ الفونيميّ (‏D-717)"
mkdir -p tools/tasmi_bench/work
curl -sSL -A "$UA" "$PUB/tasmi/g2p_labels_2026-09-20.jsonl.gz" | gunzip > tools/tasmi_bench/work/g2p_labels.jsonl || die "وسم"
N=$(wc -l < tools/tasmi_bench/work/g2p_labels.jsonl)
[ "$N" = "37416" ] || die "الوسمُ $N صفّاً لا 37416 ⇒ ليس ما قِيس عليه"
say "الوسم: $N صفّاً ✅"

say "③ أوزانُ المعلّم (‏Range لا أرشيفاً كاملاً)"
TAR="$PUB/finetune/ctc_r3/best.tar"
python3 tools/tasmi_phoneme/range_get.py --url "$TAR" --out /tmp/best.tar --end 755435007 --chunk 8388608 >/dev/null || die "range_get"
python3 tools/tasmi_phoneme/tar_pick.py --from-file /tmp/best.tar --url "$TAR" --verify 8 \
  --dest tools/tasmi_phoneme/work/out_ctc --want model.safetensors vocab.json >/dev/null || die "tar_pick"
rm -f /tmp/best.tar /tmp/best.tar.parts.json
[ -s tools/tasmi_phoneme/work/out_ctc/model.safetensors ] || die "أوزانُ المعلّم لم تصل"
say "المعلّم: $(du -h tools/tasmi_phoneme/work/out_ctc/model.safetensors | cut -f1) ✅"

# ⚠️ الأرشيفُ بلا `config.json` وأداةُ الانتقاء **لا تشتكي** (‏عطبُ عُدّةٍ سادس · D-738)
python3 tools/tasmi_phoneme/teacher_config_fix.py || die "تهيئةُ المعلّم لا تطابق أوزانَه"

say "④ بياناتٌ صغيرةٌ للمسبار (‏5 لكلّ قارئ — لا مجموعةُ D-714 الكاملة)"
python3 tools/finetune/prep.py --out /tmp/data --workers 8 --max-per-reciter 5 --per-surah-cap 2 \
  --reciters hafs:a_abdl,a_albadr warsh:basit_warsh qalun:akri_qalun >/dev/null 2>&1 || die "prep"
ROWS=$(wc -l < /tmp/data/manifest.jsonl 2>/dev/null || echo 0)
[ "$ROWS" -ge 8 ] || die "البياناتُ $ROWS صفّاً — أقلُّ من أن يُقاس بها"
say "البيانات: $ROWS صفّاً ✅"

say "⑤ عشرون خطوةً حقيقيّةً — ويُقاس الزمن"
T0=$(date +%s)
python3 tools/tasmi_phoneme/ctc_train.py \
  --labels tools/tasmi_bench/work/g2p_labels.jsonl --items /tmp/data/manifest.jsonl \
  --wav-dir / --index core/quran/src/main/assets/quran/index.jz \
  --student-from tools/tasmi_phoneme/work/out_ctc \
  --student-hidden 384 --student-layers 8 --student-heads 8 \
  --steps 20 --bs 4 --lr 1e-4 --max-seconds 12 --eval-every 20 --log-every 5 \
  --out /tmp/out_student 2>&1 | tail -20
RC=${PIPESTATUS[0]}
T1=$(date +%s)
[ "$RC" -eq 0 ] || die "التدريبُ خرج بـ$RC"
SEC=$((T1 - T0))
say "⑥ الحصيلة"
python3 - "$SEC" <<'PY'
import sys
sec = int(sys.argv[1])
per_step = sec / 20.0
# الهدفُ 3200 خطوةً بدفعة 16 ⇒ الخطوةُ أربعةُ أضعافِ خطوةِ المسبار (بدفعة 4) تقريباً
full = per_step * 4 * 3200 / 60.0
print(f"⏱️ عشرون خطوةً (بدفعة 4) + تحميلٌ: {sec}ث ⇒ ≈{per_step:.1f}ث/خطوة **بما فيها الإقلاع**")
print(f"📐 تقديرٌ أوّليٌّ للهدف (3200 خطوةً بدفعة 16): ≈{full:.0f} دقيقة ⇒ "
      f"≈{full/100:.1f} شوطاً من مئة دقيقة")
print("⛔ وهذا تقديرُ سَعةٍ لا زمنُ تدريبٍ مقيس: زمنُ الإقلاع داخلٌ فيه، والخطوةُ بدفعة 16 "
      "ليست أربعةَ أضعافِ خطوةِ دفعةِ 4 بالضبط ⇒ يُعاد حسابُه من أوّل شوطٍ حقيقيّ.")
PY
say "✅ السلسلةُ كلُّها تعمل على هذا العدّاء — والتدريبُ الكاملُ يُبنى على هذا القياس"
