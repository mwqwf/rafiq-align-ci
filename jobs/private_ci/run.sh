#!/usr/bin/env bash
# 🔒 private-ci — يستنسخ مجلّدات التطبيق والمحرّك من المستودع الخاص استنساخاً جزئيّاً ويبني ويختبر،
#    و**كلُّ مخرجٍ إلى ملفٍّ واحد من أوّل أمر** ($PCI_OUT/log.txt) — فالسجلُّ العلنيُّ يُبثّ حيّاً ولا يمحوه حارسٌ لاحق.
#
# الأطوار (‏المعامل الأوّل):
#   clone    — الطورُ الوحيد الذي يرى مفتاحَ القراءة (PCI_KEY_B64 في بيئة هذه الخطوة وحدها). يُمسح المفتاحُ بعده.
#   build    — ما قبل المحاكي (‏تحويلٌ واختباراتٌ وتجهيز).  ⛔ بلا أيّ سرٍّ في البيئة.
#   emu      — يجري داخل android-emulator-runner.          ⛔ بلا أيّ سرٍّ في البيئة.
#   finalize — يعدّ النتائج ويكتب counts.json وملخّصاً مرشَّحاً للنشر (summary.md) بأعدادٍ فقط.
#
# ⛔ لا `set -x` ولا طباعةٌ إلى stdout في أيّ طور: السطرُ الوحيد الذي قد يصل السجلَّ العلنيّ رفضُ الاستدعاء أدناه.
# ⛔ ولا يُشغَّل إلا من private-ci.yml: agent-job.yml يُنفّذ كلَّ jobs/**/*.sh تغيّر في دفعةٍ (‏مِحرفُ git يعبر `/`)
#    ومعه مفتاحُ المستودع على مستوى المستودع — فبلا هذا الشرط يصير هذا الملفُّ نفسُه بابَ تسريب.
set -uo pipefail

case "${GITHUB_WORKFLOW_REF:-}" in
  */.github/workflows/private-ci.yml@*) ;;
  *) echo "⛔ jobs/private_ci/run.sh لا يُشغَّل إلا من private-ci.yml — لا شيء نُفّذ."; exit 0 ;;
esac

MODE="${1:-}"
: "${RUNNER_TEMP:?}" "${PCI_KIND:?}" "${PCI_SHA:?}" "${PCI_SOURCE:?}" "${PCI_LEG:?}"
PCI_ROOT="$RUNNER_TEMP/private_ci"
PCI_OUT="$PCI_ROOT/out"          # ما يُرفع إلى R2 الخاص (log.txt · counts.json · summary.md)
PCI_STATE="$PCI_ROOT/state"      # رموزُ خروج الأطوار والرابطُ الموقَّع (أذونات 700)
PCI_SRC="$PCI_ROOT/src"          # المصدرُ المستنسَخ
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
umask 077
mkdir -p "$PCI_OUT" "$PCI_STATE"

# ───── من هنا لا يخرج حرفٌ إلى السجلّ العلنيّ ─────
exec >>"$PCI_OUT/log.txt" 2>&1
# ⛔ ملفّاتُ أوامر GitHub تُحوَّل إلى ملفّاتٍ مهملة: لا تكتب شيفرةٌ تحت الاختبار ملخّصاً علنيّاً (emu_focused.sh يكتب فيه)،
#    ولا تحقن متغيّراً أو مساراً في الخطوات التالية التي تحمل بيانةَ R2 ورمزَ الحالة.
for v in GITHUB_STEP_SUMMARY GITHUB_ENV GITHUB_OUTPUT GITHUB_PATH GITHUB_STATE; do
  export "$v=$PCI_STATE/inner_${v,,}"
done
export GRADLE_OPTS="-Dorg.gradle.daemon=false -Dorg.gradle.console=plain"
export GRADLE_USER_HOME="$PCI_ROOT/gradle-home"
export CI=true TERM=dumb PYTHONIOENCODING=utf-8

say(){ printf '▸ %s [%s] %s\n' "$(date -u +%H:%M:%S)" "$MODE" "$*"; }
rc_set(){ printf '%s\n' "$2" > "$PCI_STATE/rc_$1"; }
step(){ # step <اسم> <أمر…> — يسجّل رمزَ الخروج ولا يقطع الطور (‏الحكمُ في finalize)
  local name="$1"; shift
  say "← $name"
  "$@"; local rc=$?
  rc_set "$name" "$rc"
  say "→ $name = $rc"
  return 0
}

# ───── أنماطُ الاستنساخ الجزئيّ (‏non-cone) — مجلّداتُ التطبيق والمحرّك فقط ─────
# ⛔ ما لا يُستنسخ أبداً: cloud/ · secure/ · store/ · tools/store · tools/cloud* · .github/ · docs/ (‏إلا دليلَ التطبيق
#    لحارسه) · ops/ (‏إلا ملفَّ طلب اللقطات). ويُتحقَّق بعد الاستنساخ أنّ شيئاً منها لم يدخل.
BUILD_SET=(/gradlew /gradle/ /settings.gradle.kts /build.gradle.kts /gradle.properties
           /app/ /core/ /engine/ /feature/ /baselineprofile/ /tools/size/)
sparse_for_kind(){
  case "$PCI_KIND" in
    dry-run)                     printf '%s\n' /jobs/private_ci/ ;;
    app-test)                    printf '%s\n' "${BUILD_SET[@]}" /tools/ai/ /tools/ux/ /tools/i18n/ /docs/ai/app_guide/ ;;
    engine-test)                 printf '%s\n' "${BUILD_SET[@]}" /tools/tasmi_bench/ /tools/tasmi_phoneme/ /tools/ci/ ;;
    engine-models)               printf '%s\n' /engine/recitation/src/main/ /tools/tasmi_bench/ ;;
    tasmi-model-emulator-smoke)  printf '%s\n' "${BUILD_SET[@]}" /tools/ci/ ;;
    ui-shots-emu)                printf '%s\n' "${BUILD_SET[@]}" /tools/ci/ /ops/ui_shots/request.txt ;;
    hudhud-feature-test)         printf '%s\n' "${BUILD_SET[@]}" /tools/hudhud/ ;;
    ads-emulator-smoke)          printf '%s\n' "${BUILD_SET[@]}" /tools/ci/ ;;
    device-matrix)               printf '%s\n' "${BUILD_SET[@]}" /tools/qa/ /tools/ci/ ;;
    *) return 1 ;;
  esac
}
FORBIDDEN_RX='^(cloud|secure|store|\.github|tools/store|tools/cloud[^/]*|tools/ops)(/|$)|^docs/(?!ai/app_guide/)|^ops/(?!ui_shots/request\.txt$)'
FORBIDDEN_NAME_RX='(^|/)(keystore\.properties|google-services\.json|local\.properties|r2_credentials[^/]*|\.env[^/]*)$|\.(jks|keystore|p12|pem|key)$'

github_known_hosts(){ # مفاتيحُ مضيف GitHub من واجهته فوق TLS — لا قبولَ لمضيفٍ جديدٍ ولا لمفتاحٍ متغيّر
  python3 - "$1" <<'PY'
import json, sys, urllib.request
with urllib.request.urlopen("https://api.github.com/meta", timeout=30) as r:
    keys = json.load(r)["ssh_keys"]
with open(sys.argv[1], "w") as f:
    for k in keys:
        f.write("github.com " + k + "\n")
print(f"known_hosts: {len(keys)} مفاتيح من api.github.com/meta")
PY
}

scrub_key(){ # المفتاحُ يُمسح من القرص ومن البيئة في كلّ مخرجٍ من طور الاستنساخ — نجح أو فشل
  [ -f "$PCI_ROOT/ssh/id" ] && shred -u "$PCI_ROOT/ssh/id" 2>/dev/null
  rm -rf "$PCI_ROOT/ssh"
  unset PCI_KEY_B64 GIT_SSH_COMMAND 2>/dev/null || true
}

do_clone(){ do_clone_inner; local rc=$?; scrub_key; return $rc; }

do_clone_inner(){
  rm -rf "$PCI_SRC"; mkdir -p "$PCI_SRC"
  local url
  if [ "$PCI_SOURCE" = "public" ]; then
    url="https://github.com/${GITHUB_REPOSITORY:?}.git"
    # 🧪 للاختبار المحلّيّ وحده: مستودعٌ محلّيّ بدل GitHub — ولا يُقبل داخل GitHub Actions أبداً.
    [ "${GITHUB_ACTIONS:-}" != "true" ] && [ -n "${PCI_TEST_REMOTE:-}" ] && url="$PCI_TEST_REMOTE"
    unset PCI_KEY_B64 || true
  else
    [ -n "${PCI_KEY_B64:-}" ] || { say "⛔ لا مفتاحَ قراءة"; return 1; }
    url="git@github.com:mwqwf/QuranRafiq.git"
    local kd="$PCI_ROOT/ssh"; mkdir -p "$kd"; chmod 700 "$kd"
    printf '%s' "$PCI_KEY_B64" | base64 --decode > "$kd/id" 2>/dev/null || { unset PCI_KEY_B64; say "⛔ المفتاحُ غيرُ مقروء"; return 1; }
    unset PCI_KEY_B64
    chmod 600 "$kd/id"
    github_known_hosts "$kd/known_hosts" || { say "⛔ تعذّر جلبُ مفاتيح مضيف GitHub"; return 1; }
    export GIT_SSH_COMMAND="ssh -i $kd/id -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$kd/known_hosts -o BatchMode=yes"
  fi
  local patterns; patterns="$(sparse_for_kind)" || { say "⛔ نوعٌ بلا أنماط"; return 1; }
  git -C "$PCI_SRC" init -q
  git -C "$PCI_SRC" remote add origin "$url"
  git -C "$PCI_SRC" config core.sparseCheckout true
  git -C "$PCI_SRC" sparse-checkout set --no-cone $patterns
  # جزئيٌّ مرّتين: عمقٌ واحد وبلا كتل (blob:none) — فلا يُنزَّل من الكتل إلا ما تطلبه الأنماط عند الإخراج.
  git -C "$PCI_SRC" fetch -q --depth 1 --filter=blob:none origin "$PCI_SHA" || { say "⛔ تعذّر جلبُ الإيداع"; return 1; }
  git -C "$PCI_SRC" checkout -q --detach FETCH_HEAD || { say "⛔ تعذّر الإخراج"; return 1; }
  [ "$(git -C "$PCI_SRC" rev-parse HEAD)" = "$PCI_SHA" ] || { say "⛔ الرأسُ لا يطابق المطلوب"; return 1; }
  # مرجعُ whisper.cpp المثبَّت يُقرأ من مصدره الواحد (publish-apk.yml) **بلا إخراجه**: سطرٌ واحد من كتلته والمفتاحُ حاضر.
  if [ "$PCI_SOURCE" = "private" ]; then
    git -C "$PCI_SRC" cat-file -p "HEAD:.github/workflows/publish-apk.yml" 2>/dev/null \
      | grep -oE 'WHISPER_CPP_REF: *[0-9a-f]{40}' | head -1 | grep -oE '[0-9a-f]{40}' > "$PCI_STATE/whisper_ref" || true
  fi
  unset GIT_SSH_COMMAND
  git -C "$PCI_SRC" remote remove origin   # ⛔ لا جلبَ كسولٍ بعد الآن: أيُّ كتلةٍ ناقصة تفشل ولا تستعمل مفتاحاً
  # ⛔ التحقّق: لا مسارَ ممنوعٌ في الشجرة المُخرَجة، ولا ملفُّ أسرار
  local bad
  # ما على القرص فعلاً (‏لا فهرسُ git: الفهرسُ في الاستنساخ الجزئيّ يُدرج ما لم يُخرَج أيضاً)
  bad=$( (cd "$PCI_SRC" && find . -path ./.git -prune -o \( -type f -o -type l \) -print | sed 's|^\./||') | python3 -c "
import re, sys
rx = re.compile(r'''$FORBIDDEN_RX'''); nx = re.compile(r'''$FORBIDDEN_NAME_RX''')
n = sum(1 for p in sys.stdin.read().split(chr(10)) if p and (rx.search(p) or nx.search(p)))
print(n)")
  if [ "${bad:-1}" != "0" ]; then say "⛔ $bad مساراً ممنوعاً في الاستنساخ — يُمحى المصدر"; rm -rf "$PCI_SRC"; return 1; fi
  say "استُنسخ $( (cd "$PCI_SRC" && find . -path ./.git -prune -o -type f -print) | wc -l) ملفّاً · المصدر $PCI_SOURCE"
  return 0
}

fetch_whisper(){
  local ref; ref="$(cat "$PCI_STATE/whisper_ref" 2>/dev/null)"
  [[ "$ref" =~ ^[0-9a-f]{40}$ ]] || { say "⛔ لم يُقرأ WHISPER_CPP_REF — ولا يُفترض رقمٌ بديل"; return 1; }
  local wd="$PCI_SRC/third_party/whisper.cpp"
  git clone -q --filter=blob:none --no-checkout https://github.com/ggml-org/whisper.cpp "$wd" || return 1
  git -C "$wd" fetch -q --depth 1 origin "$ref" && git -C "$wd" checkout -q --detach FETCH_HEAD || return 1
  [ "$(git -C "$wd" rev-parse HEAD)" = "$ref" ]
}

fatiha_wav(){ # تلاوةٌ بشريّةٌ منشورة (الحصري · الفاتحة) — لا صوتَ مستخدم
  bash tools/ci/ensure_ffmpeg.sh || return 1
  mkdir -p app/src/androidTest/assets
  curl -fsSL --retry 3 -o "$PCI_ROOT/fatiha.mp3" https://server13.mp3quran.net/husr/001.mp3 || return 1
  ffmpeg -hide_banner -loglevel error -y -i "$PCI_ROOT/fatiha.mp3" -ac 1 -ar 16000 -c:a pcm_s16le \
    -map_metadata -1 -fflags +bitexact -flags:a +bitexact app/src/androidTest/assets/tasmi_fatiha_husary.wav || return 1
  [ "$(stat -c %s app/src/androidTest/assets/tasmi_fatiha_husary.wav)" -gt 640044 ]
}

free_disk(){ sudo rm -rf /usr/share/dotnet /opt/ghc /usr/local/.ghcup /opt/hostedtoolcache/CodeQL /usr/local/share/boost; df -h /; }

enable_kvm(){
  echo 'KERNEL=="kvm", GROUP="kvm", MODE="0666", OPTIONS+="static_node=kvm"' | sudo tee /etc/udev/rules.d/99-kvm4all.rules >/dev/null
  sudo udevadm control --reload-rules && sudo udevadm trigger --name-match=kvm && sudo udevadm settle
  sudo setfacl -m "u:$(id -un):rw" /dev/kvm
  test -r /dev/kvm -a -w /dev/kvm
}

gradle(){ chmod +x ./gradlew && ./gradlew --no-daemon --console=plain "$@"; }

jni_check(){ # فحصٌ نحويٌّ لجسر jni.c على ترويسات الالتزام المثبَّت (‏مطابقٌ لوظيفة jni في engine-test.yml)
  local ref; ref="$(cat "$PCI_STATE/whisper_ref" 2>/dev/null)"; [[ "$ref" =~ ^[0-9a-f]{40}$ ]] || return 1
  local ck="$PCI_ROOT/ck"; mkdir -p "$ck/inc/android"
  local f n
  for f in include/whisper.h ggml/include/ggml.h ggml/include/ggml-cpu.h ggml/include/ggml-backend.h ggml/include/ggml-alloc.h; do
    n=$(basename "$f")
    curl -fsS -o "$ck/inc/$n" "https://raw.githubusercontent.com/ggml-org/whisper.cpp/$ref/$f" || return 1
  done
  bash tools/tasmi_bench/jni_stubs.sh "$ck/inc/android" || return 1
  local jh="${JAVA_HOME:?}"
  sed 's/params\.no_speech_thold/params.no_speech_tholdZZ/' engine/recitation/src/main/cpp/jni.c > "$ck/bad.c"
  if gcc -fsyntax-only -std=c11 -I "$ck/inc" -I "$jh/include" -I "$jh/include/linux" "$ck/bad.c"; then
    say "⛔ الفحصُ قبل حقلاً لا وجودَ له ⇒ لا يحرس شيئاً"; return 1
  fi
  gcc -fsyntax-only -std=c11 -Werror=implicit-function-declaration -Werror=incompatible-pointer-types \
    -Werror=int-conversion -I "$ck/inc" -I "$jh/include" -I "$jh/include/linux" engine/recitation/src/main/cpp/jni.c
}

ui_shots_request(){ # صنفُ اللقطات ومتغيّرُها من ملفّ الطلب — بقيمٍ معروفة الشكل وحدها
  local cls var
  cls=$(sed -nE 's/^class[:=][[:space:]]*//p' ops/ui_shots/request.txt | head -1 | tr -d '\r ')
  var=$(sed -nE 's/^variant[:=][[:space:]]*//p' ops/ui_shots/request.txt | head -1 | tr -d '\r ')
  cls="${cls:-com.ali.rafiq.ui.UiTextComfortShotsTest}"
  [[ "$cls" =~ ^[A-Za-z][A-Za-z0-9_.]{2,200}$ ]] || return 1
  [[ -z "$var" || "$var" =~ ^[A-Za-z0-9_-]{1,40}$ ]] || return 1
  printf '%s\n%s\n' "$cls" "$var" > "$PCI_STATE/ui_shots_req"
}

do_build(){
  cd "$PCI_SRC" || return 1
  case "$PCI_KIND" in
    dry-run)
      step unit python3 -m unittest discover -s jobs/private_ci -p 'test_*.py' -v ;;
    app-test)
      step app_guide python3 tools/ai/test_app_guide_guard.py
      step no_blocking python3 tools/ux/test_no_blocking_notices.py
      step back_handling python3 tools/ux/test_back_handling.py
      step i18n_verify python3 tools/i18n/verify.py
      step i18n_locale python3 tools/i18n/check_locale.py --all
      step gradle gradle :app:compileDebugKotlin :app:testDebugUnitTest :core:quran:testDebugUnitTest :core:learning:test ;;
    engine-test)
      step pip python3 -m pip install --disable-pip-version-check --no-input -q "numpy==2.1.3" "soundfile==0.13.1"
      step fixture_selftest python3 tools/tasmi_bench/fixture_audit.py --selftest
      step fixture_audit python3 tools/tasmi_bench/fixture_audit.py
      step ffmpeg bash tools/ci/ensure_ffmpeg.sh
      step phoneme_gold python3 -m unittest discover -v -s tools/tasmi_phoneme -p "test_*.py"
      step jni jni_check
      step gradle gradle :engine:recitation:test ;;
    engine-models)
      step selftest python3 tools/tasmi_bench/model_urls_check.py --selftest
      step sizes python3 tools/tasmi_bench/model_urls_check.py
      step sha python3 tools/tasmi_bench/model_urls_check.py --sha ;;
    tasmi-model-emulator-smoke|ads-emulator-smoke)
      step whisper fetch_whisper
      [ "$PCI_KIND" = tasmi-model-emulator-smoke ] && step fatiha fatiha_wav
      step disk free_disk
      step kvm enable_kvm ;;
    ui-shots-emu)
      step request ui_shots_request
      step whisper fetch_whisper
      step disk free_disk
      step kvm enable_kvm ;;
    hudhud-feature-test)
      step whisper fetch_whisper
      step gradle gradle :app:bundleRelease :app:bundleDebug
      step bundletool curl -fsSL -o bundletool.jar https://github.com/google/bundletool/releases/download/1.18.3/bundletool-all-1.18.3.jar
      step disk free_disk
      step kvm enable_kvm ;;
    device-matrix)
      step whisper fetch_whisper
      step fatiha fatiha_wav
      step gradle gradle :app:assembleDebug :app:assembleDebugAndroidTest -Prafiq.testAbis=x86
      [ "${PCI_LINT:-false}" = "true" ] && step lint gradle :app:lintDebug
      step disk free_disk
      step kvm enable_kvm ;;
    *) say "⛔ نوعٌ غيرُ معروف"; rc_set kind 1 ;;
  esac
}

do_emu(){
  cd "$PCI_SRC" || { rc_set emu 1; return 0; }
  local cls var
  case "$PCI_KIND" in
    tasmi-model-emulator-smoke)
      step emu bash tools/ci/emu_focused.sh com.ali.rafiq.ui.tasmi.LongTasmiModelEmulatorTest,com.ali.rafiq.ui.tasmi.ReciteWithMeCloudEmulatorTest,com.ali.rafiq.ui.tasmi.TasmiRecreateEmulatorTest,com.ali.rafiq.ui.tasmi.TasmiEngineDeviceTest,com.ali.rafiq.ui.NewTabsSmokeEmulatorTest,com.ali.rafiq.ui.BackNavigationEmulatorTest ;;
    ads-emulator-smoke)
      step emu bash tools/ci/emu_focused.sh com.ali.rafiq.monetization.AdsEmulatorTest ;;
    ui-shots-emu)
      cls=$(sed -n 1p "$PCI_STATE/ui_shots_req" 2>/dev/null); var=$(sed -n 2p "$PCI_STATE/ui_shots_req" 2>/dev/null)
      if [ -n "$cls" ]; then step emu bash tools/ci/emu_focused.sh "$cls" "$var"; else rc_set emu 1; fi
      local d=app/build/outputs/androidTest-results/connected/ui_shots
      if [ -d "$d" ] && command -v mogrify >/dev/null; then mogrify -resize 540x "$d"/*.png || true; fi ;;
    hudhud-feature-test)
      step emu bash tools/hudhud/emulator_probe.sh app/build/outputs/bundle/debug/app-debug.aab bundletool.jar ;;
    device-matrix)
      mkdir -p "$PCI_ROOT/device"
      step emu_smoke bash tools/qa/device_smoke.sh "$(ls app/build/outputs/apk/debug/*.apk | head -1)" "$PCI_ROOT/device" "$PCI_LEG"
      step emu_tasmi bash tools/qa/tasmi_device.sh "$(ls app/build/outputs/apk/androidTest/debug/*.apk | head -1)" "$PCI_ROOT/device" ;;
    *) say "لا طورَ محاكٍ لهذا النوع" ;;
  esac
  return 0
}

do_finalize(){
  # الحكمُ والعدّ — كلُّ ما يخرج من هنا أعدادٌ وكلماتٌ ثابتة (‏الحارسُ يفحص summary.md قبل نشره)
  python3 - "$PCI_STATE" "$PCI_OUT" "$PCI_SRC" "$PCI_KIND" "$PCI_LEG" "${PCI_PLANT:-false}" "$PCI_ROOT/device" <<'PY'
import glob, json, os, re, sys
import xml.etree.ElementTree as ET
state, out, src, kind, leg, plant, device = sys.argv[1:8]
rcs = {}
for p in glob.glob(os.path.join(state, "rc_*")):
    try:
        rcs[os.path.basename(p)[3:]] = int(open(p).read().strip() or 1)
    except ValueError:
        rcs[os.path.basename(p)[3:]] = 1
xml_dirs = {
    "app-test": ["app/build/test-results", "core/quran/build/test-results", "core/learning/build/test-results"],
    "engine-test": ["engine/recitation/build/test-results"],
    "tasmi-model-emulator-smoke": ["app/build/outputs/androidTest-results/connected"],
    "ui-shots-emu": ["app/build/outputs/androidTest-results/connected"],
    "ads-emulator-smoke": ["app/build/outputs/androidTest-results/connected"],
}.get(kind, [])
t = f = e = reports = 0
for d in xml_dirs:
    for p in glob.glob(os.path.join(src, d, "**", "*.xml"), recursive=True):
        try:
            r = ET.parse(p).getroot()
        except ET.ParseError:
            e += 1
            continue
        if r.tag not in ("testsuite", "testsuites"):
            continue
        reports += 1
        t += int(r.get("tests", 0)); f += int(r.get("failures", 0)); e += int(r.get("errors", 0))
# ما لا تقرير JUnit له: يُعدّ كلُّ طورٍ مسمّى «اختباراً» (‏unittest/فحوص/محاكي بلا XML)
if kind in ("dry-run", "engine-models", "hudhud-feature-test", "device-matrix") or (kind == "engine-test"):
    # الاستنساخُ والتجهيزُ ليسا اختباراً: يُسقطان الشوطَ إن فشلا (‏failed_phases) ولا يُعدّان في الاختبارات
    prep = {"clone", "gradle", "pip", "ffmpeg", "whisper", "fatiha", "disk", "kvm", "bundletool", "request", "lint"}
    named = {k: v for k, v in rcs.items() if k not in prep}
    extra_t = len(named)
    extra_f = sum(1 for v in named.values() if v)
    t += extra_t; f += extra_f
if kind == "device-matrix":
    res = os.path.join(device, "result.md"); tas = os.path.join(device, "tasmi.md")
    ok1 = os.path.isfile(res) and "✅" in open(res, encoding="utf-8", errors="replace").read()
    ok2 = os.path.isfile(tas) and re.search(r"^التسميع: ✅", open(tas, encoding="utf-8", errors="replace").read(), re.M)
    t += 2; f += (0 if ok1 else 1) + (0 if ok2 else 1)
failed_phases = sorted(k for k, v in rcs.items() if v)
# lint لا يُسقط الشوط (‏كما في device-matrix.yml: يُعدّ ويُطبع والحكمُ على المحاكيات)
failed_phases = [k for k in failed_phases if k != "lint"]
ok = (not failed_phases) and f == 0 and e == 0 and t > 0
counts = {"tests": t, "failures": f, "errors": e, "reports": reports, "phases": len(rcs),
          "failed_phases": len(failed_phases), "ok": ok}
json.dump(counts, open(os.path.join(out, "counts.json"), "w"))
open(os.path.join(state, "verdict"), "w").write("success" if ok else "failure")
lines = [f"### 🔒 private-ci · {kind} · {leg}", "",
         f"| الحكم | الاختبارات | الإخفاقات | الأعطاب | تقارير | أطوارٌ فشلت |", "|---|---|---|---|---|---|",
         f"| {'✅ نجح' if ok else '⛔ فشل'} | {t} | {f} | {e} | {reports} | {len(failed_phases)} من {len(rcs)} |", ""]
if t == 0:
    lines.append("⛔ لا اختبارَ واحدٌ جرى — ولا يُقرأ الصفرُ نجاحاً.")
lines.append("السجلُّ الكامل في R2 الخاص؛ ورابطُه في حالة الإيداع بالمستودع الخاص.")
if plant == "true":
    # 🧪 تجربةُ الحارس: سطرٌ مزروعٌ يشبه شيفرةً ومساراً داخليّاً — يجب أن يحجب الملخّصَ ويطلب حذفَ السجلّ.
    lines.append("e: file:///home/runner/work/_temp/QuranRafiq/app/src/main/kotlin/x/Planted.kt:1:1 Unresolved reference")
open(os.path.join(out, "summary.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
PY
  python3 "$HERE/guard.py" --report --json "$PCI_OUT/guard_private.json" --label "السجلّ الخاص" "$PCI_OUT/log.txt" || true
}

case "$MODE" in
  clone)    do_clone; rc_set clone $? ;;
  build)    if [ "$(cat "$PCI_STATE/rc_clone" 2>/dev/null)" = "0" ]; then do_build; else say "⛔ لا مصدر — تخطّي"; fi ;;
  emu)      if [ "$(cat "$PCI_STATE/rc_clone" 2>/dev/null)" = "0" ]; then do_emu; else rc_set emu 1; fi ;;
  finalize) do_finalize ;;
  *)        say "⛔ طورٌ غيرُ معروف" ;;
esac
exit 0
