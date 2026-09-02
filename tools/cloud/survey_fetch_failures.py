# -*- coding: utf-8 -*-
"""جرد **قراءةٍ فقط** لسور فشل جلبها في سجلات الأسطول الخمسة.

الفرضية المراد حسمها: هل التغطية المنخفضة سببها **سور ساقطة صامتة** (فشل
جلب) لا ضعفُ المحاذاة؟ فإن كان كذلك فالمرفوض يُكمَّل ناقصه ولا يُعاد كله.

⛔ لا يعدّل شيئاً على الخوادم ولا يعيد تشغيل عملية — أوامره كلها `grep`/`cat`.
   (التعديل لrafiq-fleet وحده؛ هذا سندٌ لقراره لا فعلٌ مكانه.)

    python3 survey_fetch_failures.py
"""
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FLEET = ["2.28.47.206", "2.28.30.204", "2.28.39.88",
         "167.233.228.210", "2.28.35.24"]
KEY = str(Path.home() / ".ssh" / "rafiq_worker")

# سطر الفشل من batch_run.py: "سورة  17: ❌ <السبب>"
REMOTE = (
    "for f in /root/logs/*.log; do "
    "  n=$(basename $f .log); "
    "  fail=$(grep -c '❌' $f 2>/dev/null || echo 0); "
    "  done=$(grep -c '^سورة' $f 2>/dev/null || echo 0); "
    "  bad=$(grep -o 'سورة *[0-9]*: ❌' $f 2>/dev/null "
    "        | grep -o '[0-9]*' | tr '\\n' ',' ); "
    "  echo \"$n|$fail|$done|$bad\"; "
    "done"
)


def ask(host):
    try:
        out = subprocess.run(
            ["ssh", "-i", KEY, "-o", "StrictHostKeyChecking=accept-new",
             "-o", "ConnectTimeout=25", "-o", "BatchMode=yes",
             "root@" + host, REMOTE],
            capture_output=True, text=True, timeout=120, encoding="utf-8",
            errors="replace")
        return host, out.stdout
    except Exception as e:
        return host, "ERR " + str(e)


rows = {}
with ThreadPoolExecutor(5) as ex:
    for host, out in ex.map(ask, FLEET):
        if out.startswith("ERR"):
            print("⚠️ {} تعذّر الوصول: {}".format(host, out[:80]))
            continue
        n = 0
        for line in out.splitlines():
            p = line.strip().split("|")
            if len(p) < 4 or not p[0]:
                continue
            rid, fail, done = p[0], int(p[1] or 0), int(p[2] or 0)
            bad = [int(x) for x in p[3].split(",") if x.strip().isdigit()]
            # ⚠️ سطر النجاح وسطر الفشل كلاهما يبدأ بـ«سورة» في batch_run —
            # فعدّ الكل ناقصاً الفشل، وإلا عُدّ الفاشل ناجحاً وهو أسوأ من
            # لا عدّ: يجمّل الصورة في تقرير يُبنى عليه قرار.
            rows[rid] = {"host": host, "fail": fail,
                         "processed": done, "ok": done - fail,
                         "failedSurahs": sorted(set(bad))}
            n += 1
        print("✅ {} — {} قارئاً".format(host, n))

print("\n=== القراء الذين سقطت لهم سور (مرتَّبون بالأسوأ) ===")
print("| القارئ | الخادم | سور فاشلة | سور نجحت | عولجت | أرقام الساقطة |")
print("|---|---|---:|---:|---:|---|")
bad = sorted([(k, v) for k, v in rows.items() if v["fail"]],
             key=lambda kv: -kv[1]["fail"])
for rid, v in bad:
    nums = ",".join(str(x) for x in v["failedSurahs"][:14])
    if len(v["failedSurahs"]) > 14:
        nums += "…"
    print("| `{}` | {} | **{}** | {} | {} | {} |".format(
        rid, v["host"].split(".")[-1], v["fail"], v["ok"], v["processed"],
        nums))

clean = [k for k, v in rows.items() if not v["fail"]]
print("\nالحصيلة: {} قارئاً سقطت لهم سور · {} بلا سقوط · {} مجموع.".format(
    len(bad), len(clean), len(rows)))
import os
OUT = os.environ.get("SURVEY_OUT", "survey_fetch_failures.json")
json.dump(rows, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("التفصيل: " + OUT)
