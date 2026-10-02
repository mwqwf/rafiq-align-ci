#!/usr/bin/env python3
"""Read-only review of a package-catalog artifact against current public production.
No R2 credentials, uploads, changes to guards, or app-source output.
"""
import argparse, concurrent.futures, gzip, hashlib, io, json, subprocess, urllib.request, zipfile
from pathlib import Path

REPO = "mwqwf/rafiq-align-ci"
BASE = "https://pub-2c2e1dcd92e84a2898820dd38d3e09e6.r2.dev"

def gh(path):
    p = subprocess.run(["gh", "api", path], capture_output=True, check=True)
    return p.stdout

def public(key):
    req = urllib.request.Request(BASE + "/" + key, headers={"User-Agent": "index-catalog-review/1"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def review(run_id):
    run = json.loads(gh(f"repos/{REPO}/actions/runs/{run_id}"))
    if run["status"] != "completed" or run["conclusion"] != "success":
        raise ValueError("Candidate run has not passed")
    if run["path"] != ".github/workflows/package-catalog-cloud.yml":
        raise ValueError("Unexpected producer workflow")
    artifacts = json.loads(gh(f"repos/{REPO}/actions/runs/{run_id}/artifacts"))["artifacts"]
    eligible = [x for x in artifacts if x["name"].startswith("package-catalog-candidate-") and not x["expired"]]
    if len(eligible) != 1:
        raise ValueError("Exactly one unexpired candidate required")
    art = eligible[0]
    archive = zipfile.ZipFile(io.BytesIO(gh(f"repos/{REPO}/actions/artifacts/{art['id']}/zip")))
    candidate_raw = archive.read("catalog.certified.json")
    before_raw = archive.read("catalog.before.json")
    snapshot = json.loads(archive.read("certified-indexes.json"))
    gate_summary = json.loads(archive.read("gate-summary.json"))
    id_diff = json.loads(archive.read("id-diff.json"))
    cat = json.loads(candidate_raw)
    manifest = json.loads(public("timings/manifest.json"))
    reciters_raw, live_packages_raw = public("catalog/reciters.json"), public("packages/catalog.json")
    reciters = json.loads(reciters_raw)
    rows = [x for x in cat["packages"] if x.get("kind") == "timing_index"]
    by = {(x["riwaya"], x["reciterId"]): x for x in rows}
    prod = {(x["riwaya"], x["reciterId"]): x for x in manifest["indexes"]}
    errors = []
    if len(by) != len(rows) or set(by) != set(prod):
        errors.append("Candidate identifiers differ from current production manifest")
    if sha(reciters_raw) != snapshot["catalogSha256"]:
        errors.append("Reciter catalog changed since certificate snapshot")
    if sha(live_packages_raw) != sha(before_raw):
        errors.append("Live package catalog changed since build")
    if id_diff.get("removed"):
        errors.append("Candidate removes previously certified identifiers")
    def check(item):
        who, row = item
        if len(row["files"]) != 1:
            raise ValueError("Unexpected timing file count")
        f = row["files"][0]
        key = f"timings/{who[0]}/{who[1]}.jz"
        raw = public(key)
        idx = json.loads(gzip.decompress(raw))
        evidence = snapshot["indexes"].get("/".join(who), {})
        live = prod.get(who, {})
        actual_sha = sha(raw)
        bad = []
        if f.get("key") != key or f.get("sha256") != actual_sha or f.get("bytes") != len(raw):
            bad.append("File declaration differs from actual public bytes")
        if live.get("sha256") != actual_sha or evidence.get("sha256") != actual_sha or not evidence.get("verdictKeys"):
            bad.append("Manifest/certificate does not match public bytes and verdict")
        entries = len(idx["entries"])
        quality = row.get("quality") or {}
        if row.get("entries") != entries or not quality.get("ayahCertified"):
            bad.append("Entries/certification differ")
        return {"id":row["id"],"key":key,"sha256":actual_sha,"bytes":len(raw),"entries":entries,"errors":bad}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        checked = list(pool.map(check, by.items()))
    errors += [x["id"] + ": " + "; ".join(x["errors"]) for x in checked if x["errors"]]
    return {
        "ready":not errors,"errors":errors,"runId":run_id,"artifactId":art["id"],
        "artifactBytes":art["size_in_bytes"],"artifactExpiresAt":art["expires_at"],
        "candidateSha256":sha(candidate_raw),"expectedRecitersSha256":sha(reciters_raw),
        "expectedPackagesSha256":sha(live_packages_raw),"timingPackages":len(rows),
        "productionIndexes":len(prod),"gateSummary":gate_summary,"idDiff":id_diff,
        "targets":[x for x in checked if x["id"] in ("timings.hafs.kurdi","timings.hafs.a_klb","timings.qalun.akri_qalun","timings.hafs.asim")],
        "checked":checked,
        "reciterTargets":[x for riw in reciters["riwayat"] for x in riw["reciters"] if x["id"] in ("kurdi","asim","akri_qalun")],
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=int, required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    report = review(a.run)
    Path(a.out).write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k != "checked"}, ensure_ascii=False))
    return 0 if report["ready"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
