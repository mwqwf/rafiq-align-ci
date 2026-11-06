#!/usr/bin/env bash
# 📱 جولةُ الواجهة (2/2) — محاكٍ سحابيٌّ (API 34 · x86_64 · 3 ج.ب كجهازٍ اقتصاديّ · واجهةٌ عربيّة) يفتح كلَّ شاشةٍ
#    في «مصحفك» ويلتقطها، ويجرّب التسميعَ بصوتٍ محقون، والوضعَ الداكن، والخطَّ الكبير، وبلا شبكة، والإنجليزية،
#    ثمّ يزحف على الأزرار بميزانيةٍ زمنيّة ويقيس زمنَ الفتح والذاكرة والانهيارات (دراسة المستشار 2026-11-05).
#    المخرَج: tmp/ui_walk/<run_id>/ في R2 (لقطاتٌ كاملة ومصغّرة + شجرة الواجهة + تقريرٌ خام) — لا يكتب في timings/.
#    الكلفة: دقائقُ هذا المستودع العامّ مجّانية؛ وسؤالُ «اسأل» الواحد وتسميعٌ سحابيٌّ واحد = سنتات.
# ⟳ المراجعة 5 (2026-11-06 00:35Z): الرفعُ الحيّ كشف السببَ في دقيقتَين: avdmanager خرج بـ0 ولم يجد المحاكي الـAVD (ولا config.ini)
#    — وهو عينُ ما أهلك الشوطَ الأوّل. العلاج: ANDROID_AVD_HOME صريحٌ للطرفَين + طباعةُ خرج avdmanager + قراءةُ المسار من walk.ini + تحقّقٌ بـ-list-avds.
# ⟳ المراجعة 4 (2026-11-06 00:25Z): الشوط 42118906040 أُلغي بمهلة المهمّة (120 د) ولم يرفع شيئاً — بقي bash وadb وحدهما
#    بلا محاكٍ عند الإلغاء، أي أنّ المحاكي مات وانتظره `adb wait-for-device` بلا حدّ، وخرجُ السكربت كلُّه كان محبوساً في
#    `tail -400` فضاع. العلاج: (١) كلُّ انتظارٍ محدودٌ بمهلةٍ ويُفحص بقاءُ المحاكي قبله؛ (٢) سجلُّ التقدّم والتقريرُ الجزئيّ
#    والمصغّراتُ تُرفع إلى R2 كلَّ دقيقتَين ونصف (tmp/ui_walk/<run>/live/) فلا يضيع شيءٌ إن قُتل الشوط؛ (٣) خياراتُ المحاكي
#    هي خياراتُ وصفة device-matrix المجرَّبة وحدها (بلا -prop ولا -memory)؛ (٤) الميزانية 100 د من البدء تترك 20 د للختام؛
#    (٥) KVM شرطٌ لا تحذير (x86_64 بلا تسريعٍ لا يُقلع أصلاً). ويُعاد بسكربت الجولة وحده لأنّ APK المصدر 7c45dde في R2.
# ⟳ المراجعة 3ب (2026-11-05 22:14Z): إيداعٌ مباشرٌ فوق main لأنّ دفعةَ الدمج لا تُظهر السكربتين لـagent-job.
# ⟳ المراجعة 3 (2026-11-05 22:10Z): يُعاد مع السكربت الأوّل بعد إصلاح إيجاد APK (الشوط 42115041851 بنى ولم يجد الملف).
set -uo pipefail
mkdir -p /tmp/ui_walk/out /tmp/ui_walk/live
OUT=/tmp/ui_walk/out
APK=/tmp/ui_walk/app-debug.apk
WS="${GITHUB_WORKSPACE:-$(pwd)}"
PROG=/tmp/ui_walk/progress.log
RUN="${GITHUB_RUN_ID:-local}"
exec > >(tee -a "$PROG") 2>&1
say(){ echo "▸ $(date -u +%H:%M:%S) $*"; }
START=$(cat /tmp/ui_walk_start 2>/dev/null || date +%s)
DEADLINE=$((START + 100*60))     # الشوطُ 120 د من بدء المهمّة؛ تُترك 20 د للتغليف والرفع والإيداع
say "الميزانية: $(( (DEADLINE-$(date +%s))/60 )) د حتى نهاية الجولة · الشوط $RUN"

# ───── الرفعُ الحيّ: ما يُنتَج يُرفع تدريجيّاً كي لا يضيع إن قُتل الشوط ─────
cat > /tmp/ui_walk/live_push.py <<'PY'
import boto3, os, sys, tarfile, glob
e = os.environ
if not e.get("R2_ENDPOINT"): sys.exit(0)
s3 = boto3.client("s3", endpoint_url=e["R2_ENDPOINT"], aws_access_key_id=e["R2_ACCESS_KEY_ID"],
                  aws_secret_access_key=e["R2_SECRET_ACCESS_KEY"], region_name="auto")
b = e["R2_BUCKET"]; run = e.get("GITHUB_RUN_ID", "local"); out = "/tmp/ui_walk/out"
small = sorted(glob.glob(out + "/small/*.jpg"))
if small:
    with tarfile.open("/tmp/ui_walk/live/live_small.tgz", "w:gz") as t:
        for p in small: t.add(p, arcname="small/" + os.path.basename(p))
files = [("/tmp/ui_walk/progress.log", "progress.log", "text/plain; charset=utf-8"),
         ("/tmp/ui_walk/walk_stdout.log", "walk_stdout.log", "text/plain; charset=utf-8"),
         ("/tmp/ui_walk/live/emulator_tail.txt", "emulator_tail.txt", "text/plain; charset=utf-8"),
         (out + "/walk_report.json", "walk_report.json", "application/json"),
         (out + "/walk_report.md", "walk_report.md", "text/markdown; charset=utf-8"),
         ("/tmp/ui_walk/live/live_small.tgz", "live_small.tgz", "application/gzip")]
n = 0
for src, key, ct in files:
    if os.path.isfile(src) and os.path.getsize(src) > 0:
        try:
            s3.upload_file(src, b, f"tmp/ui_walk/{run}/live/{key}", ExtraArgs={"ContentType": ct}); n += 1
        except Exception as ex:
            print("⚠ live", key, str(ex)[:120])
print(f"live↑ {n} ملفّات · لقطات {len(small)}")
PY
live_push(){
  tail -300 /tmp/ui_walk/emulator.log > /tmp/ui_walk/live/emulator_tail.txt 2>/dev/null || true
  mkdir -p "$OUT/small"
  for p in "$OUT"/shots/*.png; do
    [ -f "$p" ] || continue
    j="$OUT/small/$(basename "${p%.png}").jpg"
    [ -f "$j" ] || ffmpeg -loglevel error -y -i "$p" -vf scale=540:-1 -q:v 5 "$j" 2>/dev/null || true
  done
  timeout 120 python3 /tmp/ui_walk/live_push.py 2>&1 | tail -3 | sed 's/^/   /'
}
( while :; do sleep 150; live_push >> /tmp/ui_walk/live/push.log 2>&1; done ) &
PUSHER=$!
die(){ echo "⛔ $*"; tail -40 /tmp/ui_walk/emulator.log 2>/dev/null; kill $PUSHER 2>/dev/null; live_push; exit 1; }

say "① APK"
if [ ! -s "$APK" ]; then
  say "لا APK من السكربت الأوّل في هذا الشوط — يُنزَّل آخرُ بناءٍ من R2"
  timeout 600 python3 - <<'PY' || die "لا APK في R2 ولا في الشوط"
import boto3, os
s3 = boto3.client("s3", endpoint_url=os.environ["R2_ENDPOINT"], aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
                  aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"], region_name="auto")
s3.download_file(os.environ["R2_BUCKET"], "tmp/ui_walk/apk/app-debug.apk", "/tmp/ui_walk/app-debug.apk")
print(s3.get_object(Bucket=os.environ["R2_BUCKET"], Key="tmp/ui_walk/apk/LATEST.json")["Body"].read().decode())
PY
fi
[ -s "$APK" ] || die "لا APK"
say "APK $(( $(stat -c %s "$APK")/1024/1024 )) م.ب"

say "② صوتُ الحقن للتسميع (مصادرُ عامّة؛ لا صوتَ مستخدم)"
( cd "$WS" && timeout 600 bash tools/app_e2e/prep_audio.sh ) > /tmp/ui_walk/prep_audio.log 2>&1 \
  && say "جاهز: $(ls "$WS"/e2e/*.wav 2>/dev/null | xargs -n1 basename | tr '\n' ' ')" \
  || { say "⚠ تعذّر تجهيزُ الصوت ($(tail -2 /tmp/ui_walk/prep_audio.log | tr '\n' ' ' | cut -c1-160)) — تُلتقط شاشاتُ التسميع بلا صوت"; }
WAV="$WS/e2e/hafs_start.wav"; [ -s "$WAV" ] || WAV=""

say "③ عُدّةُ أندرويد: المحاكي وصورةُ النظام (API 34 · google_apis · x86_64)"
SDK="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-/usr/local/lib/android/sdk}}"
SDKM="$SDK/cmdline-tools/latest/bin/sdkmanager"
[ -x "$SDKM" ] || SDKM=$(ls -d "$SDK"/cmdline-tools/*/bin/sdkmanager 2>/dev/null | tail -1)
[ -x "${SDKM:-/nonexistent}" ] || { ls "$SDK" 2>/dev/null; die "لا sdkmanager في $SDK"; }
IMG="system-images;android-34;google_apis;x86_64"
yes 2>/dev/null | timeout 300 "$SDKM" --licenses > /dev/null 2>&1 || true
timeout 1200 "$SDKM" --install "platform-tools" "emulator" "$IMG" > /tmp/ui_walk/sdk.log 2>&1 || { tail -5 /tmp/ui_walk/sdk.log; die "sdkmanager"; }
export PATH="$SDK/platform-tools:$SDK/emulator:$PATH"
say "emulator $(emulator -version 2>/dev/null | head -1 | cut -c1-80) · adb $(adb --version 2>/dev/null | head -1 | cut -c1-60)"
echo 'KERNEL=="kvm", GROUP="kvm", MODE="0666", OPTIONS+="static_node=kvm"' | sudo tee /etc/udev/rules.d/99-kvm4all.rules > /dev/null
sudo udevadm control --reload-rules && sudo udevadm trigger --name-match=kvm
sudo setfacl -m "u:$(id -un):rw" /dev/kvm 2>/dev/null || true
test -r /dev/kvm -a -w /dev/kvm && say "KVM جاهز" || { ls -la /dev/kvm 2>&1; die "لا KVM — x86_64 لا يُقلع بلا تسريع (وصفةُ device-matrix تشترطه أيضاً)"; }
AVDM="$(dirname "$SDKM")/avdmanager"
# ⛔ الشوطان 42118906040 و42136701323: avdmanager خرج بـ0 ولم يجد المحاكي الـAVD («Unknown AVD name [walk]») — فيُثبَّت بيتُ الـAVD صريحاً
#    للطرفَين، ويُطبع خرجُ avdmanager كلُّه، ويُقرأ مسارُ الـAVD من walk.ini لا من افتراض، ويُتحقَّق بـ`emulator -list-avds` قبل الإقلاع.
export ANDROID_AVD_HOME=/tmp/ui_walk/avd; mkdir -p "$ANDROID_AVD_HOME"
echo no | timeout 300 "$AVDM" create avd --force -n walk --abi google_apis/x86_64 --package "$IMG" --device pixel_2 > /tmp/ui_walk/avd.log 2>&1; RCA=$?
say "avdmanager خرج بـ$RCA؛ خرجُه:"; sed 's/^/   │ /' /tmp/ui_walk/avd.log | head -20
say "بيئة أندرويد: $(env | grep -i -E '^(ANDROID|HOME=)' | tr '\n' ' ' | cut -c1-300)"
say "AVDs التي يراها المحاكي: [$(emulator -list-avds 2>/dev/null | tr '\n' ' ')] · محتوى $ANDROID_AVD_HOME: [$(ls "$ANDROID_AVD_HOME" 2>/dev/null | tr '\n' ' ')] · ~/.android/avd: [$(ls "$HOME/.android/avd" 2>/dev/null | tr '\n' ' ')]"
INI=$(ls "$ANDROID_AVD_HOME"/walk.ini "$HOME"/.android/avd/walk.ini 2>/dev/null | head -1)
[ -n "$INI" ] || { find / -name 'walk.ini' -not -path '/proc/*' 2>/dev/null | head -5; die "لم يُنشأ AVD (avdmanager خرج بـ$RCA)"; }
AVDDIR=$(grep -E '^path=' "$INI" | head -1 | cut -d= -f2-); [ -d "$AVDDIR" ] || AVDDIR="$(dirname "$INI")/walk.avd"
CFG="$AVDDIR/config.ini"; [ -f "$CFG" ] || die "لا config.ini في $AVDDIR"
sed -i '/^hw.ramSize/d;/^hw.keyboard/d;/^hw.lcd.density/d;/^disk.dataPartition.size/d' "$CFG"
printf 'hw.ramSize=3072\nhw.keyboard=yes\nhw.lcd.density=420\ndisk.dataPartition.size=4096M\n' >> "$CFG"
say "AVD في $AVDDIR · $(grep -c '' "$CFG") سطراً في config.ini"
emulator -list-avds 2>/dev/null | grep -qx walk || die "المحاكي لا يرى AVD walk بعد الإنشاء"
nproc; free -m | head -2

say "④ إقلاعُ المحاكي (خياراتُ device-matrix المجرَّبة)"
adb start-server > /dev/null 2>&1 || true
emulator -avd walk -no-window -gpu swiftshader_indirect -noaudio -no-boot-anim -camera-back none -no-snapshot \
  > /tmp/ui_walk/emulator.log 2>&1 &
EMU=$!
wait_boot(){   # $1 = أقصى عددِ دورات (كلٌّ 5 ث) — يفحص بقاءَ المحاكي قبل كلِّ سؤال، ولا ينتظر adb بلا حدّ
  local i b
  for i in $(seq 1 "$1"); do
    kill -0 $EMU 2>/dev/null || return 2
    b=$(timeout 15 adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')
    [ "$b" = "1" ] && return 0
    [ $((i % 12)) -eq 0 ] && say "   …انتظارُ الإقلاع $((i*5/60)) د · adb: $(timeout 10 adb devices 2>/dev/null | tail -n +2 | tr '\n' ' ' | cut -c1-80) · آخرُ المحاكي: $(tail -1 /tmp/ui_walk/emulator.log 2>/dev/null | cut -c1-100)"
    sleep 5
  done
  return 1
}
wait_boot 150; RC=$?
[ $RC -eq 2 ] && die "مات المحاكي قبل الإقلاع"
[ $RC -eq 1 ] && die "لم يُقلع المحاكي في 12.5 د"
say "أقلع في $(( ($(date +%s)-START)/60 )) د من بدء الشوط · أندرويد $(timeout 10 adb shell getprop ro.build.version.release | tr -d '\r') · لغة النظام: $(timeout 10 adb shell getprop persist.sys.locale | tr -d '\r')"
LOC=$(timeout 10 adb shell getprop persist.sys.locale | tr -d '\r')
if [ "${LOC:0:2}" != "ar" ]; then
  say "لغةُ النظام ليست عربيّة — تُضبط بالجذر ويُعاد تشغيلُ الإطار"
  timeout 60 adb root > /dev/null 2>&1; sleep 3; timeout 120 adb wait-for-device
  timeout 30 adb shell "setprop persist.sys.locale ar-EG; setprop ctl.restart zygote" > /dev/null 2>&1
  sleep 20; timeout 120 adb wait-for-device
  wait_boot 60 || say "⚠ لم يُثبَت الإقلاعُ بعد إعادة الإطار — نمضي"
  sleep 10
  say "لغة النظام الآن: $(timeout 10 adb shell getprop persist.sys.locale | tr -d '\r')"
fi
timeout 20 adb shell settings put global window_animation_scale 0; timeout 20 adb shell settings put global transition_animation_scale 0; timeout 20 adb shell settings put global animator_duration_scale 0
timeout 20 adb shell settings put secure immersive_mode_confirmations confirmed 2>/dev/null
timeout 20 adb shell input keyevent 82 > /dev/null 2>&1   # فكّ القفل

say "⑤ التثبيت والأذونات"
timeout 900 adb install -r -g "$APK" > /tmp/ui_walk/install.log 2>&1 && say "install: OK" || { tail -3 /tmp/ui_walk/install.log; die "install: FAIL"; }
PKG=com.mushafak.app
timeout 20 adb shell pm grant $PKG android.permission.RECORD_AUDIO 2>/dev/null || true
timeout 20 adb shell pm grant $PKG android.permission.POST_NOTIFICATIONS 2>/dev/null || true
timeout 20 adb shell cmd locale set-app-locales $PKG --user 0 --locale-tags ar-EG > /dev/null 2>&1 || true
say "لغةُ التطبيق: $(timeout 10 adb shell cmd locale get-app-locales $PKG --user 0 2>/dev/null | tr -d '\r' | head -1)"
live_push

say "⑥ الجولة (الميزانية حتى $(( (DEADLINE-$(date +%s))/60 )) د)"
BUD=$(( DEADLINE - $(date +%s) + 240 )); [ "$BUD" -lt 300 ] && BUD=300
timeout "$BUD" python3 "$WS/jobs/ui_walk/walk.py" --out "$OUT" --deadline "$DEADLINE" --wav "$WAV" --ask 1 > /tmp/ui_walk/walk_stdout.log 2>&1
say "walk.py خرج بـ$? · $(grep -c '📸' /tmp/ui_walk/walk_stdout.log) لقطة مسجّلة"
tail -60 /tmp/ui_walk/walk_stdout.log
timeout 120 adb logcat -d > "$OUT/logcat_full.txt" 2>/dev/null; tail -c 2000000 "$OUT/logcat_full.txt" > "$OUT/logcat_last2mb.txt"; rm -f "$OUT/logcat_full.txt"
tail -200 /tmp/ui_walk/emulator.log > "$OUT/emulator_tail.txt"
cp /tmp/ui_walk/install.log "$OUT/" 2>/dev/null
kill $EMU 2>/dev/null || true
kill $PUSHER 2>/dev/null || true

say "⑦ التغليف: مصغّراتٌ 540px للقراءة السريعة + الكامل"
mkdir -p "$OUT/small"
for p in "$OUT"/shots/*.png; do
  [ -f "$p" ] || continue
  j="$OUT/small/$(basename "${p%.png}").jpg"
  [ -f "$j" ] || ffmpeg -loglevel error -y -i "$p" -vf scale=540:-1 -q:v 5 "$j" 2>/dev/null || true
done
N=$(ls "$OUT"/shots/*.png 2>/dev/null | wc -l)
cp "$PROG" "$OUT/progress.log" 2>/dev/null; cp /tmp/ui_walk/walk_stdout.log "$OUT/" 2>/dev/null
( cd "$OUT" && tar czf /tmp/ui_walk/walk_small.tgz small walk_report.md walk_report.json xml meminfo.txt logcat_errors.txt recite_log.txt emulator_tail.txt install.log progress.log walk_stdout.log 2>/dev/null )
( cd "$OUT" && tar czf /tmp/ui_walk/walk_full.tgz shots logcat_last2mb.txt logcat_tail.txt 2>/dev/null )
say "لقطات: $N · small $(( $(stat -c %s /tmp/ui_walk/walk_small.tgz 2>/dev/null || echo 0)/1024 )) ك.ب · full $(( $(stat -c %s /tmp/ui_walk/walk_full.tgz 2>/dev/null || echo 0)/1024/1024 )) م.ب"

say "⑧ الرفعُ إلى R2: tmp/ui_walk/${RUN}/"
timeout 600 python3 - "$OUT" <<'PY'
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
live_push
echo "── رأسُ التقرير الخام ──"
head -12 "$OUT/walk_report.md" 2>/dev/null
sleep 1
exit 0
