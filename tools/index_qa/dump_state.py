#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""طباعةُ حقولٍ من تقرير حكمٍ واحدٍ في state/ — تشخيصٌ للقراءة لا للكتابة.

    python tools/index_qa/dump_state.py <مفتاح state/... كاملاً> [حقل1 حقل2 ...]

بلا حقولٍ يطبع: verdict · fatal · sha256 · ts · source · sample.seedSalt.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run import s3  # noqa: E402


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("الاستعمال: dump_state.py <مفتاح state/...> [حقول]")
    key = sys.argv[1]
    fields = sys.argv[2:] or ["verdict", "fatal", "sha256", "ts", "source"]
    cl, b = s3()
    doc = json.loads(cl.get_object(Bucket=b, Key=key)["Body"].read())
    out = {}
    for f in fields:
        if f == "sample.seedSalt":
            out[f] = (doc.get("sample") or {}).get("seedSalt")
        else:
            out[f] = doc.get(f)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
