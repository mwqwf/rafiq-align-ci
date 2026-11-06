#!/usr/bin/env bash
# ⛔ (v2 · D7 · 2026-11-06) لا مستودعَ خاصّاً في هذا المستودع العامّ — يخرج هنا، وبقيّةُ النصّ محفوظةٌ للمرجع.
echo "⛔ يحتاج المصدرَ الخاصّ؛ يعمل من mushafak-ci فقط"; exit 2
# 📱 جولةُ الواجهة (1/2) — بناءُ APK تصحيحيٍّ من المستودع الخاصّ ورفعُه إلى R2 (دراسة المستشار 2026-11-05).
# ⟳ المراجعة 3ب (2026-11-05 22:14Z): إيداعٌ مباشرٌ فوق main لأنّ دفعةَ الدمج لا تُظهر السكربتين لـagent-job.
# ⟳ المراجعة 3 (2026-11-05 22:10Z): الشوط 42115041851 بنى 8 دقائق بخروج 0 ولم يجد APK — أزلتُ خاصّيةَ android.injected.build.abi
#    (وصفةُ device-matrix المجرَّبة تبني بلا حقنٍ وتجد APK في app/build/outputs/apk/debug/)، وأضفتُ تشخيصاً ورفعَ سجلّ البناء إلى R2 في كلّ حال.
#    لماذا هنا: صندوقُ الوكيل بلا dl.google.com ولا KVM؛ وهذا العدّاءُ العامُّ مجّانيٌّ وشبكتُه مفتوحة.
#    المداخلُ التصحيحيّة (openMushaf · openTasmi …) لا تعمل إلا في بناء debug، فلا يُغني عنه APK المتجر.
#    قراءةٌ محضة للمستودع الخاصّ: لا إيداعَ فيه ولا تغييرَ إعداد. ولا يكتب في timings/ ولا catalog/.
set -uo pipefail
say(){ echo "▸ $*"; }
date +%s > /tmp/ui_walk_start          # ميزانيةُ السكربت الثاني تُحسب من هنا (الشوط كلُّه 120 د)
mkdir -p /tmp/ui_walk
# ⛔ 2026-11-06: مخرجاتُ الجولة (APK تصحيحيّ · سجلّ البناء · اللقطات) تُرفع إلى الدلو الخاصّ وحده؛
#    كانت تُرفع إلى الدلو العامّ rafiq-media فصار APK التطبيق قابلاً للتنزيل من r2.dev بلا مصادقة.
export UI_WALK_BUCKET="${R2_PRIVATE_BUCKET:-mushafak-private}"

[ -n "${QR_DIR:-}" ] && [ -d "$QR_DIR" ] || { echo "⛔ لا مستودعَ خاصّ (QR_DIR غائب) — لا بناء"; exit 1; }
say "المستودعُ الخاصّ: $(git -C "$QR_DIR" rev-parse --short HEAD) (البصمةُ وحدها — عنوانُ الإيداع لا يُطبع في مستودعٍ عامّ)"
QR_SHA=$(git -C "$QR_DIR" rev-parse --short HEAD)

say "① مساحةُ القرص"
sudo rm -rf /usr/share/dotnet /opt/ghc /usr/local/.ghcup /opt/hostedtoolcache/CodeQL /usr/local/share/boost 2>/dev/null || true
df -h / | tail -1

say "② whisper.cpp على المرجع المثبَّت نفسِه الذي تبني به سيورُ المستودع الخاصّ"
WHISPER_CPP_REF=c4ac0012a8f5a2082dfca6aad4ddfd8b2c02b337
WD="$QR_DIR/third_party/whisper.cpp"
if [ ! -d "$WD/.git" ]; then
  git clone -q --filter=blob:none --no-checkout https://github.com/ggml-org/whisper.cpp "$WD" || { echo "⛔ تعذّر استنساخ whisper.cpp"; exit 1; }
  git -C "$WD" fetch -q --depth 1 origin "$WHISPER_CPP_REF"
  git -C "$WD" checkout -q --detach FETCH_HEAD
fi
test "$(git -C "$WD" rev-parse HEAD)" = "$WHISPER_CPP_REF" || { echo "⛔ مرجعُ whisper.cpp مختلف"; exit 1; }
for f in CMakeLists.txt src/whisper.cpp ggml/CMakeLists.txt; do test -e "$WD/$f" || { echo "⛔ ناقص $f"; exit 1; }; done

upload_log(){ [ -n "${R2_ENDPOINT:-}" ] || return 0; python3 - <<'PY2' || true
import boto3, os
s3 = boto3.client("s3", endpoint_url=os.environ["R2_ENDPOINT"], aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
                  aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"], region_name="auto")
k = "tmp/ui_walk/%s/build.log" % os.environ.get("GITHUB_RUN_ID", "local")
s3.upload_file("/tmp/ui_walk/build.log", os.environ["UI_WALK_BUCKET"], k); print("📄 سجلُّ البناء في الدلو الخاصّ:", k)
PY2
}
say "③ البناء: :app:assembleDebug لمعماريّة المحاكي x86_64 وحدها (JDK $(java -version 2>&1 | head -1 | cut -d'"' -f2))"
cd "$QR_DIR" || exit 1
chmod +x gradlew
T0=$(date +%s)
./gradlew :app:assembleDebug --console=plain --no-daemon > /tmp/ui_walk/build.log 2>&1
RC=$?
say "زمنُ البناء $(( ($(date +%s)-T0)/60 )) د · الخروج $RC"
if [ "$RC" -ne 0 ]; then
  echo "⛔ فشل البناء — آخرُ السجلّ:"
  grep -E '^e: |error:|FAILED|What went wrong|Exception|Could not' /tmp/ui_walk/build.log | head -30
  tail -25 /tmp/ui_walk/build.log
  upload_log; exit 1
fi
grep -E 'BUILD (SUCCESSFUL|FAILED)' /tmp/ui_walk/build.log | tail -1
APK=$(find app/build/outputs/apk/debug -name '*.apk' 2>/dev/null | head -1)
[ -n "$APK" ] || APK=$(find "$QR_DIR" -name '*.apk' -not -path '*/intermediates/*' -not -path '*/androidTest/*' 2>/dev/null | head -1)
if [ -z "$APK" ] || [ ! -s "$APK" ]; then
  echo "⛔ لا APK بعد بناءٍ ناجح؟ — تشخيص:"
  ls -la app/build/outputs 2>/dev/null | head; find "$QR_DIR" -name '*.apk' 2>/dev/null | head
  echo "— آخرُ 40 سطراً من سجلّ البناء:"; tail -40 /tmp/ui_walk/build.log
  upload_log; exit 1
fi
cp "$APK" /tmp/ui_walk/app-debug.apk
SZ=$(stat -c %s "$APK"); SHA=$(sha256sum "$APK" | cut -c1-16)
say "APK: $APK · $((SZ/1024/1024)) م.ب · sha256 $SHA… · المصدر $QR_SHA"
grep -E 'BUILD (SUCCESSFUL|FAILED)' /tmp/ui_walk/build.log | tail -1

upload_log
say "④ الرفعُ إلى الدلو الخاصّ (tmp/ui_walk/apk/) ليُعاد استعمالُه بلا بناءٍ جديد"
[ -n "${R2_ENDPOINT:-}" ] || { echo "⚠ لا بيانةَ R2 — يبقى APK في /tmp للسكربت الثاني فقط"; exit 0; }
python3 - "$QR_SHA" "$SZ" "$SHA" <<'PY'
import boto3, json, os, sys, datetime
s3 = boto3.client("s3", endpoint_url=os.environ["R2_ENDPOINT"], aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
                  aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"], region_name="auto")
b = os.environ["UI_WALK_BUCKET"]
meta = {"qr_sha": sys.argv[1], "bytes": int(sys.argv[2]), "sha256_16": sys.argv[3],
        "built": datetime.datetime.utcnow().isoformat() + "Z", "run": os.environ.get("GITHUB_RUN_ID", "")}
try:
    s3.upload_file("/tmp/ui_walk/app-debug.apk", b, "tmp/ui_walk/apk/app-debug.apk")
    s3.put_object(Bucket=b, Key="tmp/ui_walk/apk/LATEST.json", Body=json.dumps(meta, ensure_ascii=False).encode(), ContentType="application/json")
    print("✅ رُفع tmp/ui_walk/apk/app-debug.apk إلى الدلو الخاصّ +", json.dumps(meta, ensure_ascii=False))
except Exception as ex:  # مفتاحُ R2 قد لا يملك الدلوَ الخاصّ — فلا يُرفع إلى العامّ أبداً، ويبقى APK في /tmp لهذا الشوط
    print("⚠ لم يُرفع APK إلى الدلو الخاصّ (" + type(ex).__name__ + ") — يبقى في /tmp لهذا الشوط فقط")
PY
