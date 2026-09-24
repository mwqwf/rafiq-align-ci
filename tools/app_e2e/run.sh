#!/usr/bin/env bash
# 📱 سائقُ سيناريوهات «سمّع معي» على المحاكي — المخرجُ سطورُ نجاح/إخفاق ومقتطفاتُ `recite` وحدَها.
set -uo pipefail
PKG=com.mushafak.app
OUT=${OUT:-e2e/result.txt}
: > "$OUT"
# 18:22 بالعدّ الكوفيّ (صفريّ): مجموعُ آي السور 1..17 + 21
EXP=$(python3 -c "print(sum([7,286,200,176,120,165,206,75,129,109,123,111,43,52,99,128,111])+21)")
say(){ echo "$*" | tee -a "$OUT"; }
# ⏹️ إيقافٌ مؤكَّد: force-stop ثمّ انتظارُ موت العمليّة (كانت سطورُ pid سيناريو تظهر في التالي)
stop_app(){ adb shell am force-stop $PKG; for _ in $(seq 1 20); do [ -z "$(adb shell pidof $PKG 2>/dev/null | tr -d '\r')" ] && return; sleep 0.5; done; say "WARN: $PKG still alive after force-stop"; }
adb wait-for-device
adb install -r -g app.apk >/dev/null 2>&1 && say "install: OK" || { say "install: FAIL"; exit 0; }
adb shell pm grant $PKG android.permission.RECORD_AUDIO 2>/dev/null || true
adb shell pm grant $PKG android.permission.POST_NOTIFICATIONS 2>/dev/null || true
# تشغيلٌ أوّلٌ يُنشئ الملفّات ويُحمّل المصحف
adb shell am start -n $PKG/com.ali.rafiq.MainActivity >/dev/null; sleep 40
adb shell am force-stop $PKG

scenario(){ # name wav riwaya
  local name=$1 wav=$2 riw=$3
  local dur; dur=$(python3 -c "import wave;w=wave.open('e2e/$wav');print(int(w.getnframes()/w.getframerate())+1)")
  adb push "e2e/$wav" /data/local/tmp/inj.wav >/dev/null
  stop_app
  adb shell run-as $PKG cp /data/local/tmp/inj.wav files/tasmi_inject.wav
  # ✅ الحقنةُ في مكانها بحجمها قبل البدء (‏وإلا سمع التطبيقُ الميكروفونَ الفارغ فهلوس)
  local want got; want=$(stat -c %s "e2e/$wav"); got=$(adb shell run-as $PKG stat -c %s files/tasmi_inject.wav 2>/dev/null | tr -d '\r')
  [ "$want" = "$got" ] || say "WARN: $name inject size want=$want got=${got:-missing}"
  adb logcat -c
  adb shell am start -n $PKG/com.ali.rafiq.MainActivity --es setRiwaya "$riw" --ez openReciteWithMe true --ez autoRecite true >/dev/null
  # مهلةٌ للنموذج/السحابة ثم زمنُ التسجيل وهامش
  local t=0 lim=$((dur + 150))
  while [ $t -lt $lim ]; do
    sleep 5; t=$((t+5))
    adb logcat -d -s recite:D > "e2e/$name.log" 2>/dev/null
    grep -q "locked" "e2e/$name.log" && [ $t -gt $((dur + 20)) ] && break
  done
  adb logcat -d -s recite:D > "e2e/$name.log" 2>/dev/null
  local flat; flat=$(grep -o "locked [A-Z]* flat=[0-9]*" "e2e/$name.log" | head -1 | grep -o "[0-9]*$")
  if [ -n "$flat" ] && [ $(( flat>EXP ? flat-EXP : EXP-flat )) -le 1 ]; then r=PASS; else r=FAIL; fi
  say "SCENARIO $name riwaya=$riw expect_flat=$EXP(±1: 18:22/23) locked_flat=${flat:-none} => $r"
  grep -E "audio|locate|locked|done|events" "e2e/$name.log" | sed -E 's/^.{0,19}//' | cut -c1-260 | head -14 | sed 's/^/  | /' | tee -a "$OUT" >/dev/null
  stop_app
  adb shell run-as $PKG rm -f files/tasmi_inject.wav
}

# ① بلا شبكة قبل تنزيل أيّ نموذج: الرسالةُ الظاهرة
adb shell svc wifi disable; adb shell svc data disable; sleep 3
adb logcat -c
adb shell am start -n $PKG/com.ali.rafiq.MainActivity --ez openReciteWithMe true --ez autoRecite true >/dev/null
sleep 25
adb shell uiautomator dump /sdcard/ui.xml >/dev/null 2>&1; adb pull /sdcard/ui.xml e2e/ui_off.xml >/dev/null 2>&1
TXT=$(python3 - <<'PY'
import re
try: s=open("e2e/ui_off.xml",encoding="utf-8").read()
except Exception: s=""
t=[x for x in re.findall(r'text="([^"]+)"',s) if len(x)>6]
print(" / ".join(t)[:300])
PY
)
say "SCENARIO offline_recite_with_me ui_text: ${TXT:-<none>}"
adb logcat -d -s recite:D AndroidRuntime:E | grep -E "recite|FATAL" | cut -c1-200 | head -5 | sed 's/^/  | /' | tee -a "$OUT" >/dev/null
stop_app
adb shell svc wifi enable; adb shell svc data enable
# 🌐 انتظارُ الشبكة فعلاً لا 8ث ثابتة
for _ in $(seq 1 30); do adb shell ping -c1 -W2 1.1.1.1 >/dev/null 2>&1 && break; sleep 2; done

scenario hafs_start hafs_start.wav hafs
scenario hafs_mid hafs_mid.wav hafs
scenario qalun_start qalun_start.wav qalun
scenario hafs_basmala_prefix hafs_basmala.wav hafs
if adb logcat -d -b crash 2>/dev/null | grep -q "$PKG"; then say "CRASH: yes"; adb logcat -d -b crash | grep -A3 "FATAL" | cut -c1-200 | head -8 | tee -a "$OUT" >/dev/null; else say "CRASH: none"; fi
exit 0
