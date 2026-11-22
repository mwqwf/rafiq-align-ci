#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مقارنة سريعة للفهارس الـ55 المضغوطة (pV 2026-10-13) بالمنشور الحيّ.

يقرأ رأس كلّ فهرس منشور (أو يحسب SHA إن غاب الحقل) ويقابل بصمته الثمانية
ببصمة المسح 20261013_1520_pV_sweep. لا يقيس صوتاً ولا يحكم «أُصلح» من تغيّر
البصمة وحده: الترقية قد تُصلح بعض السور وتُبقي غيرها.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CREDS = ROOT / "secure" / "r2_credentials.json"
DEFAULT_LIST = HERE / "data" / "compressed_pV_20261013.json"


def _client():
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


def sha8_of_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:8]


def load_index(data: bytes) -> dict:
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return json.loads(data)


def inspect_object(s3, bucket: str, key: str):
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
    except Exception as exc:  # noqa: BLE001
        return {"key": key, "error": str(exc)}
    raw = obj["Body"].read()
    live_sha8 = sha8_of_bytes(raw)
    meta = {
        "key": key,
        "live_sha8": live_sha8,
        "size": obj.get("ContentLength") or len(raw),
        "last_modified": obj["LastModified"].strftime("%Y-%m-%dT%H:%M:%SZ")
        if obj.get("LastModified") else "",
    }
    try:
        index = load_index(raw)
        header_sha = str(index.get("sha256") or index.get("sha") or "")
        if header_sha:
            meta["header_sha8"] = header_sha[:8]
        meta["from_key"] = index.get("fromKey") or index.get("parent") or ""
        missing = index.get("missing")
        if isinstance(missing, dict):
            meta["missing_count"] = missing.get("count") or missing.get("n") or ""
    except Exception:
        meta["parse"] = "failed"
    return meta


def compare(catalog: dict, live: dict) -> str:
    if live.get("error"):
        return "غائب"
    if not catalog.get("pv_sha8"):
        return "بلا_مرجع"
    if live.get("live_sha8") == catalog["pv_sha8"]:
        return "كما_في_pV"
    return "تغيّرت_بصمته"


def report(catalog, lives):
    buckets = {"كما_في_pV": [], "تغيّرت_بصمته": [], "غائب": [], "بلا_مرجع": []}
    lines = ["## حالة إصلاح الفهارس المضغوطة (مقابل مسح pV في 2026-10-13)"]
    for item, live in zip(catalog["indexes"], lives):
        status = compare(item, live)
        buckets[status].append((item, live))
        sha = live.get("live_sha8") or "؟"
        when = live.get("last_modified") or ""
        err = live.get("error")
        extra = f" ⛔ {err}" if err else f" → {sha} · {when}"
        lines.append(
            f"- {status}: {item['key']}  pV={item['pv_sha8']}  "
            f"سورٌ أكيدة={item['n_confirmed_surahs']}{extra}"
        )
    lines.append("")
    lines.append(
        f"**الخلاصة:** كما في pV {len(buckets['كما_في_pV'])} · "
        f"تغيّرت بصمته منذ المسح {len(buckets['تغيّرت_بصمته'])} · "
        f"غائب {len(buckets['غائب'])} · المجموع {len(catalog['indexes'])}."
    )
    lines.append(
        "تغيّر البصمة يعني ترقيةً لاحقة، ولا يثبت وحده زوال الضغط — يلزم مسح سماع على الحيّ."
    )
    return "\n".join(lines) + "\n", buckets


def main(argv=None, s3_factory=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", default=str(DEFAULT_LIST))
    args = parser.parse_args(argv)
    catalog = json.loads(Path(args.list).read_text(encoding="utf-8"))
    factory = s3_factory or _client
    s3, bucket = factory()
    lives = [inspect_object(s3, bucket, item["key"]) for item in catalog["indexes"]]
    text, buckets = report(catalog, lives)
    sys.stdout.write(text)
    # شفرة خروج 0 دائماً: هذه أداة جرد لا حارس جودة.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
