#!/usr/bin/env python3
"""Back up the exact live package catalog before any replacement."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
from pathlib import Path

LIVE_KEY = "packages/catalog.json"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def backup_live(client, bucket: str, expected_sha256: str,
                now: dt.datetime | None = None) -> dict:
    if not _SHA256.fullmatch(expected_sha256):
        raise ValueError("expected SHA-256 is invalid")
    body = client.get_object(Bucket=bucket, Key=LIVE_KEY)["Body"].read()
    live_sha = hashlib.sha256(body).hexdigest()
    if live_sha != expected_sha256:
        raise ValueError("live package catalog changed before backup")
    when = now or dt.datetime.now(dt.timezone.utc)
    stamp = when.astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    key = f"packages/backups/catalog.{stamp}.{live_sha}.json"
    client.put_object(
        Bucket=bucket, Key=key, Body=body, ContentType="application/json",
        Metadata={"source-key": LIVE_KEY, "source-sha256": live_sha},
        IfNoneMatch="*",
    )
    copied = client.get_object(Bucket=bucket, Key=key)["Body"].read()
    if hashlib.sha256(copied).hexdigest() != live_sha:
        raise RuntimeError("backup verification failed")
    return {"backupKey": key, "sha256": live_sha, "bytes": len(body)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--credentials", required=True)
    ap.add_argument("--expected-sha256", required=True)
    args = ap.parse_args()
    creds = json.loads(Path(args.credentials).read_text(encoding="utf-8"))
    import boto3
    client = boto3.client(
        "s3", endpoint_url=creds["endpoint"],
        aws_access_key_id=creds["accessKeyId"],
        aws_secret_access_key=creds["secretAccessKey"], region_name="auto")
    result = backup_live(client, creds["bucket"], args.expected_sha256)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
