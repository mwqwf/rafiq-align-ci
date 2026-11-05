#!/usr/bin/env bash
# 📱 جولةُ الواجهة (1/2) — بناءُ APK تصحيحيٍّ من المستودع الخاصّ ورفعُه إلى R2 (دراسة المستشار 2026-11-05).
# ⟳ المراجعة 2 (2026-11-05 21:45Z): إعادةُ إطلاقٍ بإيداعٍ مباشرٍ على main — دفعةُ الدمج لم يرَ فيها agent-job السكربتين (يقارن بالأب الأوّل).
#    لماذا هنا: صندوقُ الوكيل بلا dl.google.com ولا KVM؛ وهذا العدّاءُ العامُّ مجّانيٌّ وشبكتُه مفتوحة.
#    المداخلُ التصحيحيّة (openMushaf · openTasmi …) لا تعمل إلا في بناء debug، فلا يُغني عنه APK المتجر.
#    قراءةٌ محضة للمستودع الخاصّ: لا إيداعَ فيه ولا تغييرَ إعداد. ولا يكتب في timings/ ولا catalog/.
set -uo pipefail
say(){ echo "▸ $*"; }
date +%s > /tmp/ui_walk_start          # ميزانيةُ السكربت الثاني تُحسب من هنا (الشوط كلُّه 120 د)
mkdir -p /tmp/ui_walk

[ -n "${QR_DIR:-}" ] && [ -d "$QR_DIR" ] || { echo "⛔ لا مستودعَ خاصّ (QR_DIR غائب) — لا بناء"; exit 1; }
say "المستودعُ الخاصّ: $(git -C "$QR_DIR" log -1 --format='%h %s' | cut -c1-140)"
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

say "③ البناء: :app:assembleDebug لمعماريّة المحاكي x86_64 وحدها (JDK $(java -version 2>&1 | head -1 | cut -d'"' -f2))"
cd "$QR_DIR" || exit 1
chmod +x gradlew
T0=$(date +%s)
./gradlew :app:assembleDebug -Pandroid.injected.build.abi=x86_64 --console=plain --no-daemon > /tmp/ui_walk/build.log 2>&1
RC=$?
say "زمنُ البناء $(( ($(date +%s)-T0)/60 )) د · الخروج $RC"
if [ "$RC" -ne 0 ]; then
  echo "⛔ فشل البناء — آخرُ السجلّ:"
  grep -E '^e: |error:|FAILED|What went wrong|Exception|Could not' /tmp/ui_walk/build.log | head -30
  tail -25 /tmp/ui_walk/build.log
  exit 1
fi
APK=$(find app/build/outputs/apk -name 'app-debug.apk' -o -name 'app-*-debug.apk' 2>/dev/null | head -1)
[ -n "$APK" ] && [ -s "$APK" ] || { echo "⛔ لا APK بعد بناءٍ ناجح؟"; find app/build/outputs -name '*.apk' | head; exit 1; }
cp "$APK" /tmp/ui_walk/app-debug.apk
SZ=$(stat -c %s "$APK"); SHA=$(sha256sum "$APK" | cut -c1-16)
say "APK: $APK · $((SZ/1024/1024)) م.ب · sha256 $SHA… · المصدر $QR_SHA"
grep -E 'BUILD (SUCCESSFUL|FAILED)' /tmp/ui_walk/build.log | tail -1

say "④ الرفعُ إلى R2 (tmp/ui_walk/apk/) ليُعاد استعمالُه بلا بناءٍ جديد"
[ -n "${R2_ENDPOINT:-}" ] || { echo "⚠ لا بيانةَ R2 — يبقى APK في /tmp للسكربت الثاني فقط"; exit 0; }
python3 - "$QR_SHA" "$SZ" "$SHA" <<'PY'
import boto3, json, os, sys, datetime
s3 = boto3.client("s3", endpoint_url=os.environ["R2_ENDPOINT"], aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
                  aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"], region_name="auto")
b = os.environ["R2_BUCKET"]
s3.upload_file("/tmp/ui_walk/app-debug.apk", b, "tmp/ui_walk/apk/app-debug.apk")
meta = {"qr_sha": sys.argv[1], "bytes": int(sys.argv[2]), "sha256_16": sys.argv[3],
        "built": datetime.datetime.utcnow().isoformat() + "Z", "run": os.environ.get("GITHUB_RUN_ID", "")}
s3.put_object(Bucket=b, Key="tmp/ui_walk/apk/LATEST.json", Body=json.dumps(meta, ensure_ascii=False).encode(), ContentType="application/json")
print("✅ رُفع tmp/ui_walk/apk/app-debug.apk +", json.dumps(meta, ensure_ascii=False))
PY
