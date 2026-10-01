#!/usr/bin/env python3
"""فحص مرشّح محلي بالمحكّم القائم، بلا اعتماد دلو أو كتابة خارجية."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run as R


def candidate_identity(path):
    blob = Path(path).read_bytes()
    sha = hashlib.sha256(blob).hexdigest()
    idx = json.loads(gzip.decompress(blob))
    key = f"timings-staging/{idx['riwaya']}/{idx['reciterId']}.{sha[:8]}.jz"
    return idx, sha, key


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--index", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--cache", required=True)
    ap.add_argument("--mode", choices=["struct", "audio", "census", "openers"], required=True)
    ap.add_argument("--seed-salt", default="")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    idx, sha, key = candidate_identity(a.index)
    if a.mode == "audio" and not a.seed_salt:
        ap.error("كل فحص صوتي يحتاج ملحاً صريحاً")
    cache = Path(a.cache).resolve(); cache.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    if a.mode == "openers":
        sys.path.insert(0, str(ROOT / "tools/tasmi_bench"))
        import openers_scan as O
        class LocalCandidate:
            def download_file(self, bucket, requested, dest):
                if requested != key:
                    raise ValueError("الفاحص طلب مرشّحاً آخر")
                shutil.copyfile(a.index, dest)
        O.s3 = lambda: (LocalCandidate(), "local-candidate")
        old = sys.argv
        sys.argv = [O.__file__, "--key", key, "--model", a.model, "--threads", "4"]
        try:
            O.main()
        finally:
            sys.argv = old
        witness = ROOT / "tools/index_qa/state" / (key.replace("/", "_") + ".openers.json")
        report = json.loads(witness.read_text(encoding="utf-8"))
        if report.get("late"):
            subprocess_args = [sys.executable, str(ROOT / "tools/alignment_v3/ctc_opener_probe.py"),
                               "--witness", str(witness), "--riwaya", idx["riwaya"]]
            import subprocess
            subprocess.run(subprocess_args, check=True)
            report = json.loads(witness.read_text(encoding="utf-8"))
        if report.get("sha256") != sha:
            raise SystemExit("⛔ شاهد المطالع يخص بصمة أخرى")
    else:
        def fetch(requested, want_sha=None):
            if requested != key or (want_sha and want_sha != sha):
                raise ValueError("المفتاح أو البصمة لا يطابقان المرشّح المحلي")
            return idx, sha
        R.fetch_index = fetch
        R._src_mtime = lambda requested: Path(a.index).stat().st_mtime
        R.LOCAL_MODEL = Path(a.model).resolve()
        R.LOCAL_CACHE = cache
        os.environ["QA_SOURCE"] = "ci" if os.environ.get("GITHUB_ACTIONS") else "session"
        os.environ["QA_RUN_ID"] = os.environ.get("GITHUB_RUN_ID", "session")
        os.environ["QA_SEED_SALT"] = a.seed_salt
        os.environ["QA_KIND"] = "splice-census" if a.mode == "census" else a.mode
        os.environ.pop("QA_CENSUS_SURAHS", None)
        if a.mode == "census":
            from promote import census_surahs
            needed = census_surahs(idx)
            if not needed:
                raise SystemExit("⛔ لا سور مدموجة ولا مصدر بديل لإحصائه")
            os.environ["QA_CENSUS_SURAHS"] = ",".join(sorted(needed, key=int))
        args = argparse.Namespace(struct_only=a.mode == "struct", allow_unmarked=True,
                                  local=True, rejudge=False, clusters=20, per_cluster=10,
                                  band=None, refined=None, long_seg=False, batch=48,
                                  threads=1, host=None, expect_sha=sha)
        report = R.audit(key, args)
        if a.mode == "census":
            report["census"] = {"surahs": sorted(needed, key=int)}
    if hashlib.sha256(Path(a.index).read_bytes()).hexdigest() != sha:
        raise SystemExit("⛔ تغير المرشّح أثناء الفحص")
    report["unpublishedLocalCandidate"] = True
    report["elapsedSec"] = round(time.time() - t0)
    report["provenance"] = {"tool": "tools/index_qa/local_candidate.py",
                            "tool_sha": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                            "run_sha": hashlib.sha256(Path(R.__file__).read_bytes()).hexdigest(),
                            "run_id": os.environ.get("GITHUB_RUN_ID", "session")}
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"key": key, "sha256": sha, "mode": a.mode,
                      "verdict": report.get("verdict", report.get("openersVerdict")),
                      "fatal": report.get("fatal", []), "elapsedSec": report["elapsedSec"]}, ensure_ascii=False))
    if report.get("fatal") or str(report.get("verdict", "")).startswith("مرفوض"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
