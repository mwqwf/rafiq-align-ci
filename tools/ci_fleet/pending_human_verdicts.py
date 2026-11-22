#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""جرد سريع لشواهد state-ci التي تنتظر قراراً بشريّاً.

الخطوة القديمة في النبّاض كانت تنزّل كلّ ملفّ حكمٍ واحداً تلو الآخر بلا سقف زمني،
فتجاوزت مهلة الوظيفة (25د) وأُلغي الشوط بعد نجاح الترقية — فتبدو التشغيلات
«ملغاة» وليست كذلك بسبب مجموعة التزامن (cancel-in-progress: false).

هذا الجرد يقرأ الأحدث أولاً بتوازٍ محدود، ويتوقف عند الميزانية الزمنية، ويعلن
إن كان الجرد جزئياً. لا يكتب في الدلو ولا يغيّر حكماً.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CREDS = ROOT / "secure" / "r2_credentials.json"


def classify(verdict) -> str:
    v = str(verdict or "")
    if v.startswith("مقبول"):
        return "مقبول"
    if "بنيوي" in v:
        return "خلل بنيوي"
    if "جسيم" in v:
        return "عطبٌ جسيم"
    if "حدّي" in v:
        return "حدّي"
    if "موقوف" in v:
        return "موقوف"
    return "آخر"


def list_state_objects(s3, bucket: str, prefix: str = "state-ci"):
    objects = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents") or []:
            objects.append({"Key": obj["Key"], "LastModified": obj.get("LastModified")})
    objects.sort(key=lambda o: o["LastModified"] or 0, reverse=True)
    return objects


def fetch_verdict(s3, bucket: str, key: str):
    body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    data = json.loads(body)
    return classify(data.get("verdict"))


def scan(s3, bucket: str, budget_sec: float = 90, workers: int = 16, prefix: str = "state-ci"):
    started = time.monotonic()
    objects = list_state_objects(s3, bucket, prefix)
    listed = len(objects)
    list_sec = time.monotonic() - started
    pending = collections.Counter()
    accepted = 0
    errors = 0
    scanned = 0
    truncated = False
    deadline = started + budget_sec

    def remaining():
        return deadline - time.monotonic()

    # نزّل الأحدث أولاً؛ إن ضاق الوقت يُعلن الجرد جزئياً ولا يُترك الشوط معلّقاً.
    idx = 0
    while idx < listed:
        if remaining() <= 0.5:
            truncated = True
            break
        batch_end = min(listed, idx + max(1, workers))
        batch = objects[idx:batch_end]
        idx = batch_end
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futs = {pool.submit(fetch_verdict, s3, bucket, o["Key"]): o["Key"] for o in batch}
            for fut in as_completed(futs, timeout=max(1, remaining())):
                try:
                    kind = fut.result()
                except Exception:
                    errors += 1
                    scanned += 1
                    continue
                scanned += 1
                if kind == "مقبول":
                    accepted += 1
                else:
                    pending[kind] += 1
        if remaining() <= 0.5 and idx < listed:
            truncated = True
            break

    return {
        "listed": listed,
        "scanned": scanned,
        "accepted": accepted,
        "errors": errors,
        "pending": dict(pending),
        "truncated": truncated,
        "list_sec": round(list_sec, 2),
        "elapsed_sec": round(time.monotonic() - started, 2),
    }


def render(result: dict) -> str:
    lines = ["## ⚡ ما ينتظر قراراً"]
    pending = result["pending"]
    if pending:
        for kind, n in sorted(pending.items(), key=lambda kv: (-kv[1], kv[0])):
            lines.append(f"- {kind}: {n} شاهداً")
    else:
        lines.append("- لا شاهدَ معلّقاً في العيّنة الممسوحة")
    lines.append(
        f"- مُسِح {result['scanned']}/{result['listed']} شاهداً "
        f"(مقبول {result['accepted']} · تعذّر {result['errors']} · "
        f"{result['elapsed_sec']}ث)"
    )
    if result["truncated"]:
        lines.append("- ⚠️ الجرد جزئي بسبب سقف الزمن — الأحدث أولاً، والباقي يُستأنف في النبضة التالية")
    return "\n".join(lines) + "\n"


def default_client():
    import boto3
    creds = json.loads(CREDS.read_text(encoding="utf-8"))
    client = boto3.client(
        "s3",
        endpoint_url=creds["endpoint"],
        aws_access_key_id=creds["accessKeyId"],
        aws_secret_access_key=creds["secretAccessKey"],
        region_name="auto",
    )
    return client, creds["bucket"]


def main(argv=None, s3_factory=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--budget-sec", type=float, default=90)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--prefix", default="state-ci")
    args = parser.parse_args(argv)
    factory = s3_factory or default_client
    s3, bucket = factory()
    result = scan(s3, bucket, budget_sec=args.budget_sec, workers=args.workers, prefix=args.prefix)
    sys.stdout.write(render(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
