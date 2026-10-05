#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""طباعةُ ترويسة فهرسٍ في الدلو (كلُّ الحقول عدا المداخل) — قارئٌ محض (fixV · 2026-10-05).

    python tools/index_qa/index_header.py <مفتاح .jz> [<مفتاح> …]

لمعرفة `transform` و`missing.byReason` وخرائط السور قبل بناء تحويلٍ فوق مرشّح.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run import s3  # noqa: E402


def main() -> None:
    cl, b = s3()
    for key in sys.argv[1:]:
        body = cl.get_object(Bucket=b, Key=key)["Body"].read()
        idx = json.loads(gzip.decompress(body).decode("utf-8"))
        head = {k: v for k, v in idx.items() if k != "entries"}
        miss = dict(head.get("missing") or {})
        if isinstance(miss.get("ids"), list) and len(miss["ids"]) > 60:
            miss["ids"] = miss["ids"][:60] + [f"… و{len(miss['ids']) - 60}"]
        head["missing"] = miss
        if isinstance(head.get("audioSha256"), list):
            head["audioSha256"] = f"[{len(head['audioSha256'])} بصمة]"
        print(f"== {key} · {hashlib.sha256(body).hexdigest()[:12]} · مداخل {len(idx.get('entries') or [])}")
        print(json.dumps(head, ensure_ascii=False, indent=1)[:12000])


if __name__ == "__main__":
    main()
