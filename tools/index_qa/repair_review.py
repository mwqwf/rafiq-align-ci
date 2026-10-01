#!/usr/bin/env python3
"""Read-only review of published repair proofs and their exact-SHA audio gates."""
import argparse
import collections
import concurrent.futures
import gzip
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import promote as p

def get(cl, bucket, key):
    return json.loads(cl.get_object(Bucket=bucket, Key=key)["Body"].read())

def read_report(cl, bucket, key, sha):
    report = get(cl, bucket, key)
    if report.get("sha256") != sha:
        raise ValueError("report SHA differs: " + key)
    if report.get("fatal") or (report.get("sample") or {}).get("errors"):
        raise ValueError("fatal or failed audio windows: " + key)
    return report

def review(name, cl, bucket):
    if not re.fullmatch(r"[a-z0-9_]+", name):
        raise ValueError("invalid proof name")
    proof = json.loads((ROOT / "ops/source-repair/staged" / (name + ".json")).read_text())
    key, sha = proof["key"], proof["sha256"]
    result = {"name": name, "key": key, "sha256": sha, "parentSha": proof["parentSha"],
              "parent": proof["parent"], "added": proof.get("added", []), "ready": False}
    try:
        actual, _, body = p.object_sha(cl, bucket, key)
        if actual != sha:
            raise ValueError("staged object differs from proof")
        idx = json.loads(gzip.decompress(body))
        reps = []
        for salt in ("rs1", "rs2", "rs3", "rs4"):
            state = "state/" + key.replace("/", "_") + ".audio-" + salt + ".json"
            rep = read_report(cl, bucket, state, sha)
            sample = rep.get("sample") or {}
            severe = sample.get("severe") or []
            if (sample.get("seedSalt") != salt or not p.has_audio_sample(rep)
                    or len(severe) < 2 or severe[1] != 200
                    or len(sample.get("rows") or []) != 200):
                raise ValueError("incomplete or wrong-salt sample: " + state)
            reps.append(rep)
            result[salt] = {"severe": severe[:2], "errors": sample.get("errors"),
                            "fatal": rep.get("fatal"), "provenance": rep.get("provenance")}
        pooled = p.pooled_samples(reps)
        result["pooled"] = pooled
        if pooled is None or pooled["hi"] >= p.SEVERE_CEILING:
            raise ValueError("four-salt pooled evidence does not pass unchanged ceiling")
        opener = read_report(cl, bucket, "state/" + key.replace("/", "_") + ".openers.json", sha)
        if (opener.get("scope") != "full" or not p.openers_tool_ok(opener)
                or any(opener.get(k) for k in ("errors", "swallowed", "lateConfirmed"))
                or (opener.get("verdict") and opener["verdict"] != p.ACCEPTED)):
            raise ValueError("full trusted opener evidence does not pass")
        result["openers"] = {k: opener.get(k) for k in
                             ("counts", "scope", "errors", "swallowed", "lateConfirmed", "commit")}
        census_key = "state-census/" + key.replace("/", "_") + ".json"
        census = read_report(cl, bucket, census_key, sha)
        why = p.census_gate(cl, bucket, key, sha, idx)
        result["census"] = {"gate": why, "population": len(census["sample"]["rows"]),
                           "counts": dict(collections.Counter(r["kind"] for r in census["sample"]["rows"])),
                           "surahs": census.get("census", {}).get("surahs"),
                           "errors": census["sample"].get("errors"), "fatal": census.get("fatal")}
        result["addedRows"] = [r for r in census["sample"]["rows"] if r["aid"] in proof.get("added", [])]
        if why:
            raise ValueError(why)
        result["ready"] = True
    except Exception as ex:
        result["pendingOrRejected"] = str(ex)
    return result

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--names", nargs="+")
    ap.add_argument("--out", default="ops/out/repair-review-20261001.json")
    a = ap.parse_args()
    if a.self_test:
        subprocess.run([sys.executable, "-m", "unittest", "tools/index_qa/test_ctc_splice.py"],
                       cwd=ROOT, check=True)
        return
    if not a.names:
        ap.error("--names required")
    dest = ROOT / a.out
    if dest.parent != ROOT / "ops/out" or dest.suffix != ".json":
        ap.error("output must be a JSON file directly in ops/out")
    cl, bucket = p.s3()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda n: review(n, cl, bucket), a.names))
    dest.write_text(json.dumps({"results": results}, ensure_ascii=False, indent=2) + "\n")
    for result in results:
        print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    main()
