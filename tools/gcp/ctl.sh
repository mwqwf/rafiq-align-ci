#!/usr/bin/env bash
# مُتحكِّم حملة تدريب «مصحفك-1»: launch · status · export · teardown · watch
# المسارُ الافتراضيّ Vertex AI CustomJob (BACKEND=vertex)؛ ومسارُ GCE باقٍ كما كان (BACKEND=gce).
# يعمل في سير gcp_train بعد المصادقة (OIDC). المتغيّرات من السير: PROJECT_ID ZONE INSTANCE BUCKET BACKEND REGION
# ⛔ لا يطبع روابطَ موقّعة ولا مفاتيح؛ أعدادٌ وأرقامٌ فقط.
set -euo pipefail

: "${PROJECT_ID:?}" "${ZONE:?}" "${INSTANCE:?}"
BUCKET=${BUCKET:-${PROJECT_ID}-mushafak1}
REGION=${REGION:-us-central1}
# صورة PyTorch GPU الجاهزة في Vertex: أحدث وسمٍ موثّقٍ ومنشور (2.4 · py310 · CUDA 12.x) — يُتحقَّق منه بسجلّ us-docker.pkg.dev
VERTEX_IMAGE=${VERTEX_IMAGE:-us-docker.pkg.dev/vertex-ai/training/pytorch-gpu.2-4.py310:latest}
SA_EMAIL=mushafak-ci@${PROJECT_ID}.iam.gserviceaccount.com
VERTEX_MACHINE=${VERTEX_MACHINE:-g2-standard-24}
GSB=gs://$BUCKET
TMP=${RUNNER_TEMP:-/tmp}
HERE=$(cd "$(dirname "$0")" && pwd)
gc() { gcloud --project "$PROJECT_ID" "$@"; }
err() { echo "::error::$*"; }

inst_status() { gc compute instances list --filter="name=$INSTANCE" --format='value(status)' 2>/dev/null | head -1; }
bucket_exists() { gc storage buckets describe "$GSB" >/dev/null 2>&1; }
gs_has() { gcloud storage ls "$1" >/dev/null 2>&1; }
gs_json() { gcloud storage cat "$1" 2>/dev/null || echo '{}'; }
jget() { python3 -c 'import json,sys;d=json.load(sys.stdin);print(d.get(sys.argv[1],sys.argv[2]))' "$1" "${2:-0}"; }
cost_of() { awk -v s="$1" -v r="$2" 'BEGIN{printf "%.2f", s*r/3600}'; }

ledger_cost() {   # يطبع: ثوانٍ كلفة سقف
  local c s r b
  c=$(gs_json "$GSB/campaign.json"); s=$(gs_json "$GSB/ledger.json" | jget seconds 0)
  r=$(echo "$c" | jget rate_usd_per_hour 0); b=$(echo "$c" | jget budget_usd 0)
  echo "$s $(cost_of "$s" "$r") $b"
}

default_rate() {   # سعر us-central1 لـg2-standard-24 (2026-07): عند الطلب 2.0008 · spot ≈1.5702 (تتبّعٌ خارجيّ)؛ الافتراضيّ ×1.15 هامشاً
  if [ "$SPOT" = "true" ]; then echo 1.81; else echo 2.01; fi
}

do_export() {
  bucket_exists || { echo "لا دلو — لا تصدير"; return 0; }
  gs_has "$GSB/m1/last.pt" || { echo "لا last.pt في الدلو — لا تصدير"; return 0; }
  local d="$TMP/export"; rm -rf "$d"; mkdir -p "$d"
  for f in last.pt best.pt run.json status.json; do gcloud storage cp -q "$GSB/m1/$f" "$d/$f" 2>/dev/null || true; done
  local step
  step=$(gs_json "$GSB/vm_status.json" | jget ckpt_step "")
  if [ -z "$step" ] || [ "$step" = None ]; then step=$(python3 - "$d/status.json" <<'PYEOF'
import json, re, sys
try: m = re.search(r"(?:STEP|DONE step) (\d+)", json.load(open(sys.argv[1])).get("last_step") or "")
except Exception: m = None
print(m.group(1) if m else "")
PYEOF
); fi
  [ -n "$step" ] || step="u$(date -u +%Y%m%dT%H%M%S)"
  pip install -q boto3
  python3 "$HERE/r2_stage.py" export --dir "$d" --out-prefix "models/mushafak1/stage-out/$step"
  echo "stage-out step=$step (حدٌّ أدنى للخطوة الفعلية؛ استعمله في --expect-step)"
  rm -rf "$d"
}

gce_launch() {
  [[ "${EXPECT_STEP:-}" =~ ^[0-9]+$ ]] || { err "expect_step مطلوب ورقميّ"; exit 1; }
  [[ "$ZONE" =~ ^[a-z]+-[a-z]+[0-9]+-[a-z]$ ]] || { err "zone غير صالحة"; exit 1; }
  [[ "$MACHINE_TYPE" =~ ^g2-standard-[0-9]+$ ]] || { err "machine_type من عائلة g2-standard"; exit 1; }
  [[ "$BUDGET_USD" =~ ^[0-9]+([.][0-9]+)?$ ]] || { err "budget_usd غير رقميّ"; exit 1; }
  local rate=${RATE_USD_PER_HOUR:-}; [ -n "$rate" ] || rate=$(default_rate)
  [[ "$rate" =~ ^[0-9]+([.][0-9]+)?$ ]] || { err "rate غير رقميّ"; exit 1; }
  [ -z "$(inst_status)" ] || { err "الجهاز $INSTANCE قائمٌ ($(inst_status)) — لا جهازَ ثانياً"; exit 1; }
  if bucket_exists; then
    read -r s c _ <<< "$(ledger_cost)"
    # السقفُ الجديد يُقارَن بالكلفة التراكميّة بالسعر المطلوب الآن
    c=$(cost_of "$s" "$rate")
    awk -v c="$c" -v b="$BUDGET_USD" 'BEGIN{exit !(c>=b)}' && { err "الدفترُ بلغ السقف (\$$c من \$$BUDGET_USD)"; exit 1; }
    echo "ledger: seconds=$s cost=\$$c"
  else
    gc storage buckets create "$GSB" --location=us-central1 --uniform-bucket-level-access
  fi
  pip install -q boto3
  python3 "$HERE/r2_stage.py" urls --out "$TMP/stage_urls.json" --expect-step "$EXPECT_STEP"
  local fam
  fam=$(gc compute images list --project deeplearning-platform-release --no-standard-images \
    --filter='family~"^pytorch-[0-9-]+-cu12[0-9]*-ubuntu-[0-9]+-nvidia-[0-9]+$" AND NOT deprecated.state:*' \
    --sort-by=~creationTimestamp --limit=1 --format='value(family)')
  [ -n "$fam" ] || { err "لا عائلةَ صورة pytorch+cu12 مناسبة"; exit 1; }
  echo "الصورة: $fam"
  local prov=STANDARD; [ "$SPOT" = "true" ] && prov=SPOT
  local secs; secs=$(awk -v b="$BUDGET_USD" -v r="$rate" 'BEGIN{printf "%d", (b/r+1)*3600}')
  python3 - "$rate" "$BUDGET_USD" "$MACHINE_TYPE" "$prov" > "$TMP/campaign.json" <<'PYEOF'
import json, sys, time
print(json.dumps({"rate_usd_per_hour": float(sys.argv[1]), "budget_usd": float(sys.argv[2]), "machine_type": sys.argv[3],
                  "provisioning": sys.argv[4], "launched": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}))
PYEOF
  gcloud storage cp -q "$TMP/campaign.json" "$GSB/campaign.json"
  gcloud storage rm -q "$GSB/done" "$GSB/stop_request" "$GSB/fails" 2>/dev/null || true
  gc compute instances create "$INSTANCE" --zone "$ZONE" --machine-type "$MACHINE_TYPE" \
    --image-family "$fam" --image-project deeplearning-platform-release \
    --boot-disk-size 200GB --boot-disk-type pd-balanced --boot-disk-auto-delete \
    --maintenance-policy TERMINATE --no-restart-on-failure \
    --provisioning-model "$prov" --instance-termination-action STOP \
    --max-run-duration "${secs}s" \
    --service-account "mushafak-ci@${PROJECT_ID}.iam.gserviceaccount.com" --scopes cloud-platform \
    --labels app=mushafak1 \
    --metadata "install-nvidia-driver=True,bucket=${BUCKET},expect-step=${EXPECT_STEP},rate=${rate},budget-usd=${BUDGET_USD},workers=10" \
    --metadata-from-file "startup-script=$HERE/train_startup.sh,stage-urls=$TMP/stage_urls.json" >/dev/null
  rm -f "$TMP/stage_urls.json"
  echo on > "$TMP/active"; gcloud storage cp -q "$TMP/active" "$GSB/active"
  echo "أُطلق $INSTANCE ($MACHINE_TYPE $prov) · rate=\$$rate/h · budget=\$$BUDGET_USD · max_run=${secs}s"
}

gce_status() {
  local st; st=$(inst_status); echo "instance_status=${st:-NONE}"
  bucket_exists || { echo "bucket=none"; return 0; }
  echo "active=$(gs_has "$GSB/active" && echo 1 || echo 0) done=$(gs_has "$GSB/done" && echo "$(gcloud storage cat "$GSB/done")" || echo 0)"
  read -r s c b <<< "$(ledger_cost)"
  echo "ledger_seconds=$s hours=$(awk -v s="$s" 'BEGIN{printf "%.2f", s/3600}') cost_usd=$c budget_usd=$b"
  gs_json "$GSB/vm_status.json" | python3 -c '
import json, sys
d = json.load(sys.stdin)
for k in ("stage", "phase", "last_step", "ckpt_step", "start_step", "resumed_from", "train_rc", "sync_ok", "torch", "updated"):
    if k in d: print(f"vm.{k}={d[k]}")'
}

cmd_export() { do_export; }

count_zero() {   # $1 اسم $2.. الأمر ⇒ يطبع العدد؛ واجهةٌ معطّلة تُحسب صفراً
  local name=$1 out; shift
  if out=$("$@" 2>&1); then
    echo "$name=$(printf '%s' "$out" | grep -c . || true)"
  elif echo "$out" | grep -qiE "has not been used|is disabled|API .* not enabled|SERVICE_DISABLED|PERMISSION_DENIED.*disabled"; then
    echo "$name=0"
  else echo "$name=ERR"; fi
}

cmd_teardown() {
  if bucket_exists; then
    if [ "$(inst_status)" = RUNNING ] || [ -n "$(v_active_ids)" ]; then
      echo on > "$TMP/sr"; gcloud storage cp -q "$TMP/sr" "$GSB/stop_request"
      echo "طُلب من الجهاز/المهمة مزامنةٌ أخيرة وإيقاف؛ انتظارٌ حتى 14 د"
      for _ in $(seq 1 28); do [ "$(inst_status)" = RUNNING ] || [ -n "$(v_active_ids)" ] || break; sleep 30; done
    fi
    v_cancel_active
    do_export
  else
    v_cancel_active
  fi
  gc compute instances list --format='value(name,zone.basename())' | while read -r n z; do
    [ -n "$n" ] && gc compute instances delete "$n" --zone "$z" --quiet --delete-disks=all >/dev/null
  done
  gc compute disks list --format='value(name,zone.basename())' | while read -r n z; do
    [ -n "$n" ] && gc compute disks delete "$n" --zone "$z" --quiet
  done
  gc compute snapshots list --format='value(name)' | while read -r n; do [ -n "$n" ] && gc compute snapshots delete "$n" --quiet; done
  gc compute images list --no-standard-images --format='value(name)' | while read -r n; do [ -n "$n" ] && gc compute images delete "$n" --quiet; done
  gc compute addresses list --filter='region:*' --format='value(name,region.basename())' | while read -r n r; do
    [ -n "$n" ] && gc compute addresses delete "$n" --region "$r" --quiet
  done
  gc compute addresses list --global --format='value(name)' | while read -r n; do [ -n "$n" ] && gc compute addresses delete "$n" --global --quiet; done
  bucket_exists && gcloud storage rm -r -q "$GSB"
  echo "── جرد ما يكلّف (يجب أن يكون كلُّه صفراً) ──"
  local bad=0 line
  {
    count_zero vertex_active_jobs v_nonterminal_lines
    count_zero vertex_endpoints gc ai endpoints list --region "$REGION" --format='value(name)'
    count_zero vertex_models gc ai models list --region "$REGION" --format='value(name)'
    count_zero instances gc compute instances list --format='value(name)'
    count_zero disks gc compute disks list --format='value(name)'
    count_zero snapshots gc compute snapshots list --format='value(name)'
    count_zero images gc compute images list --no-standard-images --format='value(name)'
    count_zero addresses gc compute addresses list --format='value(name)'
    count_zero buckets gc storage buckets list --format='value(name)'
    count_zero artifact_repos gc artifacts repositories list --format='value(name)'
    count_zero secrets gc secrets list --format='value(name)'
    count_zero scheduler_jobs bash -c 'for l in $(gcloud --project "$0" scheduler locations list --format="value(locationId)"); do gcloud --project "$0" scheduler jobs list --location "$l" --format="value(name)"; done' "$PROJECT_ID"
  } | while read -r line; do echo "$line"; done | tee "$TMP/inventory.txt"
  if grep -qvE '=0$' "$TMP/inventory.txt"; then err "الجردُ فيه غيرُ الصفر أو خطأ"; exit 1; fi
  echo "الجردُ كلُّه صفر"
}

gce_watch() {
  bucket_exists || { echo "لا دلو ⇒ لا حملة"; return 0; }
  gs_has "$GSB/active" || { echo "لا حملة فعّالة"; return 0; }
  local st; st=$(inst_status); st=${st:-NONE}
  read -r s c b <<< "$(ledger_cost)"
  local fin=0 over=0
  gs_has "$GSB/done" && fin=1
  awk -v c="$c" -v b="$b" 'BEGIN{exit !(b>0 && c>=b)}' && over=1
  echo "status=$st cost=\$$c budget=\$$b done=$fin over=$over"
  if [ "$fin" = 1 ] || [ "$over" = 1 ]; then
    case "$st" in
      NONE) ;;
      RUNNING|STAGING|PROVISIONING)
        # الجهازُ يوقف نفسَه عند السقف؛ نحذفه قسراً فقط إن تجاوز السقفَ بهامش 5%
        if awk -v c="$c" -v b="$b" 'BEGIN{exit !(c>=b*1.05)}' || [ "$fin" = 1 ]; then
          echo "حذفٌ قسريّ"; gc compute instances delete "$INSTANCE" --zone "$ZONE" --quiet --delete-disks=all >/dev/null
        fi ;;
      *) gc compute instances delete "$INSTANCE" --zone "$ZONE" --quiet --delete-disks=all >/dev/null; echo "حُذف الجهاز" ;;
    esac
    [ -n "$(inst_status)" ] && [ "$(inst_status)" != RUNNING ] && { err "الجهاز ما زال قائماً"; exit 1; }
    gcloud storage rm -q "$GSB/active" 2>/dev/null || true
    echo "الحملة منتهية؛ أُزيل active"
    return 0
  fi
  if [ "$st" = RUNNING ]; then
    # جهازٌ يعمل ولا ينبض ساعةً (علق قبل الدفتر أو بعده) يُكلّف بلا عدّ ⇒ يُوقَف ويُحسب إخفاقاً
    local age
    age=$(python3 - "$(gs_json "$GSB/vm_status.json" | jget updated "")" \
      "$(gc compute instances describe "$INSTANCE" --zone "$ZONE" --format='value(lastStartTimestamp)')" <<'PYEOF'
import sys, time
from datetime import datetime
def t(x):
    try: return datetime.fromisoformat(x.replace("Z", "+00:00")).timestamp()
    except Exception: return 0
print(int(time.time() - max(t(sys.argv[1]), t(sys.argv[2]))))
PYEOF
)
    echo "آخر نبضة/إقلاع منذ ${age}ث"
    if [ "$age" -gt 3600 ]; then
      local n; n=$(gcloud storage cat "$GSB/fails" 2>/dev/null || echo 0); n=$(( ${n:-0} + 1 ))
      echo "$n" > "$TMP/fails"; gcloud storage cp -q "$TMP/fails" "$GSB/fails"
      if (( n >= 3 )); then
        err "الجهاز صامتٌ للمرّة $n ⇒ حذفٌ وإنهاءُ الحملة"
        gc compute instances delete "$INSTANCE" --zone "$ZONE" --quiet --delete-disks=all >/dev/null
        echo stalled > "$TMP/done"; gcloud storage cp -q "$TMP/done" "$GSB/done"; gcloud storage rm -q "$GSB/active" || true
      else
        err "الجهاز صامتٌ ساعةً (إخفاق $n) ⇒ إيقاف، ويعيده المراقب"
        gc compute instances stop "$INSTANCE" --zone "$ZONE" >/dev/null
      fi
      return 0
    fi
  fi
  case "$st" in
    TERMINATED|STOPPED) gc compute instances start "$INSTANCE" --zone "$ZONE" >/dev/null && echo "أُعيد التشغيل" ;;
    NONE) gcloud storage rm -q "$GSB/active" 2>/dev/null || true; echo "لا جهاز ولا إنهاء ⇒ أُزيل active" ;;
    *) echo "لا إجراء" ;;
  esac
}

# ══════════════ مسار Vertex AI CustomJob ══════════════
# السعر المحاسَب به (دولار/ساعة، us-central1، صفحة أسعار Vertex للتدريب المخصّص https://cloud.google.com/vertex-ai/pricing):
#   عند الطلب: g2-standard-24 = 2.30138 (يشمل L4×2) ⇒ ×1.15 = 2.65.
#   spot: يُفوتَر بسعر Compute Engine Spot + رسم إدارة Vertex، ولم يُؤكَّد رقمُه من صفحة Google؛ مصادر خارجية متضاربة
#   (0.74 – 1.57 للجهاز وحده) ⇒ نحسب بسقفٍ متحفّظ ≈ (1.57 + رسم إدارة تقديريّ 0.30) ×1.15 = 2.15. الكلفة الفعلية من API.
v_default_rate() { if [ "$SPOT" = "true" ]; then echo 2.15; else echo 2.65; fi; }

v_list() { gc ai custom-jobs list --region "$REGION" --filter='labels.app=mushafak1' --format=json 2>/dev/null || echo '[]'; }
# vj <وضع> [وسائط] ⇐ JSON المهام من stdin: active | nonterminal | cost <بدء> <سعر> | last
vj() {
  python3 -c '
import json, sys, time
from datetime import datetime
mode = sys.argv[1]
try: jobs = json.load(sys.stdin)
except Exception: jobs = []
def t(x):
    try: return datetime.fromisoformat(x.replace("Z", "+00:00")).timestamp()
    except Exception: return 0.0
TERM = {"JOB_STATE_SUCCEEDED", "JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED", "JOB_STATE_PARTIALLY_SUCCEEDED"}
ACT = {"JOB_STATE_PENDING", "JOB_STATE_QUEUED", "JOB_STATE_RUNNING"}
now = time.time()
if mode == "active":
    for j in jobs:
        if j.get("state") in ACT: print(j["name"].rsplit("/", 1)[-1], j["state"].replace("JOB_STATE_", ""))
elif mode == "nonterminal":
    for j in jobs:
        if j.get("state") not in TERM: print(j["name"].rsplit("/", 1)[-1], j.get("state"))
elif mode == "cost":
    start, rate = t(sys.argv[2]), float(sys.argv[3])
    secs = 0.0
    for j in jobs:
        if t(j.get("createTime", "")) < start or not j.get("startTime"): continue
        # Vertex يضع startTime لحظةَ القبول ولو بقيت المهمة تنتظر السعة؛ والانتظارُ لا يُحاسَب
        if j.get("state") in ("JOB_STATE_PENDING", "JOB_STATE_QUEUED"): continue
        end = t(j["endTime"]) if j.get("endTime") else now
        secs += max(0.0, end - t(j["startTime"]))
    print(f"{secs / 3600 * rate:.2f} {len(jobs)}")
elif mode == "last":
    if not jobs: print("NONE NONE 0 0")
    else:
        j = max(jobs, key=lambda x: t(x.get("createTime", "")))
        print(j["name"].rsplit("/", 1)[-1], j.get("state", "?").replace("JOB_STATE_", ""), int(t(j.get("startTime") or j.get("createTime", ""))), int(t(j.get("endTime", ""))))
' "$@"
}
v_active_ids() { v_list | vj active | awk '{print $1}'; }
v_nonterminal_lines() {   # للجرد: بلا ابتلاعٍ للأخطاء (واجهةٌ معطّلة تُحسب صفراً في count_zero، وغيرُها ERR) ولا حصرَ بالوسم
  local j; j=$(gc ai custom-jobs list --region "$REGION" --format=json) || return 1
  printf '%s' "$j" | vj nonterminal
}
v_cancel_active() {
  local id
  for id in $(v_list | vj nonterminal | awk '{print $1}'); do
    gc ai custom-jobs cancel "$id" --region "$REGION" --quiet >/dev/null 2>&1 && echo "أُلغيت المهمة $id" || echo "تعذّر إلغاء $id"
  done
}

# الكلفة: الأكبر من (API: مجموع مدد مهام الوسم منذ بدء الحملة × السعر) و(دفتر النبضات داخل المهمة) ⇒ يطبع: api ledger max budget jobs
v_costs() {
  local c rate b start api jobs s led mx
  c=$(gs_json "$GSB/campaign.json"); rate=$(echo "$c" | jget rate_usd_per_hour 0); b=$(echo "$c" | jget budget_usd 0)
  start=$(echo "$c" | jget campaign_start "1970-01-01T00:00:00Z")
  read -r api jobs <<< "$(v_list | vj cost "$start" "$rate")"
  s=$(gs_json "$GSB/ledger.json" | jget seconds 0); led=$(cost_of "$s" "$rate")
  mx=$(awk -v a="$api" -v l="$led" 'BEGIN{printf "%.2f", (a>l)?a:l}')
  echo "$api $led $mx $b $jobs"
}

# عدّاد الإخفاق المشترك مع الجهاز (fails.json): يُصفَّر إن تقدّمت الخطوة، ويُرفع الدفتر ⇒ يطبع العدد
v_bump_fails() {
  local step; step=$(gs_json "$GSB/vm_status.json" | jget ckpt_step -1); [ "$step" = None ] && step=-1
  gs_json "$GSB/fails.json" | python3 -c '
import json, sys, time
d = json.load(sys.stdin); cur = int(sys.argv[1])
n = 1 if cur > int(d.get("step", -1)) else int(d.get("n", 0)) + 1
json.dump({"n": n, "step": max(cur, int(d.get("step", -1))), "updated_epoch": int(time.time()), "by": "watch"}, open(sys.argv[2], "w"))
print(n)' "$step" "$TMP/fails.json" && gcloud storage cp -q "$TMP/fails.json" "$GSB/fails.json"
}

# يقدّم المهمة: يقرأ campaign.json (spot · rate · budget) ويحسب المهلة من الميزانية الباقية
v_submit() {
  local c rate b spot mx rem secs strat
  c=$(gs_json "$GSB/campaign.json"); rate=$(echo "$c" | jget rate_usd_per_hour 0); b=$(echo "$c" | jget budget_usd 0)
  spot=$(echo "$c" | jget spot true)
  read -r _ _ mx _ _ <<< "$(v_costs)"
  rem=$(awk -v b="$b" -v c="$mx" -v r="$rate" 'BEGIN{h=(b-c)/r; if(h<0)h=0; printf "%.3f", h}')
  awk -v h="$rem" 'BEGIN{exit !(h>0.05)}' || { err "لا ميزانية باقية (الكلفة \$$mx من \$$b)"; return 1; }
  secs=$(awk -v h="$rem" 'BEGIN{t=(h+0.25); if(t>24)t=24; printf "%d", t*3600}')
  strat=STANDARD; [ "$spot" = "True" ] || [ "$spot" = "true" ] && strat=SPOT
  python3 - "$VERTEX_IMAGE" "$VERTEX_MACHINE" "$GSB/run" "$secs" "$strat" "$SA_EMAIL" > "$TMP/job.json" <<'PYEOF'
import json, sys
image, machine, run_uri, secs, strat, sa = sys.argv[1:7]
boot = ('set -e; mkdir -p /tmp/vt; export RUN_URI="$1"; '
        'if command -v gcloud >/dev/null 2>&1; then gcloud storage cp -q "$RUN_URI/vertex_train.sh" /tmp/vt/vertex_train.sh; '
        'else python3 -m pip install -q google-cloud-storage && python3 -c "import sys;from google.cloud import storage;'
        'u=sys.argv[1][5:].split(\'/\',1);storage.Client().bucket(u[0]).blob(u[1]).download_to_filename(sys.argv[2])" '
        '"$RUN_URI/vertex_train.sh" /tmp/vt/vertex_train.sh; fi; exec bash /tmp/vt/vertex_train.sh')
spec = {
    "workerPoolSpecs": [{
        "machineSpec": {"machineType": machine, "acceleratorType": "NVIDIA_L4", "acceleratorCount": 2},
        "replicaCount": 1,
        "diskSpec": {"bootDiskType": "pd-ssd", "bootDiskSizeGb": 200},
        "containerSpec": {"imageUri": image, "command": ["bash", "-c"], "args": [boot, "vertex_train", run_uri]},
    }],
    "serviceAccount": sa,
    "scheduling": {"strategy": strat, "timeout": f"{secs}s", "restartJobOnWorkerRestart": False},
}
print(json.dumps(spec))
PYEOF
  local name
  name=$(gc ai custom-jobs create --region "$REGION" --display-name "mushafak1-$(date -u +%m%d-%H%M)" \
    --config "$TMP/job.json" --labels app=mushafak1 --format='value(name)') || { err "تعذّر إنشاء CustomJob"; return 1; }
  echo "أُنشئت المهمة ${name##*/} (${VERTEX_MACHINE} L4×2 $strat) · المهلة ${secs}s · الصورة ${VERTEX_IMAGE##*/}"
}

v_launch() {
  [[ "${EXPECT_STEP:-}" =~ ^[0-9]+$ ]] || { err "expect_step مطلوب ورقميّ"; exit 1; }
  [[ "$REGION" =~ ^[a-z]+-[a-z]+[0-9]+$ ]] || { err "region غير صالحة"; exit 1; }
  [[ "$VERTEX_MACHINE" =~ ^g2-standard-[0-9]+$ ]] || { err "machine_type من عائلة g2-standard"; exit 1; }
  [[ "$BUDGET_USD" =~ ^[0-9]+([.][0-9]+)?$ ]] || { err "budget_usd غير رقميّ"; exit 1; }
  local rate=${RATE_USD_PER_HOUR:-}; [ -n "$rate" ] || rate=$(v_default_rate)
  [[ "$rate" =~ ^[0-9]+([.][0-9]+)?$ ]] || { err "rate غير رقميّ"; exit 1; }
  local act; act=$(v_active_ids | head -1)
  [ -z "$act" ] || { err "توجد مهمة نشطة ($act) بالوسم app=mushafak1 — لا مهمةَ ثانية"; exit 1; }
  local start=""
  if bucket_exists; then
    start=$(gs_json "$GSB/campaign.json" | jget campaign_start "")
  else
    gc storage buckets create "$GSB" --location="$REGION" --uniform-bucket-level-access
  fi
  [[ "$start" =~ ^20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]T ]] || start=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  pip install -q boto3
  python3 "$HERE/r2_stage.py" urls --out "$TMP/stage_urls.json" --expect-step "$EXPECT_STEP"
  python3 - "$rate" "$BUDGET_USD" "$VERTEX_MACHINE" "$SPOT" "$start" "$PROJECT_ID" "$EXPECT_STEP" "$BUCKET" > "$TMP/campaign.json" 3> "$TMP/config.json" <<'PYEOF'
import json, os, sys, time
rate, budget, machine, spot, start, project, expect, bucket = sys.argv[1:9]
print(json.dumps({"backend": "vertex", "rate_usd_per_hour": float(rate), "budget_usd": float(budget), "machine_type": machine,
                  "spot": spot == "true", "campaign_start": start, "region": os.environ.get("REGION", "us-central1"),
                  "launched": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}))
with os.fdopen(3, "w") as f:
    json.dump({"bucket": bucket, "project": project, "expect_step": int(expect), "rate": float(rate), "budget_usd": float(budget),
               "workers": 10, "torch_pin": os.environ.get("TORCH_PIN", "2.10.0")}, f)
PYEOF
  gcloud storage cp -q "$TMP/campaign.json" "$GSB/campaign.json"
  gcloud storage cp -q "$TMP/config.json" "$GSB/run/config.json"
  gcloud storage cp -q "$TMP/stage_urls.json" "$GSB/run/stage_urls.json"
  gcloud storage cp -q "$HERE/vertex_train.sh" "$GSB/run/vertex_train.sh"
  rm -f "$TMP/stage_urls.json"
  gcloud storage rm -q "$GSB/done" "$GSB/stop_request" "$GSB/fails.json" 2>/dev/null || true
  v_submit || exit 1
  echo on > "$TMP/active"; gcloud storage cp -q "$TMP/active" "$GSB/active"
  echo "أُطلقت الحملة · rate=\$$rate/h · budget=\$$BUDGET_USD"
}

v_status() {
  bucket_exists || { echo "backend=vertex bucket=none"; return 0; }
  local api led mx b n id st s e
  read -r api led mx b n <<< "$(v_costs)"
  read -r id st s e <<< "$(v_list | vj last)"
  echo "backend=vertex jobs=$n last_job=$id last_state=$st active_jobs=$(v_active_ids | grep -c . || true)"
  [ "$id" != NONE ] && gc ai custom-jobs describe "$id" --region "$REGION" --format=json 2>/dev/null | python3 -c '
import json, sys
j = json.load(sys.stdin)
print("job:", j.get("state"), "create", j.get("createTime"), "start", j.get("startTime"), "update", j.get("updateTime"))
if j.get("error"): print("job.error:", j["error"].get("code"), str(j["error"].get("message", ""))[:300])' || true
  gcloud storage cat "$GSB/startup.log" 2>/dev/null | tail -n 25 | sed 's/^/log| /' || true
  echo "active=$(gs_has "$GSB/active" && echo 1 || echo 0) done=$(gs_has "$GSB/done" && echo "$(gcloud storage cat "$GSB/done")" || echo 0)"
  echo "cost_api_usd=$api cost_ledger_usd=$led cost_effective_usd=$mx budget_usd=$b"
  gs_json "$GSB/vm_status.json" | python3 -c '
import json, sys
d = json.load(sys.stdin)
for k in ("stage", "phase", "last_step", "ckpt_step", "start_step", "resumed_from", "train_rc", "sync_ok", "torch", "updated"):
    if k in d: print(f"vm.{k}={d[k]}")'
}

v_watch() {
  bucket_exists || { echo "لا دلو ⇒ لا حملة"; return 0; }
  gs_has "$GSB/active" || { echo "لا حملة فعّالة"; return 0; }
  local jobs api led mx b n fin=0 over=0 act id st s e
  jobs=$(v_list)
  read -r api led mx b n <<< "$(v_costs)"
  gs_has "$GSB/done" && fin=1
  awk -v c="$mx" -v b="$b" 'BEGIN{exit !(b>0 && c>=b)}' && over=1
  act=$(echo "$jobs" | vj active | head -1)
  echo "cost_api=\$$api cost_ledger=\$$led effective=\$$mx budget=\$$b done=$fin over=$over active=${act:-none}"
  if [ "$fin" = 1 ] || [ "$over" = 1 ]; then
    v_cancel_active
    gcloud storage rm -q "$GSB/active" 2>/dev/null || true
    [ "$over" = 1 ] && [ "$fin" = 0 ] && { echo budget_stop > "$TMP/done"; gcloud storage cp -q "$TMP/done" "$GSB/done"; }
    echo "الحملة منتهية؛ أُلغيت المهام النشطة وأُزيل active"
    return 0
  fi
  if [ -n "$act" ]; then
    read -r id st <<< "$act"
    if [ "$st" = RUNNING ]; then
      local age
      age=$(python3 - "$(gs_json "$GSB/vm_status.json" | jget updated "")" "$(echo "$jobs" | vj last | awk '{print $3}')" <<'PYEOF'
import sys, time
from datetime import datetime
def t(x):
    try: return datetime.fromisoformat(x.replace("Z", "+00:00")).timestamp()
    except Exception: return 0
print(int(time.time() - max(t(sys.argv[1]), float(sys.argv[2] or 0))))
PYEOF
)
      echo "آخر نبضة/بدء منذ ${age}ث"
      if [ "$age" -gt 3600 ]; then
        local k; k=$(v_bump_fails)
        err "المهمة $id صامتةٌ أكثر من 60 د (إخفاق $k) ⇒ إلغاء"
        gc ai custom-jobs cancel "$id" --region "$REGION" --quiet >/dev/null 2>&1 || true
        if (( k >= 3 )); then
          echo stalled > "$TMP/done"; gcloud storage cp -q "$TMP/done" "$GSB/done"; gcloud storage rm -q "$GSB/active" || true
        fi
      fi
    else echo "لا إجراء (المهمة $id $st)"; fi
    return 0
  fi
  # لا مهمة نشطة: أخفقت آخرُ مهمة بلا عدٍّ من الجهاز؟ ثم إعادة الإطلاق
  read -r id st s e <<< "$(echo "$jobs" | vj last)"
  if [ "$st" = FAILED ]; then
    local upd; upd=$(gs_json "$GSB/fails.json" | jget updated_epoch 0)
    if [ "${upd:-0}" -lt "${s:-0}" ]; then
      local k; k=$(v_bump_fails); echo "أخفقت المهمة $id بلا عدٍّ من الجهاز ⇒ إخفاق $k"
      if (( k >= 3 )); then
        echo failed_final > "$TMP/done"; gcloud storage cp -q "$TMP/done" "$GSB/done"; gcloud storage rm -q "$GSB/active" || true
        err "ثلاثُ مهامّ متتاليةٌ فاشلةٌ بلا تقدّم ⇒ failed_final"; return 0
      fi
    fi
  fi
  echo "لا مهمة نشطة (آخرها $id $st) ⇒ إعادة الإطلاق"
  v_submit || return 1
}

# ══════════════ توزيع الأفعال حسب المسار ══════════════
resolve_backend() {   # launch: من المدخل؛ وغيره: من campaign.json (الحملات القديمة بلا الحقل = gce)
  BACKEND=${BACKEND:-vertex}
  [ "${1:-}" = launch ] && return 0
  bucket_exists || return 0
  BACKEND=$(gs_json "$GSB/campaign.json" | jget backend gce)
}
cmd_launch() { if [ "$BACKEND" = vertex ]; then v_launch; else gce_launch; fi; }
cmd_status() { if [ "$BACKEND" = vertex ]; then v_status; else gce_status; fi; }
cmd_watch()  { if [ "$BACKEND" = vertex ]; then v_watch; else gce_watch; fi; }

resolve_backend "${1:-}"
case "${1:?الفعل}" in
  launch) cmd_launch ;;
  relaunch) [ "$BACKEND" = vertex ] || { err "relaunch لـvertex وحده"; exit 1; }; v_cancel_active; cmd_launch ;;
  status) cmd_status ;; export) cmd_export ;; teardown) cmd_teardown ;; watch) cmd_watch ;;
  *) err "فعلٌ مجهول: $1"; exit 1 ;;
esac
