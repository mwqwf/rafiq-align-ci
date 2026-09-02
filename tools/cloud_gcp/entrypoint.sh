#!/usr/bin/env bash
# مدخل مهمة Cloud Run: يترجم متغيرات Cloud Run إلى ما تتوقعه run_shard.sh،
# ويجهّز الأسرار والنموذج، ثم يسلّم القيادة للعدة المشتركة بلا تعديل.
set -euo pipefail

ROOT=/root/QuranRafiq

# ١) التقسيم: Cloud Run يعطي TASK_INDEX/TASK_COUNT ⇒ SHARD/SHARDS بنفس
#    قاعدة run_fleet.py حرفياً (i % SHARDS == SHARD).
export SHARD="${CLOUD_RUN_TASK_INDEX:-${SHARD:-0}}"
export SHARDS="${CLOUD_RUN_TASK_COUNT:-${SHARDS:-1}}"
export JOBS="${JOBS:-8}"                 # 8 عمليات × خيط واحد على 8 vCPU
# قياس github-8e (37eea00): العمليات تغلب الخيوط — 16×1 أسرع 4.7× من 4×4،
# لأن whisper يوازي داخل الطبقة لا عبر الملفات فتتقاتل الخيوط على الأنوية.
# والمقبض موجود في العدة أصلاً فلا تعديل محرّك ولا تفريع نسخة.
export WHISPER_THREADS="${WHISPER_THREADS:-1}"
# ⛔ WHISPER_AC=0 — قرار المشرف github-f4 المحسوم بقياس 8e الثاني (997859f):
#    التعرّض 63.2% من المدخلات حدّاً أدنى صلباً (39 فهرساً · 138,050 مدخلاً)
#    والتقدير بالمقاطع 86.0% — فليس حالةً طرفية. والصقل بنوافذ 9ث يبطل أثره
#    في الجيل الثاني، و12×1 يعوّض السرعة. وشرط العدة نفسها («يبقى 512 حتى
#    يقيس 8e النطاق الفعلي») قد تحقّق بهذا القياس. ويسري على الجبهات الثلاث
#    عند حدود القارئ لا في منتصف قارئ.
export WHISPER_AC="${WHISPER_AC:-0}"
export ALIGN_REFINE=1                    # ⛔ الجيل الثاني إلزامي
export LIST="${LIST:-$ROOT/tools/ci_fleet/reciters_gcp.tsv}"

# ٢) الأسرار من Secret Manager (تُحقن كمتغيرات بيئة على المهمة).
#    upload_timings.py وstage_upload.py يقرآن secure/r2_credentials.json،
#    فنكتبه هنا بصلاحية 600 ونحذفه حتماً عند أي خروج.
mkdir -p "$ROOT/secure"
CRED="$ROOT/secure/r2_credentials.json"
cleanup() { rm -f "$CRED"; }
trap cleanup EXIT INT TERM
: "${R2_ENDPOINT:?ناقص}" "${R2_ACCESS_KEY_ID:?ناقص}" \
  "${R2_SECRET_ACCESS_KEY:?ناقص}" "${R2_BUCKET:?ناقص}"
umask 077
cat > "$CRED" <<JSON
{"endpoint":"$R2_ENDPOINT","accessKeyId":"$R2_ACCESS_KEY_ID",
 "secretAccessKey":"$R2_SECRET_ACCESS_KEY","bucket":"$R2_BUCKET",
 "publicBase":"${R2_PUBLIC_BASE:-}"}
JSON

# ٣) النموذج من دلونا لا من الشبكة العامة — مع تحقق الحجم.
MODEL="$ROOT/assets-archive/ggml/ggml-tiny-ar-quran-q8_0.bin"
if [ ! -s "$MODEL" ]; then
  echo "… تنزيل النموذج من R2"
  "$ROOT/.venv/bin/python" - <<PY
import json, os, boto3
c = json.load(open("$CRED"))
s3 = boto3.client("s3", endpoint_url=c["endpoint"],
                  aws_access_key_id=c["accessKeyId"],
                  aws_secret_access_key=c["secretAccessKey"], region_name="auto")
key = os.environ.get("MODEL_KEY", "models/whisper-tiny-ar-quran/ggml-q8_0.bin")
head = s3.head_object(Bucket=c["bucket"], Key=key)
s3.download_file(c["bucket"], key, "$MODEL")
got = os.path.getsize("$MODEL")
assert got == head["ContentLength"], f"حجم النموذج {got} ≠ {head['ContentLength']}"
print("✅ النموذج", got, "بايت")
PY
fi

# ٤) حارس b9: مهمةٌ خارج المدى تعمل صامتةً بلا عمل — تُوقف عند الإقلاع.
if ! [ "$SHARD" -ge 0 ] 2>/dev/null || [ "$SHARD" -ge "$SHARDS" ]; then
  echo "⛔ تقسيم غير صالح: SHARD=$SHARD SHARDS=$SHARDS"; exit 1
fi

# ٥) ⛔ أهمّ قرار في التصميم (تحذير b9): `batch_run` لا يعيد سورةً لها json،
#    فمجلد العمل على قرص المهمة المؤقت يعني أن كل مهمة تسقط تبدأ من الصفر.
#    فيُوصل `work` بحجم Cloud Storage مركّب على /mnt/work (انظر deploy.sh).
if [ -d /mnt/work ]; then
  mkdir -p /mnt/work/alignment
  rm -rf "$ROOT/tools/alignment/work"
  ln -s /mnt/work/alignment "$ROOT/tools/alignment/work"
  echo "✅ مجلد العمل باقٍ على /mnt/work (الاستئناف مضمون)"
else
  echo "⚠️ لا حجم دائم — الاستئناف معطّل وكل سقوط يبدأ من الصفر"
fi

# ٦) ⛔ لا تحديث للمانيفست من المهام إطلاقاً (تحذير b9: عشرون كاتباً
#    متوازياً على read-modify-write تضيع صفوفاً بلا خطأ ظاهر). run_shard.sh
#    يستدعي stage_upload.py وهو يكتب في timings-staging/ ولا يمسّ مانيفستاً.
echo "شريحة $SHARD/$SHARDS · JOBS=$JOBS · القائمة $LIST"
exec bash "$ROOT/tools/ci_fleet/run_shard.sh"
