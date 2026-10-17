#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""جردُ بصمة المصدر ومدّته لكلّ سورةٍ في فهرسٍ منشور — قارئٌ محض (e6 · 2026-10-17).

    python tools/index_qa/source_inventory.py <مفتاح .jz>

يطبع سطراً لكلّ سورة: رقمها · audioSha256 المعلَنة · أكبر endMs في الفهرس · fileRef.
وللمقارنة بالملفّات الحيّة على الخادم من خارج الأداة.
"""
from __future__ import annotations
import gzip, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run import s3  # noqa: E402


def main() -> None:
    cl, b = s3()
    key = sys.argv[1]
    idx = json.loads(gzip.decompress(cl.get_object(Bucket=b, Key=key)["Body"].read()).decode("utf-8"))
    shas = idx.get("audioSha256")
    by = {}
    for e in idx["entries"]:
        s = int(e["ayahId"].split(":")[0])
        d = by.setdefault(s, {"end": 0, "ref": e.get("fileRef")})
        d["end"] = max(d["end"], int(e.get("endMs") or 0))
    present = sorted(by)
    if isinstance(shas, list) and len(shas) == 114:
        want = {s: shas[s - 1] for s in present}
    elif isinstance(shas, list) and len(shas) == len(present):
        want = dict(zip(present, shas))
    else:
        want = {}
    for s in present:
        print(f"S\t{s}\t{want.get(s)}\t{by[s]['end']}\t{by[s]['ref']}")


if __name__ == "__main__":
    main()
