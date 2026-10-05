#!/usr/bin/env python3
"""تصدير نسخة منشورة واحدة كما هي، ببصمة كاملة، دون كتابة إلى الدلو.

يحفظ gzip الأصلي بصيغة base64 في ops/out فقط، فلا تُعاد صناعة الترويسة أو
المداخل من جرد مختصر. يرفض تغير البصمة المطلوبة ولا يصدر أي شهادة جودة.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile

ROOT = Path(__file__).resolve().parents[2]
MAX_BYTES = 512 * 1024
MAX_UNCOMPRESSED = 8 * 1024 * 1024
KEY_RE = re.compile(r"timings/([A-Za-z0-9_-]+)/([A-Za-z0-9_-]+)\.jz")


def output_path(path):
    target = Path(os.path.abspath(path))
    if (target.parent != ROOT / "ops/out" or target.suffix != ".json"
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*\.json", target.name)
            or any(p.is_symlink() for p in (target, *target.parents))):
        raise ValueError("مسار التصدير يجب أن يكون ملف JSON مباشرًا داخل ops/out بلا روابط رمزية")
    if target.exists():
        raise ValueError("ملف التصدير موجود؛ اختر اسمًا جديدًا")
    return target


def identity(key, expected_sha):
    match = KEY_RE.fullmatch(key)
    if not match or not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
        raise ValueError("يلزم مفتاح منشور واحد وبصمة SHA-256 كاملة")
    return match[1], match[2]


def export(cl, bucket, key, expected_sha, out):
    riwaya, reciter = identity(key, expected_sha)
    target = output_path(out)
    # طلب قراءة واحد فقط؛ الحجم محدود حتى لو أخطأت ترويسة ContentLength.
    response = cl.get_object(Bucket=bucket, Key=key)
    stream = response["Body"]
    try:
        raw = stream.read(MAX_BYTES + 1)
    finally:
        stream.close()
    if len(raw) > MAX_BYTES:
        raise ValueError("الأصل أكبر من سقف التصدير؛ لا تحفظ نسخة مبتورة")
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise ValueError("بصمة الأصل الحي لا تطابق البصمة المطلوبة")
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as compressed:
        unpacked = compressed.read(MAX_UNCOMPRESSED + 1)
    if len(unpacked) > MAX_UNCOMPRESSED:
        raise ValueError("الفهرس المفكوك يتجاوز سقف القراءة")
    index = json.loads(unpacked)
    if (not isinstance(index, dict) or index.get("riwaya") != riwaya
            or index.get("reciterId") != reciter or not isinstance(index.get("entries"), list)):
        raise ValueError("هوية الفهرس أو مداخله لا تطابق المفتاح")
    report = {"generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
              "key": key, "sha256": expected_sha, "bytes": len(raw),
              "entryCount": len(index["entries"]), "encoding": "base64",
              "gzipBase64": base64.b64encode(raw).decode("ascii"),
              "qualityClaim": False, "bucketWritten": False}
    target.parent.mkdir(parents=True, exist_ok=True)
    output_path(target)
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".index-export-", delete=False) as file:
        temporary = Path(file.name)
        try:
            file.write(json.dumps(report, ensure_ascii=False, indent=1).encode("utf-8"))
            file.flush()
            os.fsync(file.fileno())
            os.link(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    return {k: v for k, v in report.items() if k != "gzipBase64"}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--key", required=True)
    ap.add_argument("--expect-sha", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    try:
        identity(args.key, args.expect_sha)
        output_path(args.out)
        from run import s3
        client, bucket = s3()
        summary = export(client, bucket, args.key, args.expect_sha, args.out)
    except Exception as ex:
        # أخطاء SDK قد تحمل عنوان الدلو أو معلومات الطلب؛ لا تطبعها أو الأسرار.
        message = str(ex) if type(ex) is ValueError else type(ex).__name__
        raise SystemExit(f"تعذر تصدير الأصل: {message}") from None
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
