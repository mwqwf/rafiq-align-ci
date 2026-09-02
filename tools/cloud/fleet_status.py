#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""حالة الأسطول في مخرج واحد — يُشغَّل من جهاز المالك.

    python tools/cloud/fleet_status.py            # تقرير كامل
    python tools/cloud/fleet_status.py --brief    # سطر لكل خادم
    python tools/cloud/fleet_status.py --json     # للأتمتة

القاعدة الحاكمة: **الخادم قد يكذب والدلو لا.** ما يعدّه الخادم في
`/root/done/` نيّةُ عملٍ تمّ محلياً؛ والحقيقة الوحيدة أن الفهرس **مرفوع إلى
R2** — فالتقرير يعرض الاثنين ويصيح إن اختلفا.

⛔ لا يعدّل هذا السكربت شيئاً على الخوادم ولا في الدلو: قراءةٌ محضة. إعادة
التشغيل والقتل أفعالٌ منفصلة بقرار إنسان (‏`/root/restart.sh`).
"""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# ⚠️ صفحة ترميز ويندوز الافتراضية (cp1256) تعجز عن الرموز والعربية معاً،
# فتنهار الأداة عند الطباعة لا عند العمل — يُثبَّت المخرج على UTF-8 أولاً.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

ROOT = Path(__file__).resolve().parents[2]
RECITERS_TSV = ROOT / "tools" / "cloud" / "reciters.tsv"
R2_CREDS = ROOT / "secure" / "r2_credentials.json"
SSH_KEY = Path.home() / ".ssh" / "rafiq_worker"

# الشريحة = ترتيب الخادم في هذه القائمة (SHARD)، والمجموع SHARDS
FLEET = [
    "2.28.47.206",
    "2.28.30.204",
    "2.28.39.88",
    "167.233.228.210",
    "2.28.35.24",
]

STALL_MINUTES = 90  # قارئ بلا تقدم أطول من هذا = تعليق مشتبه به
# ⚠️ درس 2026-09-01: 45ث أعلنت خادماً سليماً ساقطاً (حمل ~11 ونت المالك ضعيف)،
# والإنذار الكاذب يُدرّب المشغّل على تجاهل الإنذار الصادق. مهلة أسخى ومحاولة
# ثانية قبل إعلان السقوط — فالسقوط الحقيقي يبقى مرئياً وتختفي الضوضاء.
SSH_TIMEOUT = 90
SSH_RETRIES = 2

# أمرٌ واحد لكل خادم — جولة ذهاب وإياب واحدة بدل ست.
#
# ⚠️ **حيلة القوس `[r]un_fleet` ليست زينة**: نمطُ `pgrep -f` يفحص سطور أوامر
# كل العمليات، **وسطرُ أمرنا نحن من بينها** — فأمرٌ يحمل الاسم صريحاً يعدّ
# نفسه فيقول «سائقان» والحقيقة سائق واحد. وقع ذلك فعلاً في أول تشغيل، وكاد
# يُبلَّغ تكراراً وهمياً على الأسطول كله. والقوس يكسر التطابق الذاتي لأن
# السطر يحمل `[r]un_fleet` لا `run_fleet`. (وهو نفس سبب درس `pkill` الذي
# قتل جلسة ssh نفسها.)
REMOTE_PROBE = r"""
echo "DONE=$(ls /root/done 2>/dev/null | wc -l)"
echo "DONE_LIST=$(ls /root/done 2>/dev/null | tr '\n' ',')"
echo "WHISPER=$(pgrep -fc '[w]hisper-cli' 2>/dev/null || echo 0)"
echo "DRIVERS=$(pgrep -fc '[r]un_fleet' 2>/dev/null || echo 0)"
echo "LOAD=$(cut -d' ' -f1-3 /proc/loadavg)"
echo "DISK_FREE_GB=$(df -BG --output=avail /root | tail -1 | tr -dc '0-9')"
echo "UPTIME_MIN=$(awk '{printf "%d", $1/60}' /proc/uptime)"
echo "NEWEST_DONE_AGE_MIN=$(find /root/done -type f -printf '%T@\n' 2>/dev/null | sort -n | tail -1 | awk -v now=$(date +%s) '{printf "%d", (now-$1)/60}')"
echo "WORK_DIRS=$(ls -1 /root/work 2>/dev/null | tr '\n' ',')"
echo "CREDS=$([ -f /root/QuranRafiq/secure/r2_credentials.json ] && echo 1 || echo 0)"
echo "ORPHAN_JZ=$(for f in /root/QuranRafiq/tools/alignment/work/timings_*.jz; do [ -e "$f" ] || continue; [ "$(stat -c %s "$f")" -gt 20480 ] || continue; b=$(basename "$f" .jz); rid=${b#timings_*_}; [ -e "/root/done/$rid" ] || printf '%s,' "$rid"; done)"
echo "LOG_TAIL=$(tail -c 300 /root/fleet.log 2>/dev/null | tr '\n' '|' | tr -d '\r')"
"""


def read_reciters() -> list[str]:
    ids = []
    for line in RECITERS_TSV.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        ids.append(line.split("\t")[0].strip())
    return ids


def probe(host: str) -> dict:
    """يستجوب خادماً واحداً. الفشل حالةٌ تُبلَّغ لا استثناء يُسقط التقرير."""
    cmd = [
        "ssh", "-i", str(SSH_KEY),
        "-o", "StrictHostKeyChecking=no",
        "-o", "BatchMode=yes",
        "-o", f"ConnectTimeout={SSH_TIMEOUT}",
        f"root@{host}", REMOTE_PROBE,
    ]
    started = time.time()
    # محاولة ثانية قبل إعلان السقوط: تعذُّرٌ عابر ليس خادماً ساقطاً.
    out = None
    last_err = "فشل ssh"
    for attempt in range(SSH_RETRIES):
        try:
            out = subprocess.run(
                cmd, capture_output=True, text=True, timeout=SSH_TIMEOUT + 20,
            )
        except subprocess.TimeoutExpired:
            out, last_err = None, "مهلة الاتصال انتهت"
        else:
            if out.returncode == 0:
                break
            err = (out.stderr or "").strip().splitlines()
            last_err = err[-1] if err else "فشل ssh"
            out = None
        if attempt + 1 < SSH_RETRIES:
            time.sleep(5)
    if out is None:
        return {"host": host, "reachable": False,
                "error": f"{last_err} (بعد {SSH_RETRIES} محاولتين)"}

    kv = {}
    for line in out.stdout.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            kv[k.strip()] = v.strip()

    def num(key, default=0):
        m = re.search(r"-?\d+", kv.get(key, ""))
        return int(m.group()) if m else default

    done_list = [x for x in kv.get("DONE_LIST", "").split(",") if x]
    work_dirs = [x for x in kv.get("WORK_DIRS", "").split(",") if x]
    # ⚠️ الاسم مشتقّ في الخادم من `timings_{riwaya}_{rid}.jz` بحذف البادئة
    # والرواية، فيطابق وسم `/root/done/{rid}` حرفاً بحرف. (المحاولة الأولى
    # قارنت باللاحقة داخل `case` وسط `$( )` فكسر القوسُ التحليلَ وأنتج
    # يتيماً كاذباً لقارئ مرفوع فعلاً — لا `case` هنا بعد اليوم.)
    orphans = [x for x in kv.get("ORPHAN_JZ", "").split(",") if x]
    return {
        "creds": num("CREDS"),
        "orphan_jz": orphans,
        "host": host,
        "reachable": True,
        "rtt_s": round(time.time() - started, 1),
        "done": num("DONE"),
        "done_list": done_list,
        "whisper": num("WHISPER"),
        "drivers": num("DRIVERS"),
        "load": kv.get("LOAD", "?"),
        "disk_free_gb": num("DISK_FREE_GB"),
        "uptime_min": num("UPTIME_MIN"),
        "idle_min": num("NEWEST_DONE_AGE_MIN", -1),
        "running": work_dirs,
        "log_tail": kv.get("LOG_TAIL", "")[-160:],
    }


def r2_uploaded() -> tuple[set[str], str | None]:
    """يعدّ الفهارس المرفوعة فعلاً — الحقيقة التي لا تكذب."""
    try:
        import boto3  # noqa: PLC0415
    except ImportError:
        return set(), "boto3 غير مثبّتة — تعذّر التحقق من الدلو"
    if not R2_CREDS.exists():
        return set(), f"لا اعتماد R2 في {R2_CREDS}"
    c = json.loads(R2_CREDS.read_text(encoding="utf-8"))
    try:
        s3 = boto3.client(
            "s3",
            endpoint_url=c.get("endpoint") or f"https://{c['accountId']}.r2.cloudflarestorage.com",
            aws_access_key_id=c["accessKeyId"],
            aws_secret_access_key=c["secretAccessKey"],
            region_name="auto",
        )
        found = set()
        token = None
        while True:
            kw = {"Bucket": c["bucket"], "Prefix": "timings/"}
            if token:
                kw["ContinuationToken"] = token
            page = s3.list_objects_v2(**kw)
            for obj in page.get("Contents", []):
                # timings/{riwaya}/{reciterId}.jz
                parts = obj["Key"].split("/")
                if len(parts) >= 3 and parts[-1].endswith(".jz"):
                    found.add(parts[-1][: -len(".jz")])
            if not page.get("IsTruncated"):
                break
            token = page.get("NextContinuationToken")
        return found, None
    except Exception as exc:  # noqa: BLE001 — الفشل يُبلَّغ ولا يُسقط التقرير
        return set(), f"تعذّر قراءة الدلو: {exc}"


def build_report() -> dict:
    reciters = read_reciters()
    with futures.ThreadPoolExecutor(max_workers=len(FLEET)) as pool:
        servers = list(pool.map(probe, FLEET))
    uploaded, r2_error = r2_uploaded()
    in_fleet = [r for r in reciters if r in uploaded]

    warnings = []
    for i, s in enumerate(servers):
        s["shard"] = i
        if not s["reachable"]:
            warnings.append(f"⛔ الخادم {s['host']} (شريحة {i}) لا يستجيب: {s['error']} — يستحق `/root/restart.sh`")
            continue
        if s["drivers"] > 1:
            warnings.append(
                f"⛔ الخادم {s['host']}: {s['drivers']} سائقين لـrun_fleet.py — تكرارٌ يضاعف الحمل ويجب إنهاء الزائد"
            )
        if s["drivers"] == 0:
            warnings.append(f"⛔ الخادم {s['host']}: لا سائق يعمل — العمل متوقف، يستحق `/root/restart.sh`")
        if s["whisper"] == 0 and s["drivers"] >= 1:
            warnings.append(f"⚠️ الخادم {s['host']}: سائقٌ بلا عمليات whisper — قد يكون بين قارئين أو معلقاً")
        if 0 <= s["idle_min"] > STALL_MINUTES:
            warnings.append(
                f"⚠️ الخادم {s['host']}: لا قارئ اكتمل منذ {s['idle_min']} دقيقة (الحد {STALL_MINUTES}) — تعليق مشتبه به"
            )
        # درس 2026-09-01: غياب هذا الملف يجعل كل قارئ يُفهرَس ثم يفشل رفعه بصمت
        # ساعاتٍ — والعدّاد يبدو عالقاً بلا سبب ظاهر. فحصٌ دائم لا استقصاء لاحق.
        if not s["creds"]:
            warnings.append(
                f"⛔ الخادم {s['host']}: لا `secure/r2_credentials.json` — كل رفع سيفشل "
                f"بعد الفهرسة؛ يُعاد إنشاؤه من `/root/.r2env` (`/root/restart.sh` يفعلها)"
            )
        if s["orphan_jz"]:
            warnings.append(
                f"⚠️ الخادم {s['host']}: {len(s['orphan_jz'])} فهرساً يتيماً (فُهرس ولم يُرفع) — "
                f"{', '.join(s['orphan_jz'][:4])} — يُرفع بـ`upload_timings.py --index` (يمرّ بالحُرّاس) بلا إعادة فهرسة"
            )
        if s["disk_free_gb"] and s["disk_free_gb"] < 20:
            warnings.append(f"⚠️ الخادم {s['host']}: القرص الحر {s['disk_free_gb']}ج.ب — الحارس يتوقف تحت الحد")

    # الفارق بين ما يدّعيه الخادم وما في الدلو
    claimed = sum(s.get("done", 0) for s in servers if s.get("reachable"))
    if not r2_error and claimed > len(in_fleet):
        warnings.append(
            f"⚠️ الخوادم تدّعي {claimed} منجزاً والدلو فيه {len(in_fleet)} — الفارق رفعٌ لم يتم أو علامة كاذبة"
        )

    # التقدير بالمعدل المقيس: أطول تشغيل ÷ ما أنجزه فعلاً
    rate_per_hour = 0.0
    for s in servers:
        if s.get("reachable") and s.get("uptime_min", 0) > 30 and s.get("done", 0) > 0:
            rate_per_hour += s["done"] / (s["uptime_min"] / 60.0)
    remaining = len(reciters) - len(in_fleet)
    eta_hours = round(remaining / rate_per_hour, 1) if rate_per_hour > 0 else None

    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "servers": servers,
        "reciters_total": len(reciters),
        "uploaded_count": len(in_fleet),
        "remaining": remaining,
        "claimed_done": claimed,
        "r2_error": r2_error,
        "rate_per_hour": round(rate_per_hour, 2),
        "eta_hours": eta_hours,
        "warnings": warnings,
    }


def render(rep: dict, brief: bool = False) -> str:
    out = []
    out.append(f"🛰️  حالة أسطول رفيق — {rep['generated_at']}")
    out.append("")
    for s in rep["servers"]:
        if not s["reachable"]:
            out.append(f"  ⛔ شريحة {s['shard']} · {s['host']:<16} لا يستجيب ({s['error']})")
            continue
        flag = "⛔" if (s["drivers"] != 1 or not s["creds"]) else ("⚠️" if (s["whisper"] == 0 or s["orphan_jz"]) else "✅")
        out.append(
            f"  {flag} شريحة {s['shard']} · {s['host']:<16} "
            f"منجز {s['done']:>3} · whisper {s['whisper']} · سائق {s['drivers']} · "
            f"حمل {s['load']} · قرص {s['disk_free_gb']}ج.ب · آخر إنجاز قبل {s['idle_min']}د"
            + ("" if s["creds"] else " · 🔑 لا اعتماد R2")
            + (f" · 🧩 يتيم {len(s['orphan_jz'])}" if s["orphan_jz"] else "")
        )
        if not brief and s["running"]:
            out.append(f"       جارٍ: {', '.join(s['running'][:4])}")
    out.append("")
    if rep["r2_error"]:
        out.append(f"  ⚠️ الحقيقة من الدلو غير متاحة: {rep['r2_error']}")
    else:
        pct = rep["uploaded_count"] * 100 // max(1, rep["reciters_total"])
        out.append(
            f"  📦 الحقيقة من R2: {rep['uploaded_count']}/{rep['reciters_total']} مرفوعاً ({pct}٪) · "
            f"ادّعاء الخوادم {rep['claimed_done']}"
        )
    if rep["eta_hours"] is not None:
        out.append(f"  ⏳ المتبقي {rep['remaining']} قارئاً · بمعدل {rep['rate_per_hour']}/ساعة ⇒ ~{rep['eta_hours']} ساعة")
    else:
        out.append(f"  ⏳ المتبقي {rep['remaining']} قارئاً · لا معدل مقيس بعد")
    if rep["warnings"]:
        out.append("")
        out.append("  ── ما يحتاج تدخلاً ──")
        for w in rep["warnings"]:
            out.append(f"  {w}")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="حالة أسطول الفهرسة")
    ap.add_argument("--json", action="store_true", help="مخرج JSON للأتمتة")
    ap.add_argument("--brief", action="store_true", help="سطر لكل خادم")
    args = ap.parse_args()

    if not SSH_KEY.exists():
        print(f"⛔ مفتاح الدخول غير موجود: {SSH_KEY}", file=sys.stderr)
        return 2

    rep = build_report()
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print(render(rep, brief=args.brief))
    # رمز الخروج: 1 إن كان ثمة ما يحتاج تدخلاً — كي تصلح المراقبة الآلية عليه
    return 1 if rep["warnings"] else 0


if __name__ == "__main__":
    sys.exit(main())
