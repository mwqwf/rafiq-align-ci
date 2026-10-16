#!/usr/bin/env bash
# سكربت بدء تشغيل جهاز GCE (L4) لاستئناف شوط «مصحفك-1» الذي كان يجري على Kaggle.
# يُمرَّر عبر metadata الجهاز (startup-script) ويُعاد تشغيله عند كل إقلاع (ومنه إقلاعُ ما بعد قطع الجهاز المتقطّع).
# ما يشغّله هو الأمرُ نفسُه الذي يشغّله دفترُ Kaggle (cloud_run.py --local-state …) بوسائطه نفسِها.
# إعداداتُه من metadata: kaggle-token (رمز Kaggle الجديد KGAT) · resume-kernel · expect-step · max-hours · bucket
# واختياريّاً: workers · data-tag · parts · grade · mirror-kernels · data-datasets · code-dataset.
# ⛔ لا يطبع المفتاحَ في أيّ سجلّ (لا set -x ولا echo له).
set -euo pipefail

BASE=/var/lib/mushafak1
CODE=/opt/mushafak1/code
IN=$BASE/input
WORK=$BASE/work
STATE=$BASE/state
LOG=/var/log/mushafak1.log
mkdir -p "$BASE" "$IN" "$WORK" "$STATE" /opt/mushafak1
exec > >(tee -a "$LOG") 2>&1

BOOT=$(date +%s)
say() { echo "$(date -u +%FT%TZ) $*"; }

# ── الإعدادات من metadata ──
MD=http://metadata.google.internal/computeMetadata/v1/instance
md()     { curl -fsS -H 'Metadata-Flavor: Google' "$MD/attributes/$1"; }
md_opt() { curl -fsS -H 'Metadata-Flavor: Google' "$MD/attributes/$1" 2>/dev/null || echo "$2"; }

BUCKET=$(md bucket)
INSTANCE=$(curl -fsS -H 'Metadata-Flavor: Google' "$MD/name")
ZONE=$(curl -fsS -H 'Metadata-Flavor: Google' "$MD/zone" | awk -F/ '{print $NF}')
RESUME_KERNEL=$(md_opt resume-kernel cloudenarymarwano/mushafak1-m1-b)
EXPECT_STEP=$(md expect-step)
MAX_HOURS=$(md max-hours)
WORKERS=$(md_opt workers 4)
DATA_TAG=$(md_opt data-tag d2)
PARTS=$(md_opt parts 17)
GRADE=$(md_opt grade m1)
MIRRORS=$(md_opt mirror-kernels cloudenarymarwano/mushafak1-d1-a,cloudenarymarwano/mushafak1-d1-b)
DATASETS=$(md_opt data-datasets cloudenarymarwano/mushafak1-d2-delta)
CODE_DS=$(md_opt code-dataset cloudenarymarwano/mushafak1-code)
KAGGLE_API_TOKEN=$(md kaggle-token)
export KAGGLE_API_TOKEN
[[ "$EXPECT_STEP" =~ ^[0-9]+$ ]] || { say "⛔ expect-step غير رقميّ"; exit 2; }
[[ "$MAX_HOURS" =~ ^[0-9]+([.][0-9]+)?$ ]] || { say "⛔ max-hours غير رقميّ"; exit 2; }

GS=gs://$BUCKET/m1
CK=$STATE/ckpt/$GRADE
PHASE_NOTE="starting"
SYNC_OK=1
START_STEP=-1
SRC=""

# ── العدّادُ التراكميّ لساعات التشغيل (يبقى عبر قطعِ الجهاز المتقطّع) ──
USED0=0
[ -f "$BASE/used_s" ] && USED0=$(cat "$BASE/used_s")
BU=$(gcloud storage cat "$GS/used_s" 2>/dev/null || echo 0)
[[ "$BU" =~ ^[0-9]+$ ]] || BU=0
(( BU > USED0 )) && USED0=$BU
BUDGET_S=$(awk -v h="$MAX_HOURS" 'BEGIN{printf "%d", h*3600}')
used_now() { echo $(( USED0 + $(date +%s) - BOOT )); }
save_used() { used_now > "$BASE/used_s"; gcloud storage cp -q "$BASE/used_s" "$GS/used_s" || true; }

# ── المهلةُ الصلبة: تُطفئ الجهازَ مهما علق شيء (تنزيلٌ أو تدريب) ──
DEADLINE=$(( BOOT + BUDGET_S - USED0 + 2700 ))
( while [ "$(date +%s)" -lt "$DEADLINE" ]; do sleep 60; done
  echo "$(date -u +%FT%TZ) ⛔ WATCHDOG: انتهت الميزانيّة ⇒ إطفاءٌ قسريّ"; sync; shutdown -h now ) &
WATCHDOG=$!

# ── الخروجُ: نشرُ الحالة ومزامنةٌ أخيرة ثمّ الإطفاءُ دائماً ──
RC=0; TRAIN_RC=-1
finish() {
  RC=$?
  trap - EXIT
  [ -n "${SYNCER:-}" ] && kill "$SYNCER" 2>/dev/null || true
  say "finish rc=$RC train_rc=$TRAIN_RC"
  save_used || true
  if ! sync_state; then SYNC_OK=0; say "⛔ المزامنة الأخيرة أخفقت — الحالةُ باقيةٌ على قرص الجهاز"; fi
  publish_status "$([ "$RC" -eq 0 ] && echo finished || echo failed)" || say "⚠ نشر الحالة أخفق"
  # علامةُ «انتهى» تُكتب عند النجاح وحده؛ الإخفاقُ يُستأنف بإعادة تشغيل الجهاز
  [ "$RC" -eq 0 ] && touch "$BASE/finished"
  gcloud storage cp -q "$LOG" "$GS/startup.log" || true
  sync
  kill "$WATCHDOG" 2>/dev/null || true
  shutdown -h now
}
trap finish EXIT

# ── أدوات ──
pick_python() {
  for p in /opt/conda/bin/python python3; do
    if command -v "$p" >/dev/null && "$p" -c "import torch" 2>/dev/null; then command -v "$p"; return 0; fi
  done
  return 1
}
PY=$(pick_python) || { say "⛔ لا python فيه torch على هذه الصورة"; exit 3; }
export PATH="$(dirname "$PY"):$PATH"

step_of() {   # خطوةُ نقطةٍ، أو -1 إن غابت أو تعذّرت قراءتها
  [ -f "$1" ] || { echo -1; return 0; }
  "$PY" - "$1" <<'PYEOF' || echo -1
import sys, torch
try:
    print(int(torch.load(sys.argv[1], map_location="cpu", weights_only=False, mmap=True).get("step", -1)))
except Exception as e:
    print("⚠ تعذّرت قراءة", sys.argv[1], e, file=sys.stderr); print(-1)
PYEOF
}

sync_state() {
  gcloud storage rsync -r --no-user-output-enabled --exclude='.*\.tmp$' "$STATE" "$GS/state"
}

publish_status() {   # $1 = مرحلة السكربت
  local tmp="$BASE/status_pub.json"
  "$PY" - "$CK" "$1" "$RC" "$TRAIN_RC" "$SYNC_OK" "$START_STEP" "$SRC" "$INSTANCE" "$(used_now)" "$GRADE" > "$tmp" <<'PYEOF'
import sys, json, re, os, time
ck, stage, rc, trc, sync_ok, start_step, src, inst, used, grade = sys.argv[1:11]
st = {}
try: st = json.load(open(os.path.join(ck, "status.json")))
except Exception: pass
def step_line(s):
    m = re.search(r"(?:STEP|DONE step) (\d+)", s or "")
    return int(m.group(1)) if m else None
per = None
ev = st.get("last_eval") or ""
if "PER " in ev:
    try: per = json.JSONDecoder().raw_decode(ev[ev.index("PER ") + 4:])[0]
    except Exception: pass
ckstep = None
try:
    import torch
    p = os.path.join(ck, "last.pt")
    if os.path.exists(p):
        ckstep = int(torch.load(p, map_location="cpu", weights_only=False, mmap=True).get("step", -1))
except Exception: pass
print(json.dumps({
    "platform": "gce", "instance": inst, "grade": grade, "stage": stage,
    "phase": st.get("phase"), "last_step": step_line(st.get("last_step")), "ckpt_step": ckstep,
    "per": per, "start_step": int(start_step), "resumed_from": src,
    "script_rc": int(rc), "train_rc": int(trc), "sync_ok": sync_ok == "1",
    "used_hours": round(int(used) / 3600, 2), "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}, ensure_ascii=False, indent=1))
PYEOF
  gcloud storage cp -q "$tmp" "$GS/status.json"
}

# ── مرحلةٌ: ميزانيّةٌ باقية؟ ──
if [ -f "$BASE/finished" ] && [ ! -f "$BASE/force_run" ]; then
  say "انتهى شوطٌ سابقٌ على هذا الجهاز (علامة finished) — لا تدريب؛ احذف الجهاز وأعد الإطلاق من السير لشوطٍ جديد"
  exit 0
fi
REM_S=$(( BUDGET_S - USED0 ))
if (( REM_S < 1200 )); then say "الميزانيّةُ استُهلكت ($USED0 من $BUDGET_S ث) — لا تدريب"; exit 0; fi
say "بدء: kernel=$RESUME_KERNEL expect>=$EXPECT_STEP budget_left=${REM_S}s instance=$INSTANCE zone=$ZONE"

# ── GPU ──
for i in $(seq 1 90); do nvidia-smi -L >/dev/null 2>&1 && break; [ "$i" = 90 ] && { say "⛔ nvidia-smi لا يعمل بعد 15 د"; exit 4; }; sleep 10; done
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader

# ── الحزم (مثلُ دفتر Kaggle + ما تستورده الشيفرة) ──
if [ ! -f "$BASE/.pip_ok" ]; then
  "$PY" -m pip install -q 'kaggle>=1.8' soundfile boto3 onnx onnxruntime kaldi-native-fbank pyarrow requests cryptography
  touch "$BASE/.pip_ok"
fi

# ── الشيفرة من مجموعة Kaggle (مرّةً واحدة؛ إعادةُ الإقلاع تستعمل النسخة نفسَها) ──
if [ ! -f "$CODE/tools/tasmi_model/cloud_run.py" ]; then
  rm -rf "$CODE.tmp"; mkdir -p "$CODE.tmp"
  kaggle datasets download -d "$CODE_DS" --unzip -p "$CODE.tmp"
  [ -f "$CODE.tmp/code.zip" ] && (cd "$CODE.tmp" && "$PY" -m zipfile -e code.zip . && rm code.zip)
  [ -f "$CODE.tmp/tools/tasmi_model/cloud_run.py" ] || { say "⛔ مجموعة الشيفرة بلا cloud_run.py"; exit 5; }
  rm -rf "$CODE"; mv "$CODE.tmp" "$CODE"
fi
FP=$("$PY" - "$CODE/tools/tasmi_model" <<'PYEOF'
import hashlib, sys, os
h = hashlib.sha1()
for f in ("cloud_run.py", "train.py", "data.py", "model.py"):
    h.update(open(os.path.join(sys.argv[1], f), "rb").read())
print(h.hexdigest()[:10])
PYEOF
)
say "CODE $FP"

# ── تنزيلُ مخرَج دفترٍ مع التحقّق من أحجام الأجزاء (يُعاد حتى 3 مرّات) ──
dl_kernel() {   # $1 = owner/slug
  local slug=${1##*/} d="$IN/${1##*/}" n
  [ -f "$d/.ok" ] && return 0
  for n in 1 2 3; do
    say "تنزيل مخرَج $1 (محاولة $n)"
    if kaggle kernels output "$1" -p "$d"; then
      if "$PY" - "$d" <<'PYEOF'
import sys, os, json, glob
bad = []
for j in glob.glob(os.path.join(sys.argv[1], "part_*.json")):
    t = j[:-5] + ".tar"
    if os.path.exists(t):
        try: want = json.load(open(j)).get("bytes")
        except Exception: want = None
        if want and os.path.getsize(t) != want: bad.append(t)
for t in bad: os.remove(t); print("حجمٌ مخالف:", t)
sys.exit(1 if bad else 0)
PYEOF
      then touch "$d/.ok"; return 0; fi
    fi
  done
  say "⛔ تعذّر تنزيل $1 سليماً"; return 1
}

# ── اختيارُ نقطة الاستئناف: الأكبرُ خطوةً بين مخرَج Kaggle وحالةِ الجهاز المحليّة وحالةِ الدلو ──
dl_kernel "$RESUME_KERNEL"
KDIR="$IN/${RESUME_KERNEL##*/}/state/ckpt/$GRADE"
KSTEP=$(step_of "$KDIR/last.pt")
LSTEP=$(step_of "$CK/last.pt")
BSTEP=-1
if gcloud storage ls "$GS/state/ckpt/$GRADE/last.pt" >/dev/null 2>&1; then
  mkdir -p "$BASE/bucket_probe"
  gcloud storage cp -q "$GS/state/ckpt/$GRADE/last.pt" "$BASE/bucket_probe/last.pt"
  BSTEP=$(step_of "$BASE/bucket_probe/last.pt"); rm -rf "$BASE/bucket_probe"
fi
say "خطوات: kaggle=$KSTEP محلي=$LSTEP دلو=$BSTEP (المطلوب ≥ $EXPECT_STEP)"
BEST=$KSTEP; SRC="kaggle:$RESUME_KERNEL"
(( LSTEP > BEST )) && { BEST=$LSTEP; SRC="local"; }
if (( BSTEP > BEST )); then
  say "الدلو أحدثُ ($BSTEP) ⇒ يُستعاد إلى $STATE"
  mkdir -p "$STATE"
  gcloud storage rsync -r --no-user-output-enabled "$GS/state" "$STATE"
  BEST=$BSTEP; SRC="bucket:$GS"
fi
START_STEP=$BEST
if (( BEST < EXPECT_STEP )); then
  say "⛔ أحدثُ نقطةٍ ($BEST) دون المتوقَّع ($EXPECT_STEP) — لا يبدأ الاستئنافُ من الصفر ولا من نقطةٍ أقدم"
  exit 6
fi

# ── البيانات: نسخُ أجزاء d1 (دفتران) وحزمةُ الدلتا ──
IFS=',' read -ra MIR <<< "$MIRRORS"
for m in "${MIR[@]}"; do dl_kernel "$m"; done
IFS=',' read -ra DSS <<< "$DATASETS"
for d in "${DSS[@]}"; do
  dd="$IN/${d##*/}"
  if [ ! -f "$dd/.ok" ]; then rm -rf "$dd"; mkdir -p "$dd"; kaggle datasets download -d "$d" --unzip -p "$dd"; touch "$dd/.ok"; fi
done
df -h "$BASE" | tail -1

# ── مزامنةٌ دوريّة كلَّ 5 دقائق في الخلفيّة (لا تُسقط الشوطَ إن أخفقت مرّة؛ تُسجَّل وتُنشر في الحالة) ──
( while true; do
    sleep 300
    save_used || true
    if sync_state; then SYNC_OK=1; else SYNC_OK=0; say "⚠ مزامنة الدلو أخفقت"; fi
    publish_status running || true
  done ) &
SYNCER=$!
publish_status running || true

# ── الشوط: الأمرُ نفسُه الذي في الدفتر (الحالةُ محليّة؛ بلا R2 ولا حزمة روابط) ──
REM_H=$(awk -v s="$(( BUDGET_S - $(used_now) ))" 'BEGIN{printf "%.3f", s/3600}')
say "تشغيل cloud_run: max-hours=$REM_H workers=$WORKERS data=$DATA_TAG parts=$PARTS"
set +e
( cd "$CODE" && env -u R2_ACCESS_KEY_ID -u R2_SECRET_ACCESS_KEY -u KAGGLE_API_TOKEN M1_PLATFORM=gce \
    "$PY" -u tools/tasmi_model/cloud_run.py --grade "$GRADE" --work "$WORK" --local-state "$STATE" --inputs "$IN" \
    --max-hours "$REM_H" --workers "$WORKERS" --stall-minutes 20 --data-tag "$DATA_TAG" --parts "$PARTS" \
    --expect-step "$EXPECT_STEP" )
TRAIN_RC=$?
set -e
say "cloud_run rc=$TRAIN_RC"
# الرمزُ غيرُ الصفريّ يمرّ إلى finish (حالة failed) — لا يُبتلع
exit "$TRAIN_RC"
