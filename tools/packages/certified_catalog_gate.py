#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""بوابة كتالوج الحزم: لا يمر timing_index إلا بشهادة حية وبصمة متسقة."""
from __future__ import annotations

import argparse
import copy
import json
import math
import re
from pathlib import Path

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CERTIFIER = "certify_catalog-1.1"


def _finite_coverage(value, package_id: str) -> float:
    # bool is an int subclass in Python; a certificate must never accept it.
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{package_id}: certified مع تغطية غير محدودة {value!r}")
    if not 0.98 <= value <= 1.0:
        raise ValueError(f"{package_id}: certified مع تغطية خارج [0.98, 1] {value!r}")
    return float(value)


def _timing_id(package: dict) -> tuple[str, dict]:
    files = package.get("files") or []
    pid = str(package.get("id") or "")
    if len(files) != 1:
        raise ValueError(f"{pid}: عدد ملفات timing_index ليس واحداً")
    key = str(files[0].get("key") or "")
    parts = key.split("/")
    if len(parts) != 3 or parts[0] != "timings" or not parts[2].endswith(".jz"):
        raise ValueError(f"{pid}: مفتاح timing_index غير صالح {key!r}")
    return f"{parts[1]}/{parts[2][:-3]}", files[0]


def _snapshot_indexes(snapshot: dict) -> dict:
    if snapshot.get("schema") != 1 or snapshot.get("certifier") != _CERTIFIER:
        raise ValueError("snapshot الشهادة غير معروف")
    if not _SHA256.fullmatch(str(snapshot.get("catalogSha256") or "")):
        raise ValueError("snapshot الشهادة بلا بصمة كتالوج كاملة")
    indexes = snapshot.get("indexes")
    if not isinstance(indexes, dict):
        raise ValueError("snapshot الشهادة بلا خريطة indexes")
    return indexes


def certified_only(doc: dict, min_timing: int = 0,
                   certificate_snapshot: dict | None = None) -> tuple[dict, dict]:
    failures = doc.get("failures") or []
    if failures:
        raise ValueError(f"البناء فيه {len(failures)} فشلاً؛ يُمنع النشر")
    out = copy.deepcopy(doc)
    kept, rejected = [], list(out.get("rejected") or [])
    snapshot = _snapshot_indexes(certificate_snapshot or {})
    seen, certified, dropped = set(), 0, 0
    kept_ids = set()
    for package in out.get("packages") or []:
        pid = str(package.get("id") or "")
        if not pid or pid in seen:
            raise ValueError(f"معرّف حزمة غائب/مكرر: {pid!r}")
        seen.add(pid)
        if package.get("kind") != "timing_index":
            kept.append(package)
            continue
        timing_id, file_doc = _timing_id(package)
        quality = package.get("quality") or {}
        cert = snapshot.get(timing_id)
        # The catalog booleans are only a redundant consistency signal.  The
        # independent certificate snapshot is the authority for inclusion.
        if cert is None:
            rejected.append({"key": (package.get("files") or [{}])[0].get("key"),
                             "reason": "NOT_IN_CERTIFICATE_SNAPSHOT"})
            dropped += 1
            continue
        if quality.get("ayahCertified") is not True:
            raise ValueError(f"{pid}: snapshot مصدّق لكن علم الحزمة ليس true")
        coverage = _finite_coverage(quality.get("ayahCoverage"), pid)
        cert_coverage = _finite_coverage(cert.get("coverage"), timing_id)
        if coverage != cert_coverage:
            raise ValueError(f"{pid}: تغطية الحزمة لا تطابق snapshot الشهادة")
        if cert.get("rejected") is not False:
            raise ValueError(f"{pid}: snapshot الشهادة لا يثبت rejected=false")
        sha = str(file_doc.get("sha256") or "")
        if not _SHA256.fullmatch(sha):
            raise ValueError(f"{pid}: sha256 غير صالح")
        certified_sha = str(cert.get("sha256") or "")
        if not _SHA256.fullmatch(certified_sha) or certified_sha != sha:
            raise ValueError(f"{pid}: بصمة الملف لا تطابق شهادة SHA-256 الكاملة")
        if quality.get("sha8") != sha[:8]:
            raise ValueError(f"{pid}: sha8 لا يطابق ملف الحزمة")
        kept.append(package)
        kept_ids.add(timing_id)
        certified += 1
    missing = sorted(set(snapshot) - kept_ids)
    if missing:
        raise ValueError(f"مرشح البناء أسقط {len(missing)} معرّفاً مصدقاً: {missing[:5]}")
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


def id_diff(previous: dict, candidate: dict) -> dict:
    before = set()
    for package in previous.get("packages") or []:
        if package.get("kind") != "timing_index":
            continue
        if (package.get("quality") or {}).get("ayahCertified") is True:
            before.add(_timing_id(package)[0])
    after = {_timing_id(p)[0] for p in candidate.get("packages") or []
             if p.get("kind") == "timing_index"}
    report = {
        "beforeCertified": sorted(before),
        "afterCertified": sorted(after),
        "added": sorted(after - before),
        "removed": sorted(before - after),
    }
    if report["removed"]:
        raise ValueError(f"المرشح أسقط قارئاً مخدوماً مصدقاً: {report['removed'][:5]}")
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--min-timing", type=int, default=0)
    ap.add_argument("--certificate-snapshot", required=True)
    ap.add_argument("--previous")
    ap.add_argument("--id-diff")
    args = ap.parse_args()
    doc = json.loads(Path(args.input).read_text(encoding="utf-8"))
    snapshot = json.loads(Path(args.certificate_snapshot).read_text(encoding="utf-8"))
    out, stat = certified_only(doc, args.min_timing, snapshot)
    if bool(args.previous) != bool(args.id_diff):
        raise ValueError("--previous و--id-diff يُعطيان معاً")
    if args.previous:
        previous = json.loads(Path(args.previous).read_text(encoding="utf-8"))
        diff = id_diff(previous, out)
        Path(args.id_diff).write_text(
            json.dumps(diff, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
        stat["beforeCertified"] = len(diff["beforeCertified"])
        stat["added"] = len(diff["added"])
        stat["removed"] = len(diff["removed"])
    Path(args.output).write_text(
        json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(json.dumps(stat, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
