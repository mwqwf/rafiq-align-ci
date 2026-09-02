#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يرصد أيّ كتابةٍ جديدة على الدلو بعد لحظةٍ معلومة — شاهدُ حياةٍ للأسطول.

    python tools/index_qa/bucket_watch.py --since 2026-09-02T06:04:00Z [--follow 120]

**لماذا؟** انقطع SSH عن الخوادم الخمسة، فلا يُعرف أهي **حيّةٌ بلا وصول** أم
**ميتة**. والدلو يفصل بينهما: عمليةٌ حيّة تكتب، وميتةٌ لا تكتب. فالكتابة شاهدُ
حياةٍ لا يحتاج إذناً من الخادم.

⛔ ولا يُقرأ الصمت حياةً: غيابُ الكتابة **دليلٌ على الموت أو على الانتظار**،
ولا يُفصل بينهما إلا بمعرفة ما كان الأسطول يعمله لحظتَه.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                 # noqa: BLE001
        pass

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import promote                                                       # noqa: E402

# **بادئاتُ الأسطول وحدها** حين يكون السؤال «أحيٌّ هو؟»: `claims/` لا يكتبها
# غيره، و`timings-staging/` مخرجُه. ⛔ ولا تُحسب `timings/` ولا `manifest` ولا
# `frozen.txt`: **أنا** أكتبها عند كل ترقية، فتُقرأ حياةً للأسطول وهي أثرُ يدي
# — وذاك أسوأ من الصمت لأنه صمتٌ يبدو كلاماً. وكذلك `catalog/` يكتبها تابعُ
# github-12 محلياً.
FLEET_PREFIXES = ("claims/", "timings-staging/")
PREFIXES = FLEET_PREFIXES


def scan(cl, bucket, since):
    fresh = []
    for prefix in PREFIXES:
        for page in cl.get_paginator("list_objects_v2").paginate(
                Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                if obj["LastModified"] > since:
                    fresh.append((obj["LastModified"], obj["Key"], obj["Size"]))
    fresh.sort()
    return fresh


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", required=True, help="ISO ‏UTC مثل 2026-09-02T06:04:00Z")
    ap.add_argument("--follow", type=int, default=0, help="ثوانٍ بين الجولات")
    ap.add_argument("--until", type=int, default=0, help="دقائق ثم يتوقف")
    ap.add_argument("--all-prefixes", action="store_true",
                    help="ارصد كل البادئات لا بادئات الأسطول وحدها")
    a = ap.parse_args()
    since = dt.datetime.fromisoformat(a.since.replace("Z", "+00:00"))
    global PREFIXES
    if a.all_prefixes:
        PREFIXES = ("claims/", "timings/", "timings-staging/", "wordtimings/",
                    "catalog/", "audio/")
    cl, bucket = promote.s3()
    deadline = time.time() + a.until * 60 if a.until else None
    while True:
        fresh = scan(cl, bucket, since)
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%H:%M:%SZ")
        if fresh:
            print(f"[{stamp}] **كتابةٌ جديدة بعد {a.since}: {len(fresh)}**", flush=True)
            for when, key, size in fresh[:12]:
                print(f"    {when:%H:%M:%SZ}  {key}  ({size} بايت)", flush=True)
            return 0
        print(f"[{stamp}] لا كتابة بعد {a.since} — صمتٌ تامّ على "
              f"{len(PREFIXES)} بادئات", flush=True)
        if not a.follow or (deadline and time.time() >= deadline):
            return 1
        time.sleep(a.follow)


if __name__ == "__main__":
    sys.exit(main())
