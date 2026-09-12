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
    echo "▶ $SET · $A (افتراضُ التطبيق)"
    python emu_sweep.py --set "$SET" --chain cap --chunk "$CHUNK" --tag "$A" --model-path "/data/local/tmp/q8_$A.bin" | tail -3
  else
    for L in $LANGS; do
      echo "▶ $SET · $A · lang=$L"
      python emu_sweep.py --set "$SET" --chain cap --chunk "$CHUNK" --tag "$A-$L" \
        --model-path "/data/local/tmp/q8_$A.bin" --es "lang=$L" | tail -3
    done
  fi
done
ls -l work/hyps_emu_*.json | tail -6
