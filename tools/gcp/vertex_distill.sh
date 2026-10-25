#!/usr/bin/env bash
# سكربت شوط تقطير «المُنصِت» التكميليّ داخل مهمة Vertex AI CustomJob (L4×2، STANDARD). يكيّف vertex_train.sh ولا يستبدله:
# يُنزَّل من gs://<bucket>/run/vertex_train.sh (ينسخه launch من هذا الملف حين job=distill) ويُشغَّل بأمر الحاوية.
# الإعدادات من gs://<bucket>/run/config.json: bucket · project · expect_step · rate · budget_usd · workers · torch_pin · distill_args · d1_parts · pub_base
# والروابطُ الموقّعة (المعلّم · الشيفرة · الجزء 16 · نقطةُ البدء · مواضعُ الكتابة) في gs://<bucket>/run/grant.json (دلوٌ خاصّ، لا تُطبع).
# الحالةُ على R2 تحت models/mushafak1/stage-distill-gcp/ (يرفعها distill_run.py: last.pt كلَّ 10 د · status.json كلَّ دقيقة · ONNX في النهاية).
# لا حذفَ ذاتيّاً ولا shutdown: المهمةُ تنتهي بخروج هذا السكربت. يكتب done عند finished/early_stop/budget_stop/stop_request/failed_final.
# ⛔ ما من إعادة إطلاقٍ تلقائيّةٍ بعد نهاية الدورة: done يوقف watch. وقطعُ SIGTERM بلا done يخرج 0 ويعيد watch الإطلاقَ من آخر نقطة (ضمن السقف).
# ⛔ لا set -x ولا طباعة لرابطٍ موقّع؛ الروابط تُمرَّر إلى curl عبر stdin لا سطر الأوامر.
set -euo pipefail

BASE=/var/lib/mushafak1
CODE=/opt/mushafak1/code
IN=$BASE/input
MIRROR=$IN/mirror
WORK=$BASE/work
OUT=$WORK/out
STATE=$BASE/state
LIB=$BASE/lib
LOG=$BASE/mushafak1.log
mkdir -p "$BASE" "$IN" "$MIRROR" "$WORK" "$OUT" "$STATE" "$LIB" /opt/mushafak1
exec > >(tee -a "$LOG") 2>&1
BOOT=$(date +%s)
say() { echo "$(date -u +%FT%TZ) $*"; }


RUN_URI=${RUN_URI:?RUN_URI غير مضبوط}   # gs://<bucket>/run يمرّره أمر الحاوية
GSB=${RUN_URI%/run}
BUCKET=${GSB#gs://}
need() { command -v "$1" >/dev/null 2>&1 || { say "⛔ ينقص الأمر $1"; exit 3; }; }
for c in python3 curl awk setsid tar nvidia-smi; do need "$c"; done
ensure_gcloud() {
  command -v gcloud >/dev/null 2>&1 && return 0
  say "gcloud غير موجود في الصورة ⇒ تنزيل google-cloud-cli"
  mkdir -p /opt/gcli && curl -fsSL https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-linux-x86_64.tar.gz | tar -xz -C /opt/gcli
  export PATH="/opt/gcli/google-cloud-sdk/bin:$PATH"; command -v gcloud >/dev/null 2>&1
}
ensure_gcloud || { say "⛔ تعذّر توفير gcloud"; exit 3; }
CFG=$BASE/config.json
gcloud storage cp -q "$RUN_URI/config.json" "$CFG" || { say "⛔ لا config.json في الدلو"; exit 2; }
# السجلُّ إلى الدلو كلَّ دقيقتين من أوّل لحظة (التحضيرُ قبل النبضة قد يطول أو يتعثّر بصمت)
( while sleep 120; do gcloud storage cp -q "$LOG" "${RUN_URI%/run}/startup.log" >/dev/null 2>&1 || true; done ) &
cfg() { python3 -c 'import json,sys;v=json.load(open(sys.argv[1])).get(sys.argv[2]);print(sys.argv[3] if v is None else v)' "$CFG" "$1" "${2:-}"; }
PROJECT=$(cfg project "")
[ -z "$PROJECT" ] || export CLOUDSDK_CORE_PROJECT=$PROJECT
INSTANCE=${CLOUD_ML_JOB_ID:-vertex-job}
# علامة الإقلاع الفعليّ: ملفٌّ فارغ باسم <معرّف>.<epoch> يعتمده ctl.sh في حساب الكلفة (المهمة المنتظرة لا تُحاسَب)
: | gcloud storage cp -q - "$GSB/jobs/${INSTANCE}.${BOOT}" >/dev/null 2>&1 || true
EXPECT_STEP=$(cfg expect_step "")
RATE=$(cfg rate "")
BUDGET=$(cfg budget_usd "")
WORKERS=$(cfg workers 10)
PUB=$(cfg pub_base https://pub-2c2e1dcd92e84a2898820dd38d3e09e6.r2.dev)
D1_PARTS=$(cfg d1_parts "h 00 01 02 03 04 05 06 07 08 09 10 11 12 13 14 15")
TORCH_PIN=$(cfg torch_pin 2.10.0)
[[ "$EXPECT_STEP" =~ ^[0-9]+$ ]] || { say "⛔ expect-step غير رقميّ"; exit 2; }
[[ "$RATE" =~ ^[0-9]+([.][0-9]+)?$ && "$BUDGET" =~ ^[0-9]+([.][0-9]+)?$ ]] || { say "⛔ rate/budget غير رقميّين"; exit 2; }

GS=$GSB/distill-out
CK=$OUT
OUTCOME=failed          # يُحدَّث قبل الخروج؛ الافتراضيّ إخفاقٌ
TRAIN_RC=-1; START_STEP=-1; SRC=""; SYNC_OK=1; TORCH_V=""
echo "$BOOT" > "$BASE/tick_last"

# ── مساعدات بايثون صغيرة تُكتب مرّةً (الروابط تبقى في ملفاتٍ لا في سطر الأوامر) ──
cat > "$LIB/ledger.py" <<'PYEOF'
import json, sys, time
# usage: ledger.py <ledger.json> <delta_seconds>  ⇒ يكتب الدفتر ويطبع مجموعَ الثواني
p, delta = sys.argv[1], int(sys.argv[2])
try: d = json.load(open(p))
except Exception: d = {}
d["seconds"] = int(d.get("seconds", 0)) + max(0, delta)
d["minutes"] = round(d["seconds"] / 60, 2)
d["updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
json.dump(d, open(p, "w"))
print(d["seconds"])
PYEOF
cat > "$LIB/fetch.py" <<'PYEOF'
import hashlib, json, os, subprocess, sys, concurrent.futures as cf
# usage: fetch.py code <grant.json> <dest.zip>  |  fetch.py data <grant.json> <dest-dir>  |  fetch.py d1 <pubbase> <dest> <parts...>
def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""): h.update(b)
    return h.hexdigest()
def curl(url, dst, secret):
    tmp = dst + ".part"
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    cfg = f'url = "{url}"\n'
    cmd = ["curl", "-fsSL", "--retry", "6", "--retry-delay", "5", "--retry-all-errors", "-C", "-",
           "-A", "Mozilla/5.0 (QuranRafiq mushafak1 vertex)", "-o", tmp]
    cmd += ["-K", "-"]
    r = subprocess.run(cmd, input=cfg.encode(), stderr=subprocess.PIPE)
    if r.returncode != 0:      # لا نطبع stderr كاملاً: قد يحوي الرابط
        raise RuntimeError(f"curl rc={r.returncode} for {os.path.basename(dst)}")
    os.replace(tmp, dst)
def stage(urls_path, dest):
    d = json.load(open(urls_path))
    ok = bad = 0
    def one(f):
        dst = os.path.join(dest, f["rel"])
        if os.path.exists(dst) and os.path.getsize(dst) == f["size"] and sha(dst) == f["sha256"]:
            return True
        for _ in range(3):
            try: curl(f["url"], dst, True)
            except Exception as e: print("⚠", e); continue
            if sha(dst) == f["sha256"] and os.path.getsize(dst) == f["size"]: return True
            os.remove(dst)
        return False
    with cf.ThreadPoolExecutor(3) as ex: res = list(ex.map(one, d["files"]))
    ok = sum(res); bad = len(res) - ok
    try: curl(d["manifest"], os.path.join(dest, "manifest.json"), True)
    except Exception as e: print("⚠ manifest", e)
    print(f"stage files ok={ok} bad={bad} step={d.get('step')}")
    return bad == 0
def verify(dest):
    m = json.load(open(os.path.join(dest, "manifest.json")))
    bad = 0
    for f in m["files"]:
        key = f["key"]; rel = key.split("models/mushafak1/stage/", 1)[-1].lstrip("/")
        p = os.path.join(dest, rel)
        if not (os.path.exists(p) and sha(p) == f["sha256"]): bad += 1
    print(f"verify files={len(m['files'])} bad={bad}")
    return bad == 0
def d1(pub, dest, parts):
    def one(p):
        for ext in ("json", "tar"):
            dst = os.path.join(dest, f"part_{p}.{ext}")
            if ext == "tar":
                want = json.load(open(os.path.join(dest, f"part_{p}.json"))).get("bytes")
                if os.path.exists(dst) and want and os.path.getsize(dst) == want: continue
            elif os.path.exists(dst): continue
            ok = False
            for _ in range(3):
                try: curl(f"{pub}/models/mushafak1/data/d1/part_{p}.{ext}", dst, False)
                except Exception as e: print("⚠", e); continue
                if ext == "tar":
                    want = json.load(open(os.path.join(dest, f"part_{p}.json"))).get("bytes")
                    if want and os.path.getsize(dst) != want: os.remove(dst); continue
                ok = True; break
            if not ok: return False
        return True
    with cf.ThreadPoolExecutor(4) as ex: res = list(ex.map(one, parts))
    print(f"d1 parts ok={sum(res)} bad={len(res) - sum(res)}")
    return all(res)
def grant_code(path, dst):
    c = json.load(open(path))["code"]
    if os.path.exists(dst) and os.path.getsize(dst) == c["size"] and sha(dst) == c["sha256"]: return True
    for _ in range(3):
        try: curl(c["get"], dst, True)
        except Exception as e: print("⚠", e); continue
        if os.path.getsize(dst) == c["size"] and sha(dst) == c["sha256"]: return True
        os.remove(dst)
    return False
def grant_data(path, dest):
    files = json.load(open(path))["data"]
    def one(f):
        dst = os.path.join(dest, f["rel"])
        if os.path.exists(dst) and os.path.getsize(dst) == f["size"] and sha(dst) == f["sha256"]: return True
        for _ in range(3):
            try: curl(f["url"], dst, True)
            except Exception as e: print("⚠", e); continue
            if os.path.getsize(dst) == f["size"] and sha(dst) == f["sha256"]: return True
            os.remove(dst)
        return False
    res = [one(f) for f in files]
    print(f"grant data files ok={sum(res)} bad={len(res) - sum(res)}")
    return all(res)
mode = sys.argv[1]
if mode == "code": ok = grant_code(sys.argv[2], sys.argv[3])
elif mode == "data": ok = grant_data(sys.argv[2], sys.argv[3])
elif mode == "d1": ok = d1(sys.argv[2], sys.argv[3], sys.argv[4:])
else: sys.exit("وضع غير معروف")
sys.exit(0 if ok else 1)
PYEOF

# ── الدفتر والكلفة ──
tick() {   # يضيف الثواني الفعليّة منذ آخر نبضة ناجحة إلى الدفتر في الدلو ⇒ يطبع المجموع
  local now last tmp="$BASE/ledger.cur" tot
  now=$(date +%s); last=$(cat "$BASE/tick_last" 2>/dev/null || echo "$now")
  gcloud storage cat "$GSB/ledger.json" > "$tmp" 2>/dev/null || echo '{}' > "$tmp"
  tot=$("$PY" "$LIB/ledger.py" "$tmp" "$(( now - last ))") || return 1
  gcloud storage cp -q "$tmp" "$GSB/ledger.json" || return 1
  echo "$now" > "$BASE/tick_last"; echo "$tot" > "$BASE/ledger_s"
}
ledger_s() { local t; t=$(gcloud storage cat "$GSB/ledger.json" 2>/dev/null | "$PY" -c 'import json,sys;print(int(json.load(sys.stdin).get("seconds",0)))' 2>/dev/null) || t=0; echo "${t:-0}"; }
cost_of()  { awk -v s="$1" -v r="$RATE" 'BEGIN{printf "%.2f", s*r/3600}'; }
over_budget() { awk -v c="$1" -v b="$BUDGET" 'BEGIN{exit !(c>=b)}'; }
# كلُّ إقلاعٍ يعدّ من لحظة الإقلاع: لا يُسقط وقتَ التحضير، ولا يحسب مدّةَ التوقّف بين إقلاعين
echo "$BOOT" > "$BASE/tick_last"
rm -f "$BASE/stop_reason"   # سببُ الإقلاع السابق لا يُورَث

PY=$(command -v python3)
TORCH_V=$("$PY" -c 'import torch;print(torch.__version__, "cuda", torch.version.cuda)' 2>/dev/null || echo none)
say "torch في الصورة: $TORCH_V · المطلوب: $TORCH_PIN"
# النقطةُ دُرّبت بـtorch 2.10.0+cu128: نثبّت النسخة نفسها (عجلة cu128 تحمل مكتبات CUDA الخاصّة بها) إن اختلفت نسخة الصورة
if [ -n "$TORCH_PIN" ] && [ "$TORCH_PIN" != none ] && [[ "$TORCH_V" != "$TORCH_PIN"* ]]; then
  say "تثبيت torch==$TORCH_PIN (cu128)"
  "$PY" -m pip install -q "torch==$TORCH_PIN" --index-url https://download.pytorch.org/whl/cu128 --extra-index-url https://pypi.org/simple \
    || { say "⛔ تعذّر تثبيت torch==$TORCH_PIN"; exit 3; }
  TORCH_V=$("$PY" -c 'import torch;print(torch.__version__, "cuda", torch.version.cuda)')
fi
"$PY" -c 'import torch,sys; sys.exit(0 if torch.cuda.is_available() else 1)' || { say "⛔ torch لا يرى CUDA"; exit 3; }
say "torch $TORCH_V · GPUs=$("$PY" -c 'import torch;print(torch.cuda.device_count())')"

step_of() {   # خطوةُ نقطةٍ أو -1
  [ -f "$1" ] || { echo -1; return 0; }
  "$PY" - "$1" <<'PYEOF' || echo -1
import sys, torch
try: print(int(torch.load(sys.argv[1], map_location="cpu", weights_only=False, mmap=True).get("step", -1)))
except Exception as e:
    print("⚠ تعذّرت قراءة", sys.argv[1], file=sys.stderr); print(-1)
PYEOF
}

sync_state() { mkdir -p "$CK"; gcloud storage rsync -r --no-user-output-enabled --exclude='.*\.tmp$' "$CK" "$GS"; }

publish_status() {
  # الحالةُ تُقرأ من سجلّ الشوط نفسِه (distill_run يطبعه إلى stdout ⇒ $LOG): آخرُ STEP وآخرُ EVAL؛ ولا تُطبع روابط
  local tmp="$BASE/status_pub.json" s; s=$(cat "$BASE/ledger_s" 2>/dev/null || echo 0)
  "$PY" - "$LOG" "$CK/last.pt" "$1" "$TRAIN_RC" "$SYNC_OK" "$START_STEP" "$SRC" "$INSTANCE" "$s" "$(cost_of "$s")" "$BUDGET" "$RATE" "$TORCH_V" > "$tmp" <<'PYEOF'
import sys, json, re, os, time
log, last, stage, trc, sync_ok, start_step, src, inst, secs, cost, budget, rate, tv = sys.argv[1:14]
tail = ""
try:
    with open(log, "rb") as f:
        f.seek(0, 2); n = f.tell(); f.seek(max(0, n - 600_000))
        tail = f.read().decode("utf-8", "replace")
except Exception: pass
steps = re.findall(r"\] STEP (\d+) (.*)", tail)
evals = re.findall(r"\] EVAL step (\d+) .*?\"_all\": \{\"n\": \d+, \"per\": ([0-9.]+)", tail)
ckstep = None
try:
    import torch
    if os.path.exists(last): ckstep = int(torch.load(last, map_location="cpu", weights_only=False, mmap=True).get("step", -1))
except Exception: pass
print(json.dumps({"platform": "vertex", "job": "distill", "instance": inst, "stage": stage, "phase": "train",
    "last_step": int(steps[-1][0]) if steps else None, "last_step_line": (steps[-1][1][:300] if steps else None),
    "last_eval": ({"step": int(evals[-1][0]), "per": float(evals[-1][1])} if evals else None),
    "ckpt_step": ckstep, "start_step": int(start_step), "resumed_from": src, "train_rc": int(trc), "sync_ok": sync_ok == "1", "torch": tv,
    "hours": round(int(secs) / 3600, 2), "cost_usd": float(cost), "budget_usd": float(budget), "rate_usd_per_hour": float(rate),
    "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, ensure_ascii=False, indent=1))
PYEOF
  gcloud storage cp -q "$tmp" "$GSB/vm_status.json"
}

# ── المهلةُ الصلبة: تقطع الشوطَ إن علق شيءٌ (الميزانيّة الباقية + 0.1 س، دون مهلة Vertex المضبوطة على +0.25 س) ──
S0=$(ledger_s)
REM_H=$(awk -v s="$S0" -v b="$BUDGET" -v r="$RATE" 'BEGIN{h=(b-s*r/3600)/r; if(h<0)h=0; printf "%.3f", h}')
MAIN=$$
( sleep "$(awk -v h="$REM_H" 'BEGIN{printf "%d", (h+0.1)*3600}')"; echo "$(date -u +%FT%TZ) ⛔ WATCHDOG"; echo budget_stop > "$BASE/stop_reason"; kill -TERM "$MAIN" ) &
WATCHDOG=$!

finish() {
  local rc=$?
  trap - EXIT TERM
  say "finish rc=$rc outcome=$OUTCOME train_rc=$TRAIN_RC"
  [ -n "${SYNCER:-}" ] && kill "$SYNCER" 2>/dev/null || true
  kill "$WATCHDOG" 2>/dev/null || true
  [ -f "$BASE/train.pid" ] && kill -TERM -- "-$(cat "$BASE/train.pid")" 2>/dev/null || true
  [ -f "$BASE/stop_reason" ] && OUTCOME=$(cat "$BASE/stop_reason")
  tick || say "⚠ نبضةُ الدفتر الأخيرة أخفقت"
  sync_state || { SYNC_OK=0; say "⛔ المزامنة الأخيرة أخفقت — الحالةُ على قرص الجهاز"; }
  publish_status "$OUTCOME" || say "⚠ نشر الحالة أخفق"
  gcloud storage cp -q "$LOG" "$GSB/startup.log" || true
  sync
  case "$OUTCOME" in
    preempted|shutdown)
      # قطعٌ خارجيّ (إلغاء المهمة أو انقضاء مهلتها): الحملةُ باقية، والمراقبُ (watch) يعيد الإطلاق من آخر نقطة على R2 ضمن السقف
      say "قطعٌ خارجيّ ($OUTCOME) ⇒ لا done"; exit 0 ;;
    failed)
      # عدّادُ الإخفاق: يُصفَّر إن تقدّمت الخطوة منذ الإخفاق المسجَّل (fails.json) ويشاركه المراقب
      n=$("$PY" - "$GSB/fails.json" "$CK/last.pt" <<'PYEOF'
import json, subprocess, sys, time
uri, ck = sys.argv[1:3]
try: d = json.loads(subprocess.run(["gcloud", "storage", "cat", uri], capture_output=True, text=True, check=True).stdout)
except Exception: d = {}
step = -1
try:
    import torch
    step = int(torch.load(ck, map_location="cpu", weights_only=False, mmap=True).get("step", -1))
except Exception: pass
n = 1 if step > int(d.get("step", -1)) else int(d.get("n", 0)) + 1
json.dump({"n": n, "step": max(step, int(d.get("step", -1))), "updated_epoch": int(time.time()), "by": "job"}, open("/tmp/fails.json", "w"))
subprocess.run(["gcloud", "storage", "cp", "-q", "/tmp/fails.json", uri])
print(n)
PYEOF
      ) || n=1
      if (( n >= 3 )); then OUTCOME=failed_final; else say "إخفاقٌ رقم $n ⇒ خروجٌ بخطأ فيعيد المراقبُ الإطلاق"; exit 1; fi ;;
  esac
  echo "$OUTCOME" > "$BASE/done"; gcloud storage cp -q "$BASE/done" "$GSB/done" || true
  gcloud storage rm -q "$GSB/active" 2>/dev/null || true
  say "done=$OUTCOME"
  [ "$OUTCOME" = failed_final ] && exit 1
  exit 0
}
trap finish EXIT
on_term() {
  if [ ! -f "$BASE/stop_reason" ]; then
    # TERM بلا سببٍ مكتوب = إلغاءُ المهمة أو انقضاءُ مهلتها
    echo shutdown > "$BASE/stop_reason"
  fi
  exit 1
}
trap on_term TERM

if gcloud storage ls "$GSB/done" >/dev/null 2>&1; then OUTCOME=$(gcloud storage cat "$GSB/done"); say "الحملةُ انتهت ($OUTCOME) — لا تدريب"; exit 0; fi
C0=$(cost_of "$S0")
say "بدء: instance=$INSTANCE expect>=$EXPECT_STEP cost=\$$C0 budget=\$$BUDGET rate=\$$RATE/h"
if over_budget "$C0"; then OUTCOME=budget_stop; exit 0; fi

for i in $(seq 1 90); do nvidia-smi -L >/dev/null 2>&1 && break; [ "$i" = 90 ] && { say "⛔ nvidia-smi لا يعمل بعد 15 د"; exit 4; }; sleep 10; done
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader

if [ ! -f "$BASE/.pip_ok" ]; then
  # -U: pyarrow الصورةِ مبنيٌّ على numpy 1 وتثبيتُ torch يرفع numpy إلى 2 ⇒ «_ARRAY_API not found» (سقط به شوط 10-16)
  "$PY" -m pip install -q -U soundfile boto3 onnx onnxruntime kaldi-native-fbank pyarrow requests cryptography
  touch "$BASE/.pip_ok"
fi
"$PY" -c 'import numpy, pyarrow, pyarrow.parquet, soundfile, kaldi_native_fbank, onnxruntime, onnx; print("numpy", numpy.__version__, "pyarrow", pyarrow.__version__)' \
  || { say "⛔ مكتباتُ البيانات لا تُستورد"; OUTCOME=failed; exit 3; }

# ── المنحة (روابط موقّعة في دلوٍ خاصّ) + الشيفرة + البيانات ──
GRANT=$BASE/grant.json
gcloud storage cp -q "$RUN_URI/grant.json" "$GRANT" || { say "⛔ لا grant.json في الدلو"; exit 7; }
if [ ! -f "$BASE/.code_ok" ]; then
  "$PY" "$LIB/fetch.py" code "$GRANT" "$BASE/code.zip" || { say "⛔ تنزيلُ الشيفرة أخفق"; OUTCOME=bad_stage; exit 7; }
  rm -rf "$CODE"; mkdir -p "$CODE"; "$PY" -m zipfile -e "$BASE/code.zip" "$CODE"
  touch "$BASE/.code_ok"
fi
[ -f "$CODE/tools/tasmi_model/distill_run.py" ] || { say "⛔ الشيفرة بلا distill_run.py"; OUTCOME=bad_stage; exit 5; }
say "الشيفرة: $(find "$CODE/tools/tasmi_model" -name '*.py' | wc -l) ملف py"

if [ ! -f "$BASE/.data_ok" ]; then
  # shellcheck disable=SC2086
  "$PY" "$LIB/fetch.py" d1 "$PUB" "$MIRROR" $D1_PARTS || { say "⛔ تنزيلُ d1 أخفق"; exit 8; }
  "$PY" "$LIB/fetch.py" data "$GRANT" "$MIRROR" || { say "⛔ تنزيلُ d2delta أخفق"; exit 8; }
  [ -f "$MIRROR/eligible.json" ] && [ -f "$MIRROR/part_16.tar" ] || { say "⛔ d2delta ناقصة (eligible.json/part_16.tar)"; OUTCOME=bad_stage; exit 8; }
  touch "$BASE/.data_ok"
fi
df -h "$BASE" | tail -1
say "مرايا البيانات: $(ls "$MIRROR"/part_*.tar | wc -l) جزءاً tar"

# ── نقطة البدء: R2 (last.pt الذي يكتبه الشوط كلَّ 10 د) ينزّله distill_run نفسُه؛ نتحقّق هنا من خطوتها قبل أيّ إنفاق ──
rm -f "$OUT/STOP_NOW"
mkdir -p "$BASE/probe"
"$PY" - "$GRANT" "$BASE/probe/last.pt" <<'PYEOF' || { say "⛔ تعذّر تنزيل نقطة البدء"; exit 6; }
import json, sys, urllib.request
g = json.load(open(sys.argv[1]))
req = urllib.request.Request(g["get"]["last"], headers={"User-Agent": "Mozilla/5.0 (QuranRafiq mushafak1 distill)"})
with urllib.request.urlopen(req, timeout=600) as r, open(sys.argv[2], "wb") as f:
    while True:
        b = r.read(1 << 22)
        if not b: break
        f.write(b)
PYEOF
START_STEP=$(step_of "$BASE/probe/last.pt"); SRC=r2
mkdir -p "$OUT"; cp -f "$BASE/probe/last.pt" "$OUT/last.pt"; rm -rf "$BASE/probe"
say "نقطة البدء: الخطوة $START_STEP (المطلوب ≥ $EXPECT_STEP)"
if (( START_STEP < EXPECT_STEP )); then
  say "⛔ نقطةُ البدء ($START_STEP) دون المتوقَّع ($EXPECT_STEP) — لا تدريب"
  OUTCOME=bad_resume; exit 6
fi

# ── النبضةُ كلَّ 5 دقائق: دفتر + مزامنة احتياطية + حالة + فحص السقف وطلب الإيقاف ──
stop_train() {
  # إيقافٌ نظيف: ملفُّ STOP_NOW يجعل distill.py يحفظ last.pt ثم يخرج 0 فيصدّر distill_run ويرفع؛ ولا قتلَ قبل 12 د
  echo "$1" > "$BASE/stop_reason"
  : > "$OUT/STOP_NOW"
  local i
  for i in $(seq 1 72); do [ -f "$BASE/train.pid" ] || return 0; sleep 10; done
  if [ -f "$BASE/train.pid" ]; then
    local p; p=$(cat "$BASE/train.pid"); kill -TERM -- "-$p" 2>/dev/null || true
    sleep 60; kill -KILL -- "-$p" 2>/dev/null || true
  fi
}
( while true; do
    sleep 300
    tick || say "⚠ نبضة الدفتر أخفقت"
    if sync_state; then SYNC_OK=1; else SYNC_OK=0; say "⚠ مزامنة الدلو أخفقت"; fi
    publish_status running || true
    c=$(cost_of "$(cat "$BASE/ledger_s" 2>/dev/null || echo 0)")
    if over_budget "$c"; then say "بلغ السقفُ (\$$c من \$$BUDGET)"; stop_train budget_stop; break; fi
    if gcloud storage ls "$GSB/stop_request" >/dev/null 2>&1; then say "طُلب الإيقاف"; stop_train stop_request; break; fi
  done ) &
SYNCER=$!
tick || true
publish_status running || true

# ── الشوط ──
rem_h() { awk -v s="$(cat "$BASE/ledger_s" 2>/dev/null || echo "$S0")" -v b="$BUDGET" -v r="$RATE" 'BEGIN{h=(b-s*r/3600)/r; if(h<0.05)h=0.05; printf "%.3f", h}'; }
H=$(rem_h)
mapfile -d '' DARGS < <("$PY" -c 'import json,sys;[sys.stdout.write(str(x)+"\0") for x in json.load(open(sys.argv[1])).get("distill_args", [])]' "$CFG")
say "تشغيل distill_run: session-hours=$H workers=$WORKERS expect=$EXPECT_STEP args=${DARGS[*]}"
set +e
cd "$CODE"
setsid env -u R2_ACCESS_KEY_ID -u R2_SECRET_ACCESS_KEY M1_PLATFORM=vertex \
  "$PY" -u tools/tasmi_model/distill_run.py --grant "$GRANT" --work "$WORK" --inputs "$MIRROR" \
  --session-hours "$H" --budget-hours 0 --workers "$WORKERS" --stall-minutes 20 -- "${DARGS[@]}" &
TP=$!; echo "$TP" > "$BASE/train.pid"
wait "$TP"; TRAIN_RC=$?
set -e
say "distill_run rc=$TRAIN_RC"
TS="$OUT/train_state.json"
REACHED=$("$PY" -c 'import json,sys;print(json.load(open(sys.argv[1])).get("target_reached", False))' "$TS" 2>/dev/null || echo False)
END_STEP=$(step_of "$OUT/last.pt")
if [ -f "$BASE/stop_reason" ]; then OUTCOME=$(cat "$BASE/stop_reason")
elif [ "$TRAIN_RC" = 78 ]; then OUTCOME=early_stop
elif [ "$TRAIN_RC" -ne 0 ]; then OUTCOME=failed
elif [ "$REACHED" = True ]; then OUTCOME=finished
else
  OUTCOME=budget_stop          # انتهى وقتُ الميزانيّة المحسوب قبل اكتمال الدورة
  # لم تتقدّم النقطةُ والميزانيّةُ باقيةٌ ⇒ إخفاقٌ لا سقف
  if ! over_budget "$(cost_of "$(ledger_s)")" && [ "$END_STEP" -le "$START_STEP" ]; then
    say "⛔ لم تتقدّم النقطة عن $START_STEP والميزانيّةُ باقية ⇒ إخفاق"; OUTCOME=failed
  fi
fi
say "نهاية: outcome=$OUTCOME start=$START_STEP end=$END_STEP reached=$REACHED"
rm -f "$BASE/train.pid"
exit 0
