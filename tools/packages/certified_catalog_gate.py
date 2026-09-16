#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""بوابة كتالوج الحزم: لا يمر timing_index إلا بشهادة حية وبصمة متسقة."""
from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def certified_only(doc: dict, min_timing: int = 0) -> tuple[dict, dict]:
    failures = doc.get("failures") or []
    if failures:
        raise ValueError(f"البناء فيه {len(failures)} فشلاً؛ يُمنع النشر")
    out = copy.deepcopy(doc)
    kept, rejected = [], list(out.get("rejected") or [])
    seen, certified, dropped = set(), 0, 0
    for package in out.get("packages") or []:
        pid = str(package.get("id") or "")
        if not pid or pid in seen:
            raise ValueError(f"معرّف حزمة غائب/مكرر: {pid!r}")
        seen.add(pid)
        if package.get("kind") != "timing_index":
            kept.append(package)
            continue
        quality = package.get("quality") or {}
        if quality.get("ayahCertified") is not True:
            rejected.append({"key": (package.get("files") or [{}])[0].get("key"),
                             "reason": "NOT_CERTIFIED"})
            dropped += 1
            continue
        coverage = quality.get("ayahCoverage")
        if not isinstance(coverage, (int, float)) or coverage < 0.98:
            raise ValueError(f"{pid}: certified مع تغطية غير صالحة {coverage!r}")
        files = package.get("files") or []
        if len(files) != 1:
            raise ValueError(f"{pid}: عدد ملفات timing_index ليس واحداً")
        sha = str(files[0].get("sha256") or "")
        if not _SHA256.fullmatch(sha):
            raise ValueError(f"{pid}: sha256 غير صالح")
        if quality.get("sha8") != sha[:8]:
            raise ValueError(f"{pid}: sha8 لا يطابق ملف الحزمة")
        kept.append(package)
        certified += 1
    if certified < min_timing:
        raise ValueError(f"الكتالوج المصدق {certified} < الحد المحافظ {min_timing}")
    out["packages"] = kept
    out["rejected"] = rejected
    out["certifiedGate"] = {
        "timingCertified": certified,
        "timingDroppedUncertified": dropped,
        "nonTimingKept": sum(p.get("kind") != "timing_index" for p in kept),
    }
    return out, out["certifiedGate"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--min-timing", type=int, default=0)
    args = ap.parse_args()
    doc = json.loads(Path(args.input).read_text(encoding="utf-8"))
    out, stat = certified_only(doc, args.min_timing)
    Path(args.output).write_text(
        json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(json.dumps(stat, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
