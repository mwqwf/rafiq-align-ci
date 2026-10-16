#!/usr/bin/env bash
# مُتحكِّم حملة تدريب «مصحفك-1» على GCE: launch · status · export · teardown · watch
# يعمل في سير gcp_train بعد المصادقة (OIDC). المتغيّرات من السير: PROJECT_ID ZONE INSTANCE BUCKET
# ⛔ لا يطبع روابطَ موقّعة ولا مفاتيح؛ أعدادٌ وأرقامٌ فقط.
set -euo pipefail

: "${PROJECT_ID:?}" "${ZONE:?}" "${INSTANCE:?}"
BUCKET=${BUCKET:-${PROJECT_ID}-mushafak1}
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

cmd_launch() {
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

cmd_status() {
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
    if [ -n "$(inst_status)" ] && [ "$(inst_status)" = RUNNING ]; then
      echo on > "$TMP/sr"; gcloud storage cp -q "$TMP/sr" "$GSB/stop_request"
      echo "طُلب من الجهاز مزامنةٌ أخيرة وحذفٌ ذاتيّ؛ انتظارٌ حتى 14 د"
      for _ in $(seq 1 28); do [ "$(inst_status)" = RUNNING ] || break; sleep 30; done
    fi
    do_export
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

cmd_watch() {
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

case "${1:?الفعل}" in
  launch) cmd_launch ;; status) cmd_status ;; export) cmd_export ;; teardown) cmd_teardown ;; watch) cmd_watch ;;
  *) err "فعلٌ مجهول: $1"; exit 1 ;;
esac
