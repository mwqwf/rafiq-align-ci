#!/usr/bin/env bash
# سكربت تدريب «مصحفك-1» داخل مهمة Vertex AI CustomJob (L4×2). يكيّف train_startup.sh (مسار GCE) ولا يستبدله.
# يُنزَّل من gs://<bucket>/run/vertex_train.sh ويُشغَّل بأمر الحاوية. الإعدادات من gs://<bucket>/run/config.json
# (لا metadata): bucket · project · expect_step · rate · budget_usd · workers · data_tag · parts · grade · pub_base · d1_parts · torch_pin
# والمرحلةُ بروابط R2 موقّعة في gs://<bucket>/run/stage_urls.json (دلوٌ خاصّ) وتُنسخ مرّةً إلى الدلو.
# لا حذفَ ذاتيّاً ولا shutdown: المهمةُ تنتهي بخروج هذا السكربت. يكتب done عند finished/budget_stop/stop_request/failed_final.
# قطعُ spot أو SIGTERM بلا done ⇒ يخرج 0 ويعيد watch الإطلاق.
# ⛔ لا set -x ولا طباعة لرابطٍ موقّع؛ الروابط تُمرَّر إلى curl عبر stdin لا سطر الأوامر.
set -euo pipefail

BASE=/var/lib/mushafak1
STAGE=$BASE/stage
CODE=/opt/mushafak1/code
IN=$BASE/input
MIRROR=$IN/mirror
WORK=$BASE/work
STATE=$BASE/state
LIB=$BASE/lib
LOG=$BASE/mushafak1.log
mkdir -p "$BASE" "$IN" "$MIRROR" "$WORK" "$STATE" "$LIB" /opt/mushafak1
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
EXPECT_STEP=$(cfg expect_step "")
RATE=$(cfg rate "")
BUDGET=$(cfg budget_usd "")
WORKERS=$(cfg workers 10)
DATA_TAG=$(cfg data_tag d2)
PARTS=$(cfg parts 17)
GRADE=$(cfg grade m1)
PUB=$(cfg pub_base https://pub-2c2e1dcd92e84a2898820dd38d3e09e6.r2.dev)
D1_PARTS=$(cfg d1_parts "h 00 01 02 03 04 05 06 07 08 09 10 11 12 13 14 15")
TORCH_PIN=$(cfg torch_pin 2.10.0)
[[ "$EXPECT_STEP" =~ ^[0-9]+$ ]] || { say "⛔ expect-step غير رقميّ"; exit 2; }
[[ "$RATE" =~ ^[0-9]+([.][0-9]+)?$ && "$BUDGET" =~ ^[0-9]+([.][0-9]+)?$ ]] || { say "⛔ rate/budget غير رقميّين"; exit 2; }

GS=$GSB/m1
CK=$STATE/ckpt/$GRADE
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
# usage: fetch.py stage <urls.json> <dest>   |   fetch.py verify <dest>   |   fetch.py d1 <pubbase> <dest> <parts...>
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
mode = sys.argv[1]
if mode == "stage": ok = stage(sys.argv[2], sys.argv[3])
elif mode == "verify": ok = verify(sys.argv[2])
else: ok = d1(sys.argv[2], sys.argv[3], sys.argv[4:])
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
  local tmp="$BASE/status_pub.json" s; s=$(cat "$BASE/ledger_s" 2>/dev/null || echo 0)
  "$PY" - "$CK" "$1" "$TRAIN_RC" "$SYNC_OK" "$START_STEP" "$SRC" "$INSTANCE" "$s" "$(cost_of "$s")" "$BUDGET" "$RATE" "$TORCH_V" > "$tmp" <<'PYEOF'
import sys, json, re, os, time
ck, stage, trc, sync_ok, start_step, src, inst, secs, cost, budget, rate, tv = sys.argv[1:13]
st = {}
try: st = json.load(open(os.path.join(ck, "status.json")))
except Exception: pass
m = re.search(r"(?:STEP|DONE step) (\d+)", st.get("last_step") or "")
ckstep = None
try:
    import torch
    p = os.path.join(ck, "last.pt")
    if os.path.exists(p): ckstep = int(torch.load(p, map_location="cpu", weights_only=False, mmap=True).get("step", -1))
except Exception: pass
print(json.dumps({"platform": "vertex", "instance": inst, "stage": stage, "phase": st.get("phase"),
    "last_step": int(m.group(1)) if m else None, "ckpt_step": ckstep, "start_step": int(start_step),
    "resumed_from": src, "train_rc": int(trc), "sync_ok": sync_ok == "1", "torch": tv,
    "hours": round(int(secs) / 3600, 2), "cost_usd": float(cost), "budget_usd": float(budget), "rate_usd_per_hour": float(rate),
    "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, ensure_ascii=False, indent=1))
PYEOF
  gcloud storage cp -q "$tmp" "$GSB/vm_status.json"
}

# ── المهلةُ الصلبة: تقطع الشوطَ إن علق شيءٌ (ميزانيّةٌ باقية + ساعتان) ──
S0=$(ledger_s)
REM_H=$(awk -v s="$S0" -v b="$BUDGET" -v r="$RATE" 'BEGIN{h=(b-s*r/3600)/r; if(h<0)h=0; printf "%.3f", h}')
MAIN=$$
( sleep "$(awk -v h="$REM_H" 'BEGIN{printf "%d", (h+2)*3600}')"; echo "$(date -u +%FT%TZ) ⛔ WATCHDOG"; echo budget_stop > "$BASE/stop_reason"; kill -TERM "$MAIN" ) &
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
      # قطعُ spot أو SIGTERM: الحملةُ باقية، والمراقبُ (watch) يعيد الإطلاق
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
    # TERM بلا سببٍ مكتوب = قطعُ spot أو إلغاءُ المهمة أو انقضاءُ مهلتها
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
# فحصُ استيرادِ ما يحمّله عمّالُ البيانات قبل أيّ تنزيل: الخطأ هنا مجّانيّ، وفي الشوط يضيع وقتَ البطاقات
"$PY" -c 'import numpy, pyarrow, pyarrow.parquet, soundfile, kaldi_native_fbank, onnxruntime; print("numpy", numpy.__version__, "pyarrow", pyarrow.__version__)' \
  || { say "⛔ مكتباتُ البيانات لا تُستورد"; OUTCOME=failed; exit 3; }

# ── المرحلة: تنزيلٌ مرّةً واحدة بتحقّق sha256 ثمّ نسخٌ إلى الدلو (تبقى بعد انتهاء الروابط) ──
if [ ! -f "$BASE/.stage_ok" ]; then
  if gcloud storage ls "$GSB/stage/.complete" >/dev/null 2>&1; then
    say "المرحلةُ من نسخة الدلو"
    gcloud storage rsync -r --no-user-output-enabled "$GSB/stage" "$STAGE"
    "$PY" "$LIB/fetch.py" verify "$STAGE" || { say "⛔ نسخةُ المرحلة في الدلو تالفة"; OUTCOME=bad_stage; exit 7; }
  else
    gcloud storage cp -q "$RUN_URI/stage_urls.json" "$BASE/stage_urls.json" || { say "⛔ لا stage_urls.json في الدلو"; exit 7; }
    "$PY" "$LIB/fetch.py" stage "$BASE/stage_urls.json" "$STAGE" || { say "⛔ تنزيلُ المرحلة أخفق"; exit 7; }
    rm -f "$BASE/stage_urls.json"
    gcloud storage rsync -r --no-user-output-enabled "$STAGE" "$GSB/stage"
    echo ok > "$BASE/.c"; gcloud storage cp -q "$BASE/.c" "$GSB/stage/.complete"
  fi
  touch "$BASE/.stage_ok"
fi
say "stage: $(find "$STAGE" -type f | wc -l) ملفاً"

# ── الشيفرة ──
if [ ! -f "$BASE/.code_ok" ]; then
  rm -rf "$CODE"; mkdir -p "$CODE"; cp -a "$STAGE/code/." "$CODE/"
  [ -f "$CODE/code.zip" ] && (cd "$CODE" && "$PY" -m zipfile -e code.zip . && rm code.zip)
  touch "$BASE/.code_ok"
fi
CR=$(find "$CODE" -path '*/tools/tasmi_model/cloud_run.py' | head -1)
[ -n "$CR" ] || { say "⛔ الشيفرة بلا cloud_run.py"; OUTCOME=bad_stage; exit 5; }
CODE=${CR%/tools/tasmi_model/cloud_run.py}

# ── البيانات: d1 من r2.dev + جزء 16 وeligible من d2delta في المجلّد نفسه (الوسم d2 يبحث بالاسم المجرّد) ──
if [ ! -f "$BASE/.data_ok" ]; then
  # shellcheck disable=SC2086
  "$PY" "$LIB/fetch.py" d1 "$PUB" "$MIRROR" $D1_PARTS || { say "⛔ تنزيلُ d1 أخفق"; exit 8; }
  [ -d "$STAGE/d2delta" ] || { say "⛔ لا d2delta في المرحلة"; OUTCOME=bad_stage; exit 8; }
  find "$STAGE/d2delta" -type f -exec cp -f {} "$MIRROR/" \;
  [ -f "$MIRROR/eligible.json" ] && [ -f "$MIRROR/part_16.tar" ] || { say "⛔ d2delta ناقصة (eligible.json/part_16.tar)"; OUTCOME=bad_stage; exit 8; }
  touch "$BASE/.data_ok"
fi
df -h "$BASE" | tail -1

# ── نقطة الاستئناف: المحلية فـGCS فـstage (الأكبرُ خطوةً يغلب، وعند التعادل الأسبقُ في الترتيب) ──
mkdir -p "$CK"
LSTEP=$(step_of "$CK/last.pt")
GSTEP=-1
if gcloud storage ls "$GS/last.pt" >/dev/null 2>&1; then
  mkdir -p "$BASE/probe"; gcloud storage cp -q "$GS/last.pt" "$BASE/probe/last.pt"
  GSTEP=$(step_of "$BASE/probe/last.pt"); rm -rf "$BASE/probe"
fi
SDIR="$STAGE/ckpt/state/ckpt/$GRADE"
SSTEP=$(step_of "$SDIR/last.pt")
say "خطوات: محلي=$LSTEP دلو=$GSTEP مرحلة=$SSTEP (المطلوب ≥ $EXPECT_STEP)"
BEST=$LSTEP; SRC=local
(( GSTEP > BEST )) && { BEST=$GSTEP; SRC=gcs; }
(( SSTEP > BEST )) && { BEST=$SSTEP; SRC=stage; }
case "$SRC" in
  gcs)   say "الاستئناف من الدلو"; gcloud storage rsync -r --no-user-output-enabled "$GS" "$CK" ;;
  stage) say "الاستئناف من المرحلة"; cp -f "$SDIR"/* "$CK/" ;;
esac
[ -f "$CK/run.json" ] || [ ! -f "$SDIR/run.json" ] || cp -n "$SDIR/run.json" "$CK/run.json"
START_STEP=$BEST
if (( BEST < EXPECT_STEP )); then
  say "⛔ أحدثُ نقطةٍ ($BEST) دون المتوقَّع ($EXPECT_STEP) — لا تدريب"
  OUTCOME=bad_resume; exit 6
fi

# ── النبضةُ كلَّ 5 دقائق: دفتر + مزامنة + حالة + فحص السقف وطلب الإيقاف ──
stop_train() {
  echo "$1" > "$BASE/stop_reason"
  if [ -f "$BASE/train.pid" ]; then
    local p; p=$(cat "$BASE/train.pid"); kill -TERM -- "-$p" 2>/dev/null || true
    sleep 90; kill -KILL -- "-$p" 2>/dev/null || true
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
say "تشغيل cloud_run: max-hours=$H workers=$WORKERS data=$DATA_TAG parts=$PARTS expect=$EXPECT_STEP"
set +e
cd "$CODE"
setsid env -u R2_ACCESS_KEY_ID -u R2_SECRET_ACCESS_KEY M1_PLATFORM=vertex \
  "$PY" -u tools/tasmi_model/cloud_run.py --grade "$GRADE" --work "$WORK" --local-state "$STATE" --inputs "$IN" \
  --max-hours "$H" --workers "$WORKERS" --stall-minutes 20 --data-tag "$DATA_TAG" --parts "$PARTS" \
  --expect-step "$EXPECT_STEP" &
TP=$!; echo "$TP" > "$BASE/train.pid"
wait "$TP"; TRAIN_RC=$?
set -e
say "cloud_run rc=$TRAIN_RC"
PHASE=$("$PY" -c 'import json,sys;print(json.load(open(sys.argv[1])).get("phase",""))' "$CK/status.json" 2>/dev/null || echo "")
if [ -f "$BASE/stop_reason" ]; then OUTCOME=$(cat "$BASE/stop_reason")
elif [ "$TRAIN_RC" -ne 0 ]; then OUTCOME=failed
else
  case "$PHASE" in
    done)    OUTCOME=finished ;;
    stopped) OUTCOME=stopped ;;
    *)       OUTCOME=budget_stop ;;     # paused: انتهى وقتُ الميزانيّة المحسوب
  esac
  # cloud_run يسمّي سقوطَ train.py «PAUSED» ويخرج 0؛ فإن لم تتقدّم النقطةُ والميزانيّةُ باقيةٌ فهو إخفاقٌ لا سقف
  if [ "$OUTCOME" = budget_stop ] && ! over_budget "$(cost_of "$(ledger_s)")" \
     && [ "$(step_of "$CK/last.pt")" -le "$START_STEP" ]; then
    say "⛔ لم تتقدّم النقطة عن $START_STEP والميزانيّةُ باقية ⇒ إخفاق"; OUTCOME=failed
  fi
fi
rm -f "$BASE/train.pid"
exit 0
