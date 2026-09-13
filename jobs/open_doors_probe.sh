#!/usr/bin/env bash
# 🚪 يفحص الأبوابَ الأربعةَ التي قال الوكيلُ السحابيُّ إنّها مغلقةٌ عليه — هنا، على العدّاء.
# ⛔ ولا يُحكم بفتحها حتى يُطبع رمزُ كلِّ بابٍ برقمه.
set -u

echo "== الأبوابُ التي تعذّرت في صندوق الوكيل — تُجرَّب هنا =="
echo

door() {
  printf '%-42s ' "$1"; shift
  code=$("$@" 2>/dev/null || echo 000)
  if [ "$code" = "200" ] || [ "$code" = "206" ]; then echo "✅ $code"; else echo "⛔ $code"; fi
}

door "dl.google.com (عتادُ gradle)" \
  curl -sS -o /dev/null -w '%{http_code}' -r 0-1 \
  "https://dl.google.com/dl/android/maven2/com/android/tools/build/gradle/8.5.0/gradle-8.5.0.pom"

door "r2.dev — النموذجُ المشحون" \
  curl -sS -o /dev/null -w '%{http_code}' -r 0-1 -A "Mozilla/5.0 (agent job)" \
  "https://pub-2c2e1dcd92e84a2898820dd38d3e09e6.r2.dev/models/whisper-tiny-ar-quran/ggml-q8_0.bin"

door "r2.dev — النموذجُ الأكبر" \
  curl -sS -o /dev/null -w '%{http_code}' -r 0-1 -A "Mozilla/5.0 (agent job)" \
  "https://pub-2c2e1dcd92e84a2898820dd38d3e09e6.r2.dev/models/whisper-base-ar-quran/ggml-q8_0.bin"

door "api.github.com" \
  curl -sS -o /dev/null -w '%{http_code}' \
  "https://api.github.com/repos/mwqwf/rafiq-align-ci"

door "huggingface.co (المرآةُ البايثونيّة)" \
  curl -sS -o /dev/null -w '%{http_code}' \
  "https://huggingface.co/tarteel-ai/whisper-tiny-ar-quran/resolve/main/config.json"

echo
echo "== العدّة =="
printf '%-42s %s\n' "python3" "$(python3 -V 2>&1)"
printf '%-42s %s\n' "java"    "$(java -version 2>&1 | head -1)"
printf '%-42s %s\n' "ffmpeg"  "$(ffmpeg -version 2>/dev/null | head -1 | cut -d' ' -f1-3)"
printf '%-42s %s\n' "بيانةُ R2" "${R2_BUCKET:+موجودة}${R2_BUCKET:-غائبة}"
printf '%-42s %s\n' "المستودعُ الخاصّ" "${QR_DIR:-غائب — لا مفتاح QR_READ_TOKEN}"

echo
if [ -n "${QR_DIR:-}" ]; then
  echo "== اختباراتُ المحرك (‏الباب الرابع) =="
  cd "$QR_DIR" || exit 0
  chmod +x gradlew
  ./gradlew :engine:recitation:test --console=plain -q 2>&1 | tail -25
  echo "رمزُ الخروج: ${PIPESTATUS[0]}"
  python3 - <<'PY'
import glob, xml.etree.ElementTree as ET
ps = glob.glob('engine/recitation/build/test-results/**/*.xml', recursive=True)
t = f = e = 0
for p in ps:
    r = ET.parse(p).getroot()
    t += int(r.get('tests', 0)); f += int(r.get('failures', 0)); e += int(r.get('errors', 0))
print(len(ps), "أصنافٍ ·", t, "اختباراً · إخفاقات", f, "· أعطاب", e)
PY
else
  echo "== اختباراتُ المحرك: مؤجَّلة =="
  echo "⛔ تحتاج السرَّ QR_READ_TOKEN في هذا المستودع (‏مفتاحُ قراءةٍ على QuranRafiq)."
  echo "   وما عداها مفتوحٌ كما فوق."
fi
