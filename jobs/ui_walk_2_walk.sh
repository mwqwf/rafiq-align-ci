#!/usr/bin/env bash
# 📱 جولةُ الواجهة (2/2) — محاكٍ سحابيٌّ (API 34 · x86_64 · 3 ج.ب كجهازٍ اقتصاديّ · واجهةٌ عربيّة) يفتح كلَّ شاشةٍ
# ⟳ المراجعة 2 (2026-11-05 21:45Z): إعادةُ إطلاقٍ بإيداعٍ مباشرٍ على main — دفعةُ الدمج لم يرَ فيها agent-job السكربتين (يقارن بالأب الأوّل).
# ⟳ المراجعة 3ب (2026-11-05 22:14Z): إيداعٌ مباشرٌ فوق main لأنّ دفعةَ الدمج لا تُظهر السكربتين لـagent-job.
# ⟳ المراجعة 3 (2026-11-05 22:10Z): يُعاد مع السكربت الأوّل بعد إصلاح إيجاد APK (الشوط 42115041851 بنى ولم يجد الملف).
#    في «مصحفك» ويلتقطها، ويجرّب التسميعَ بصوتٍ محقون، والوضعَ الداكن، والخطَّ الكبير، وبلا شبكة، والإنجليزية،
#    ثمّ يزحف على الأزرار بميزانيةٍ زمنيّة ويقيس زمنَ الفتح والذاكرة والانهيارات (دراسة المستشار 2026-11-05).
#    المخرَج: tmp/ui_walk/<run_id>/ في R2 (لقطاتٌ كاملة ومصغّرة + شجرة الواجهة + تقريرٌ خام) — لا يكتب في timings/.
#    الكلفة: دقائقُ هذا المستودع العامّ مجّانية؛ وسؤالُ «اسأل» الواحد وتسميعٌ سحابيٌّ واحد = سنتات.
set -uo pipefail
say(){ echo "▸ $*"; }
START=$(cat /tmp/ui_walk_start 2>/dev/null || date +%s)
DEADLINE=$((START + 108*60))     # الشوطُ 120 د؛ تُترك 12 د للتغليف والرفع والإيداع
mkdir -p /tmp/ui_walk/out
OUT=/tmp/ui_walk/out
APK=/tmp/ui_walk/app-debug.apk
WS="${GITHUB_WORKSPACE:-$(pwd)}"

say "① APK"
if [ ! -s "$APK" ]; then
  say "لا APK من السكربت الأوّل في هذا الشوط — يُنزَّل آخرُ بناءٍ من R2"
  python3 - <<'PY' || { echo "⛔ لا APK في R2 ولا في الشوط"; exit 1; }
import boto3, os
s3 = boto3.client("s3", endpoint_url=os.environ["R2_ENDPOINT"], aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
                  aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"], region_name="auto")
s3.download_file(os.environ["R2_BUCKET"], "tmp/ui_walk/apk/app-debug.apk", "/tmp/ui_walk/app-debug.apk")
print(s3.get_object(Bucket=os.environ["R2_BUCKET"], Key="tmp/ui_walk/apk/LATEST.json")["Body"].read().decode())
PY
fi
[ -s "$APK" ] || { echo "⛔ لا APK"; exit 1; }
say "APK $(( $(stat -c %s "$APK")/1024/1024 )) م.ب"

say "② صوتُ الحقن للتسميع (مصادرُ عامّة؛ لا صوتَ مستخدم)"
( cd "$WS" && bash tools/app_e2e/prep_audio.sh ) > /tmp/ui_walk/prep_audio.log 2>&1 \
  && say "جاهز: $(ls "$WS"/e2e/*.wav 2>/dev/null | xargs -n1 basename | tr '\n' ' ')" \
  || { say "⚠ تعذّر تجهيزُ الصوت ($(tail -2 /tmp/ui_walk/prep_audio.log | tr '\n' ' ' | cut -c1-160)) — تُلتقط شاشاتُ التسميع بلا صوت"; }
WAV="$WS/e2e/hafs_start.wav"; [ -s "$WAV" ] || WAV=""

say "③ عُدّةُ أندرويد: المحاكي وصورةُ النظام (API 34 · google_apis · x86_64)"
SDK="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-/usr/local/lib/android/sdk}}"
SDKM="$SDK/cmdline-tools/latest/bin/sdkmanager"
[ -x "$SDKM" ] || SDKM=$(ls -d "$SDK"/cmdline-tools/*/bin/sdkmanager 2>/dev/null | tail -1)
[ -x "${SDKM:-/nonexistent}" ] || { echo "⛔ لا sdkmanager في $SDK"; ls "$SDK" 2>/dev/null; exit 1; }
IMG="system-images;android-34;google_apis;x86_64"
yes 2>/dev/null | "$SDKM" --licenses > /dev/null 2>&1 || true
"$SDKM" --install "platform-tools" "emulator" "$IMG" > /tmp/ui_walk/sdk.log 2>&1 || { echo "⛔ sdkmanager"; tail -5 /tmp/ui_walk/sdk.log; exit 1; }
export PATH="$SDK/platform-tools:$SDK/emulator:$PATH"
echo 'KERNEL=="kvm", GROUP="kvm", MODE="0666", OPTIONS+="static_node=kvm"' | sudo tee /etc/udev/rules.d/99-kvm4all.rules > /dev/null
sudo udevadm control --reload-rules && sudo udevadm trigger --name-match=kvm
sudo setfacl -m "u:$(id -un):rw" /dev/kvm 2>/dev/null || true
test -r /dev/kvm -a -w /dev/kvm && say "KVM جاهز" || say "⚠ لا KVM — سيكون المحاكي بطيئاً جدّاً"
AVDM="$(dirname "$SDKM")/avdmanager"
echo no | "$AVDM" create avd -n walk -k "$IMG" -d pixel_2 --force > /dev/null 2>&1 || { echo "⛔ avdmanager"; exit 1; }
CFG="$HOME/.android/avd/walk.avd/config.ini"
sed -i '/^hw.ramSize/d;/^hw.keyboard/d;/^hw.lcd.density/d;/^disk.dataPartition.size/d' "$CFG"
printf 'hw.ramSize=3072\nhw.keyboard=yes\nhw.lcd.density=420\ndisk.dataPartition.size=4096M\n' >> "$CFG"

say "④ إقلاعُ المحاكي (عربيّ من البدء)"
emulator -avd walk -no-window -gpu swiftshader_indirect -noaudio -no-boot-anim -camera-back none -no-snapshot \
  -memory 3072 -cores 2 -prop persist.sys.locale=ar-EG -prop persist.sys.language=ar -prop persist.sys.country=EG \
  > /tmp/ui_walk/emulator.log 2>&1 &
EMU=$!
adb start-server > /dev/null 2>&1
adb wait-for-device
for i in $(seq 1 120); do
  [ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = "1" ] && break
  kill -0 $EMU 2>/dev/null || { echo "⛔ مات المحاكي"; tail -20 /tmp/ui_walk/emulator.log; exit 1; }
  sleep 5
done
[ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = "1" ] || { echo "⛔ لم يُقلع المحاكي في 10 د"; tail -20 /tmp/ui_walk/emulator.log; exit 1; }
say "أقلع في $(( ($(date +%s)-START)/60 )) د من بدء الشوط · $(adb shell getprop ro.build.version.release | tr -d '\r') · لغة النظام: $(adb shell getprop persist.sys.locale | tr -d '\r')"
LOC=$(adb shell getprop persist.sys.locale | tr -d '\r')
if [ "${LOC:0:2}" != "ar" ]; then
  say "لغةُ النظام ليست عربيّة — تُضبط بالجذر ويُعاد تشغيلُ الإطار"
  adb root > /dev/null 2>&1; sleep 3; adb wait-for-device
  adb shell "setprop persist.sys.locale ar-EG; setprop ctl.restart zygote" > /dev/null 2>&1
  sleep 20; adb wait-for-device
  for i in $(seq 1 60); do [ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = "1" ] && break; sleep 3; done
  sleep 10
fi
adb shell settings put global window_animation_scale 0; adb shell settings put global transition_animation_scale 0; adb shell settings put global animator_duration_scale 0
adb shell settings put secure immersive_mode_confirmations confirmed 2>/dev/null
adb shell input keyevent 82 > /dev/null 2>&1   # فكّ القفل

say "⑤ التثبيت والأذونات"
adb install -r -g "$APK" > /tmp/ui_walk/install.log 2>&1 && say "install: OK" || { echo "⛔ install: FAIL"; tail -3 /tmp/ui_walk/install.log; exit 1; }
PKG=com.mushafak.app
adb shell pm grant $PKG android.permission.RECORD_AUDIO 2>/dev/null || true
adb shell pm grant $PKG android.permission.POST_NOTIFICATIONS 2>/dev/null || true
adb shell cmd locale set-app-locales $PKG --user 0 --locale-tags ar-EG > /dev/null 2>&1 || true
say "لغةُ التطبيق: $(adb shell cmd locale get-app-locales $PKG --user 0 2>/dev/null | tr -d '\r' | head -1)"

say "⑥ الجولة (الميزانية حتى $(( (DEADLINE-$(date +%s))/60 )) د)"
python3 "$WS/jobs/ui_walk/walk.py" --out "$OUT" --deadline "$DEADLINE" --wav "$WAV" --ask 1 2>&1 | tail -150
adb logcat -d > "$OUT/logcat_full.txt" 2>/dev/null; tail -c 2000000 "$OUT/logcat_full.txt" > "$OUT/logcat_last2mb.txt"; rm -f "$OUT/logcat_full.txt"
tail -200 /tmp/ui_walk/emulator.log > "$OUT/emulator_tail.txt"
cp /tmp/ui_walk/install.log "$OUT/" 2>/dev/null
kill $EMU 2>/dev/null || true

say "⑦ التغليف: مصغّراتٌ 540px للقراءة السريعة + الكامل"
mkdir -p "$OUT/small"
for p in "$OUT"/shots/*.png; do
  [ -f "$p" ] || continue
  ffmpeg -loglevel error -y -i "$p" -vf scale=540:-1 -q:v 5 "$OUT/small/$(basename "${p%.png}").jpg" 2>/dev/null || true
done
N=$(ls "$OUT"/shots/*.png 2>/dev/null | wc -l)
( cd "$OUT" && tar czf /tmp/ui_walk/walk_small.tgz small walk_report.md walk_report.json xml meminfo.txt logcat_errors.txt recite_log.txt emulator_tail.txt install.log 2>/dev/null )
( cd "$OUT" && tar czf /tmp/ui_walk/walk_full.tgz shots logcat_last2mb.txt logcat_tail.txt 2>/dev/null )
say "لقطات: $N · small $(( $(stat -c %s /tmp/ui_walk/walk_small.tgz 2>/dev/null || echo 0)/1024 )) ك.ب · full $(( $(stat -c %s /tmp/ui_walk/walk_full.tgz 2>/dev/null || echo 0)/1024/1024 )) م.ب"

say "⑧ الرفعُ إلى R2: tmp/ui_walk/${GITHUB_RUN_ID:-local}/"
python3 - "$OUT" <<'PY'
import boto3, os, sys
s3 = boto3.client("s3", endpoint_url=os.environ["R2_ENDPOINT"], aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
                  aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"], region_name="auto")
b = os.environ["R2_BUCKET"]; run = os.environ.get("GITHUB_RUN_ID", "local"); out = sys.argv[1]
for src, key, ct in (("/tmp/ui_walk/walk_small.tgz", "walk_small.tgz", "application/gzip"),
                     ("/tmp/ui_walk/walk_full.tgz", "walk_full.tgz", "application/gzip"),
                     (f"{out}/walk_report.md", "walk_report.md", "text/markdown; charset=utf-8"),
                     (f"{out}/walk_report.json", "walk_report.json", "application/json")):
    if os.path.isfile(src):
        s3.upload_file(src, b, f"tmp/ui_walk/{run}/{key}", ExtraArgs={"ContentType": ct})
        print(f"✅ tmp/ui_walk/{run}/{key} ({os.path.getsize(src)//1024} ك.ب)")
PY
echo "── رأسُ التقرير الخام ──"
head -12 "$OUT/walk_report.md" 2>/dev/null
exit 0
