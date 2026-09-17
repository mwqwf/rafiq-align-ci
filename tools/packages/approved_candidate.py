#!/usr/bin/env python3
"""Verify that an approved catalog artifact still matches a fresh live build.

The private catalog builder stamps ``generatedAt`` on every run.  Publishing a
reviewed artifact therefore cannot require a later rebuild to have identical
bytes.  This verifier permits that one volatile field to differ and nothing
else, while retaining the exact reviewed bytes (and SHA-256) for publication.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name}: JSON root is not an object")
    return value


def _semantic_candidate(doc: dict) -> dict:
    out = copy.deepcopy(doc)
    stamp = out.pop("generatedAt", None)
    if type(stamp) is not int or stamp <= 0:
        raise ValueError("candidate generatedAt must be a positive integer")
    return out


def verify_approved(
    approved_path: Path,
    fresh_path: Path,
    approved_before_path: Path,
    approved_snapshot_path: Path,
    expected_candidate_sha256: str,
    expected_packages_sha256: str,
    expected_reciters_sha256: str,
) -> dict:
    for label, value in (
        ("candidate", expected_candidate_sha256),
        ("packages", expected_packages_sha256),
        ("reciters", expected_reciters_sha256),
    ):
        if not _SHA256.fullmatch(value):
            raise ValueError(f"expected {label} SHA-256 is invalid")

    approved_sha = _sha256(approved_path)
    if approved_sha != expected_candidate_sha256:
        raise ValueError("approved artifact candidate SHA-256 changed")
    if _sha256(approved_before_path) != expected_packages_sha256:
        raise ValueError("approved artifact was built from another live package catalog")

    snapshot = _load(approved_snapshot_path)
    if snapshot.get("catalogSha256") != expected_reciters_sha256:
        raise ValueError("approved artifact certificate names another reciters catalog")

    approved = _load(approved_path)
    fresh = _load(fresh_path)
    if _semantic_candidate(approved) != _semantic_candidate(fresh):
        raise ValueError("fresh live build differs from approved candidate beyond generatedAt")

    timing = sum(p.get("kind") == "timing_index"
                 for p in (approved.get("packages") or []))
    return {
        "approvedCandidateSha256": approved_sha,
        "approvedGeneratedAt": approved["generatedAt"],
        "freshGeneratedAt": fresh["generatedAt"],
        "timingPackages": timing,
        "totalPackages": len(approved.get("packages") or []),
        "semanticMatchIgnoring": ["generatedAt"],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--approved", type=Path, required=True)
    ap.add_argument("--fresh", type=Path, required=True)
    ap.add_argument("--approved-before", type=Path, required=True)
    ap.add_argument("--approved-snapshot", type=Path, required=True)
    ap.add_argument("--expected-candidate-sha256", required=True)
    ap.add_argument("--expected-packages-sha256", required=True)
    ap.add_argument("--expected-reciters-sha256", required=True)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    result = verify_approved(
        args.approved, args.fresh, args.approved_before,
        args.approved_snapshot, args.expected_candidate_sha256,
        args.expected_packages_sha256, args.expected_reciters_sha256,
    )
    text = json.dumps(result, ensure_ascii=False, sort_keys=True)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
