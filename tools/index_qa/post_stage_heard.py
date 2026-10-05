#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Final heard gate for one SHA-bound staged candidate, with no Actions artifacts.

The workflow restores the CTC model before invoking this command. Every required
surah is probed afresh with float32. Only the existing heard gate decides timing
quality; an incomplete measurement never becomes an official state report.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import heard_gate as H  # noqa: E402
sys.path.insert(0, str(ROOT / "tools/ci_fleet"))
from emit_probe_map import payload_lines  # noqa: E402


def emit_evidence(data, prefix):
    """الدليل الكامل في السجل؛ البصمة وعدد الأجزاء يكشفان أي اقتطاع."""
    try:
        for line in payload_lines(data, prefix):
            print(line, flush=True)
    except ValueError as exc:
        # لا تطمس مشكلة القياس الأصلية ولا توهم بوجود نسخة كاملة في السجل.
        print(json.dumps({"evidencePrefix": prefix, "logEvidenceComplete": False,
                          "emissionError": str(exc)}, ensure_ascii=False), flush=True)


def load_bound_candidate(key, sha, parent_sha):
    # Importing the pure helpers and tests must not initialize an R2 client.
    from post_stage_guard import load_bound_candidate as load
    return load(key, sha, parent_sha)


def ci_provenance():
    run = os.environ.get("GITHUB_RUN_ID", "")
    commit = os.environ.get("GITHUB_SHA", "")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    if (os.environ.get("GITHUB_ACTIONS") != "true" or not run.isdecimal()
            or not re.fullmatch(r"[0-9a-f]{40}", commit)
            or repository != "mwqwf/rafiq-align-ci"):
        raise ValueError("official heard reports require GitHub Actions run provenance")
    paths = ("tools/index_qa/post_stage_heard.py", "tools/index_qa/post_stage_guard.py",
             "tools/index_qa/heard_gate.py", "tools/alignment_v3/ctc_heard_map.py",
             "tools/alignment_v3/ctc_seg.py")
    return {"run_id": run, "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
            "commit": commit, "repository": repository,
            "run_url": f"https://github.com/{repository}/actions/runs/{run}",
            "ctc_int8": 0, "ctc_threads": 2,
            "toolSha256": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
                           for p in paths}}


def required_sources(idx, parent, sha):
    """Use the real final SHA for the unchanged four-surah sample."""
    j = H.judge(idx, parent, sha, {})
    groups = H.by_surah(idx.get("entries") or [])
    shas = idx.get("audioSha256")
    if not isinstance(shas, list):
        raise ValueError("candidate audioSha256 is not a list")
    present = sorted(groups)
    if len(shas) == 114:
        by_sha = {s: shas[s - 1] for s in present}
    elif len(shas) == len(present):
        by_sha = dict(zip(present, shas))
    else:
        raise ValueError("candidate audioSha256 does not cover its surahs")
    items = []
    for s in j["required"]:
        refs = {v[2] for v in groups[s].values()}
        if len(refs) != 1:
            raise ValueError(f"surah {s}: exactly one audio file is required")
        url = refs.pop()
        if not isinstance(url, str):
            raise ValueError(f"surah {s}: missing audio URL")
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or not parsed.netloc or parsed.username
                or parsed.password or parsed.fragment or any(c.isspace() for c in url)):
            raise ValueError(f"surah {s}: invalid HTTPS audio URL")
        audio_sha = by_sha.get(s)
        if not isinstance(audio_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", audio_sha):
            raise ValueError(f"surah {s}: missing full audio SHA256")
        items.append((s, url, audio_sha))
    return items


def probe(surah, url, riwaya, out_dir):
    """Fresh directory prevents the probe CLI from reusing an older audio file."""
    work = Path(tempfile.mkdtemp(prefix=f"s{surah:03d}-", dir=out_dir))
    env = dict(os.environ, CTC_INT8="0", CTC_THREADS="2", OMP_NUM_THREADS="2",
               MKL_NUM_THREADS="2", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
               TOKENIZERS_PARALLELISM="false")
    cmd = [sys.executable, str(ROOT / "tools/alignment_v3/ctc_heard_map.py"),
           "--url", url, "--surah", str(surah), "--riwaya", riwaya,
           "--out-dir", str(work), "--probe", "--report", str(work / "heard.txt")]
    try:
        with (work / "probe.log").open("w", encoding="utf-8") as log:
            subprocess.run(cmd, env=env, cwd=ROOT, stdin=subprocess.DEVNULL,
                           stdout=log, stderr=subprocess.STDOUT, check=True)
        raw = json.loads((work / f"heard_s{surah:03d}.json").read_text(encoding="utf-8"))
        emit_evidence(raw, "POST_STAGE_HEARD_PROBE")
        return raw
    except Exception:
        log_path = work / "probe.log"
        emit_evidence({"surah": surah, "riwaya": riwaya, "fileRef": url,
                       "measurementComplete": False,
                       "log": log_path.read_text(encoding="utf-8", errors="replace")
                       if log_path.exists() else None}, "POST_STAGE_HEARD_PROBE_FAILURE")
        raise
    finally:
        # Delete only audio files in this invocation's private probe directory.
        for pattern in ("*.mp3", "*.wav"):
            for path in work.glob(pattern):
                path.unlink()


def collect_maps(idx, parent, sha, out_dir, probe_fn=probe):
    maps, errors = {}, {}
    for surah, url, audio_sha in required_sources(idx, parent, sha):
        try:
            raw = probe_fn(surah, url, idx["riwaya"], out_dir)
            if (not isinstance(raw, dict) or type(raw.get("surah")) is not int
                    or raw["surah"] != surah or raw.get("riwaya") != idx["riwaya"]
                    or raw.get("fileRef") != url or raw.get("sha256") != audio_sha
                    or raw.get("engine") != "ctc-heardmap-1"
                    or raw.get("entries") != [] or not isinstance(raw.get("heardMap"), dict)):
                raise ValueError("probe identity, audio SHA256, or probe-only output mismatch")
            cmap = H.compact_map(raw)
            # Exercise the real row parser before accepting a probe as complete.
            H.surah_rows({a: v[0] for a, v in H.by_surah(idx["entries"])[surah].items()}, cmap)
            maps[surah] = cmap
        except Exception as exc:  # Record all failures, then try every required surah.
            errors[str(surah)] = f"{type(exc).__name__}: {exc}"
    return maps, errors


def make_report(key, sha, parent_sha, idx, parent, maps, errors, provenance):
    j = H.judge(idx, parent, sha, maps)
    missing = sorted(set(j["required"]) - set(maps))
    complete = not errors and not missing
    rep = {"src": key, "sha256": sha, "parentSha256": parent_sha,
           "source": "ci", "run": provenance["run_id"], "provenance": provenance,
           "ts": int(time.time()), **j,
           "maps": {str(s): m for s, m in sorted(maps.items())},
           "measurementComplete": complete, "measurementErrors": errors}
    if not complete:
        rep["ok"] = False
        rep["reason"] = "incomplete required probe maps: " + ",".join(map(str, missing))
        rep["heardGateReason"] = j["reason"]
    rep["gateError"] = H.gate_error(idx, parent, sha, rep)
    return rep


def write_local(path, report):
    data = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")
    path.write_bytes(data + b"\n")
    emit_evidence(report, "POST_STAGE_HEARD_REPORT")
    return data


def run(key, sha, parent_sha, out_dir, *, loader=None, probe_fn=None, provenance=None):
    """One CI job: bind, measure, rebind, write the official report, read it back."""
    loader = loader or load_bound_candidate
    probe_fn = probe_fn or probe
    provenance = ci_provenance() if provenance is None else provenance
    _cl, _bucket, idx, parent = loader(key, sha, parent_sha)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "heard-report.json"
    maps, errors = collect_maps(idx, parent, sha, out_dir, probe_fn)
    report = make_report(key, sha, parent_sha, idx, parent, maps, errors, provenance)
    body = write_local(report_path, report)
    if not report["measurementComplete"]:
        print(f"heard: incomplete measurement; local report: {report_path}")
        return 1
    try:
        cl, bucket, current, live = loader(key, sha, parent_sha)
        if current != idx or live != parent:
            raise ValueError("candidate or published parent changed after measurement")
    except Exception as exc:
        report["ok"] = False
        report["reason"] = "candidate or published parent could not be rebound after measurement"
        report["bindingError"] = f"{type(exc).__name__}: {exc}"
        write_local(report_path, report)
        raise
    state_key = H.state_key(key)
    cl.put_object(Bucket=bucket, Key=state_key, Body=body, ContentType="application/json")
    back_raw = cl.get_object(Bucket=bucket, Key=state_key)["Body"].read()
    if back_raw != body:
        raise ValueError("official heard report read-back differs from written bytes")
    back = json.loads(back_raw)
    why = H.gate_error(current, live, sha, back)
    print(json.dumps({"src": key, "sha256": sha, "stateKey": state_key,
                      "required": report["required"], "modified": report["modified"],
                      "sample": report["sample"], "ok": why is None,
                      "reason": why, "localReport": str(report_path)}, ensure_ascii=False))
    return 1 if why else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--key", required=True)
    ap.add_argument("--sha", required=True)
    ap.add_argument("--parent-sha", required=True)
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args(argv)
    try:
        return run(a.key, a.sha, a.parent_sha, a.out_dir)
    except Exception as exc:
        print(f"heard: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
