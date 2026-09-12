#!/usr/bin/env bash
# 📱 جسمُ شوطِ محاكي العدّاء — **ملفٌّ واحدٌ عمداً**.
# ⛔ درسٌ مدفوع (‏2026-09-12): `reactivecircus/android-emulator-runner` ينفّذ **كلَّ سطرٍ في `script:` بصدفةٍ
# منفصلة** (`sh -c` لكلِّ سطر) ⇒ `export` و`cd` لا يعبران السطر، و`"$VAR"` الفارغُ يعطي
# `sh: 1: : Permission denied` وخروجاً 127 **بعد إقلاع المحاكي** فيبدو كأنّ المحاكي هو العطب.
# فالسطرُ في المسار صار واحداً: `bash tools/tasmi_bench/ci_emu_run.sh`، وكلُّ شيءٍ هنا.
#
# البيئة: APK · CAND_TAG (فارغٌ = المشحونُ وحدَه) · SET · LANGS (فارغٌ = افتراضُ التطبيق) · CHUNK
set -euo pipefail
ADB="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-/usr/local/lib/android/sdk}}/platform-tools/adb"
export RAFIQ_ADB="$ADB"
SET="${SET:?يلزم SET}"; CHUNK="${CHUNK:-12}"; CAND_TAG="${CAND_TAG:-}"; LANGS="${LANGS:-}"
# 🎚️ مفاتيحُ المسبار المنطقيّة (‏`decodeGuard` · `criticalPairs`) ولاحقةُ الوسم كي لا تُكتب ذراعٌ فوق أخرى.
EZ="${EZ:-}"; SUF="${TAG_SUFFIX:-}"
EZARGS=""; for f in $EZ; do EZARGS="$EZARGS --ez $f=true"; done
[ -n "$EZ" ] && echo "🎚️ مفاتيح: $EZ · لاحقةُ الوسم: '${SUF}'"

echo "🔌 $("$ADB" devices | tail -n +2 | tr '\n' ' ')"
"$ADB" wait-for-device
"$ADB" install -r -g "${APK:?يلزم APK}" | tail -2
"$ADB" push models/shipped.bin /data/local/tmp/q8_shipped.bin | tail -1
if [ -n "$CAND_TAG" ] && [ -f models/cand.bin ]; then
  "$ADB" push models/cand.bin "/data/local/tmp/q8_$CAND_TAG.bin" | tail -1
fi

cd tools/tasmi_bench
ARMS="shipped"; [ -n "$CAND_TAG" ] && ARMS="$ARMS $CAND_TAG"
for A in $ARMS; do
  if [ -z "$LANGS" ]; then
    # ⛔ **D-308:** ما دُرِّب بـ`<|ar|>` يُقاس بـ`<|ar|>`. خدمةُ مضبوطٍ بـ`en` رفعت اتّهامَه الكاذب **2.22 نقطة**
    # فحُكم على ثلاثة نماذجَ بالرسوب ظلماً. والمشحونُ يبقى على افتراض التطبيق (`en`) لأنّ `ar` تكلّفه 3.1 نقاطٍ من الكشف
    # ⇒ الزوجُ الافتراضيُّ هنا هو **زوجُ الشحن**: المشحونُ كما يُشحن، والمرشَّحُ كما سيُشحن.
    if [ "$A" = "shipped" ]; then
      # ⛔ **صريحاً لا افتراضاً (‏2026-09-12 · صُحِّح في D-313):** كلُّ ذراعٍ هنا تُثبِّت لغتَها بالنيّة، ولا
      # تتّكل على اشتقاقٍ يملكه غيرُنا. والسببُ الحقيقيُّ بعد D-312 **ليس** أنّ `q8_shipped.bin` يُشتقّ له
      # `ar` — بل أنّه **ليس اسمَ نموذجٍ في جدول `WhisperDecode.SERVING`** (الأسماءُ هناك أسماءُ الشحن
      # `whisper-tiny-ar-quran…bin` لا أسماءُ `/data/local/tmp/q8_*.bin`) ⇒ **كلُّ** ذراعٍ بلا نيّةٍ تسقط
      # إلى `DEFAULT=en`، فتتطابق ذراعا `en`/`ar` في حلقة `LANGS` ويُحكم كذباً أنّ «اللغةَ لا أثرَ لها».
      # وبالتثبيت الصريح يبقى القياسُ صحيحاً أيضاً **بعد** أن يكسب الجدولُ سطراً جديداً (بوّابةُ v2).
      # 🛡️ ويسندُه حارسُ `emu_sweep.py`: سطرُ `RafiqFrontEnd … lang=` يجب أن يُقرّ بالنيّة وإلا وقف المسح.
      echo "▶ $SET · $A · lang=en (صريحاً — كما يُشحن)"
      python emu_sweep.py --set "$SET" --chain cap --chunk "$CHUNK" --tag "$A$SUF" --model-path "/data/local/tmp/q8_$A.bin" --es "lang=en" $EZARGS | tail -3
    else
      # ⛔ والوسمُ يحمل اللغةَ صراحةً (`v2-ar` لا `v2`): ملفُّ الذراع القديمةِ المخدومةِ بـ`en` يحمل الاسمَ المجرَّد،
      # فلو تساويا لكُتب أحدُهما فوق الآخر و**قورنت ذراعٌ بذراعٍ أخرى بلا أن يظهر في الرقم شيء**.
      echo "▶ $SET · $A · lang=ar (‏D-308: المضبوطُ يُقاس بما دُرِّب عليه)"
      python emu_sweep.py --set "$SET" --chain cap --chunk "$CHUNK" --tag "$A-ar$SUF" --model-path "/data/local/tmp/q8_$A.bin" --es "lang=ar" $EZARGS | tail -3
    fi
  else
    for L in $LANGS; do
      echo "▶ $SET · $A · lang=$L"
      python emu_sweep.py --set "$SET" --chain cap --chunk "$CHUNK" --tag "$A-$L" \
        --model-path "/data/local/tmp/q8_$A.bin" --es "lang=$L" | tail -3
    done
  fi
done
ls -l work/hyps_emu_*.json | tail -6
