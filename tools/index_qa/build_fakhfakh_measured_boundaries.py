"""Build a bounded Fakhfakh/Qalun candidate from pinned CTC/heard evidence.

Only the starts of 11:19 and 20:93 and the matching preceding ends move.
The source, reader, riwaya, Quran text, confidence, and every unrelated row are
preserved.  The candidate remains unpublished and requires fresh final-SHA QA.
"""
from __future__ import annotations

import copy
import gzip
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_registered_candidate as C
import run as R
import stage_transform as T

ROOT = Path(__file__).resolve().parents[2]
PARENT_SHA = "5bad920fd4994019caacc00b9edd6662941abae720ba0b3a2b41281016c23eef"
PARENT_KEY = "timings/qalun/fakhfakh_qalun.jz"
PARENT_PATH = "ops/source-repair/parents/codex-short-tail-qalun-fakhfakh_qalun-5bad920f.jz"
ENGINE = "ctc-heardmap-1"
EVIDENCE = {
    11: ("ops/out/codex-fakhfakh11-ctc-37599896584.json", "09f8bf8fda548e06b53271fad2eaddcd57aec8dd46224112ef071b0739452a90"),
    20: ("ops/out/codex-fakhfakh20-ctc-37599193396.json", "1450cb7a03c16473e2ee7616800fe18e0ea1c1fc3c7a161d96e4b7d6fa8b0f03"),
}
TARGETS = {
    11: {"ayah": 19, "startMs": 409205, "sourceSha256": "ec1ba4434cd5483a6ad43d1e1d057f513338b30bbfe1021bb3730afb592d088c"},
    20: {"ayah": 93, "startMs": 1086713, "sourceSha256": "09b4306ed043ce8832506fc8b131cb7bd728bc8eb559e45ddb7bd47cb42d86a5"},
}


def checked(path: str, expected_sha: str, *, packed: bool = False):
    blob = (ROOT / path).read_bytes()
    C.require(hashlib.sha256(blob).hexdigest() == expected_sha, "changed input: " + path)
    return json.loads(gzip.decompress(blob) if packed else blob)


def validate_evidence(parent: dict, surah: int, report: dict) -> dict:
    spec = TARGETS[surah]
    ayah = spec["ayah"]
    target_id = f"{surah}:{ayah}"
    previous_id = f"{surah}:{ayah - 1}"
    next_id = f"{surah}:{ayah + 1}"
    rows = {entry["ayahId"]: entry for entry in parent["entries"]}
    target = report["target"]
    ctc = target["ctcEntry"]
    heard = target["heardAnchor"]
    occurrence = target["heardOccurrence"]
    C.require(report["scope"] == f"qalun/fakhfakh_qalun/{surah}"
              and report["conclusion"] == "success"
              and report["artifactCount"] == 0
              and not report["cacheWrite"] and not report["r2Write"],
              "probe provenance changed")
    C.require(report["engine"] == ENGINE and report["entryCount"] == C.splice_surah.COUNTS[surah - 1]
              and report["source"]["sha256"] == spec["sourceSha256"]
              and parent["audioSha256"][surah - 1] == spec["sourceSha256"],
              "probe identity, source, or population changed")
    C.require(target["ayahId"] == target_id and target["published"] == {
        key: rows[target_id][key] for key in target["published"]
    }, "published target no longer matches the pinned parent")
    C.require(ctc["startMs"] == spec["startMs"] and ctc["heard"]
              and not ctc["snapped"] and ctc["conf"] >= .70,
              "weak or changed CTC boundary")
    C.require(abs(heard["startMs"] - ctc["startMs"]) <= 600
              and abs(occurrence["startMs"] - ctc["startMs"]) <= 150
              and heard["quality"] >= .88 and occurrence["score"] >= .88,
              "heard witnesses do not independently support the CTC start")
    C.require(rows[target_id]["startMs"] - ctc["startMs"] > 1500,
              "boundary no longer exceeds the unchanged strict tolerance")
    C.require(report["neighbors"][previous_id]["endMs"] == ctc["startMs"]
              and report["neighbors"][next_id]["startMs"] == ctc["endMs"],
              "CTC target no longer agrees with both measured neighbours")
    return {
        "runId": report["runId"],
        "jobId": report["jobId"],
        "resultSha256": report["resultSha256"],
        "sourceSha256": report["source"]["sha256"],
        "target": target_id,
        "oldStartMs": rows[target_id]["startMs"],
        "newStartMs": ctc["startMs"],
        "ctcConfidence": ctc["conf"],
        "heardAnchorStartMs": heard["startMs"],
        "heardAnchorQuality": heard["quality"],
        "heardOccurrenceStartMs": occurrence["startMs"],
        "heardOccurrenceScore": occurrence["score"],
    }


def build() -> dict:
    parent = checked(PARENT_PATH, PARENT_SHA, packed=True)
    C.require(parent["reciterId"] == "fakhfakh_qalun" and parent["riwaya"] == "qalun"
              and len(parent["entries"]) == 6236 and len(parent["audioSha256"]) == 114,
              "parent identity changed")
    reports = {surah: checked(*spec) for surah, spec in EVIDENCE.items()}
    proof_rows = {surah: validate_evidence(parent, surah, report)
                  for surah, report in reports.items()}
    candidate = copy.deepcopy(parent)
    rows = {entry["ayahId"]: entry for entry in candidate["entries"]}
    changes = []
    for surah, spec in TARGETS.items():
        ayah = spec["ayah"]
        previous_id, target_id = f"{surah}:{ayah - 1}", f"{surah}:{ayah}"
        before_previous = copy.deepcopy(rows[previous_id])
        before_target = copy.deepcopy(rows[target_id])
        rows[previous_id]["endMs"] = rows[target_id]["startMs"] = spec["startMs"]
        for before, after in ((before_previous, rows[previous_id]), (before_target, rows[target_id])):
            C.require(before != after and after["endMs"] > after["startMs"],
                      "invalid or empty boundary repair")
            strip = lambda row: {k: v for k, v in row.items() if k not in ("startMs", "endMs")}
            C.require(strip(before) == strip(after), "confidence, source, or flags changed")
            changes.append({"before": before, "after": copy.deepcopy(after)})
        candidate.setdefault("engineBySurah", {})[str(surah)] = ENGINE
    changed_ids = {change["after"]["ayahId"] for change in changes}
    C.require([row for row in parent["entries"] if row["ayahId"] not in changed_ids]
              == [row for row in candidate["entries"] if row["ayahId"] not in changed_ids],
              "unrelated entry changed")
    proof = {
        "kind": "independent-ctc-heard-boundary-repair",
        "qualityClaim": False,
        "thresholdMs": 1500,
        "thresholdChanged": False,
        "sourceChanged": False,
        "canonicalTextChanged": False,
        "evidence": {
            str(surah): {"path": EVIDENCE[surah][0], "sha256": EVIDENCE[surah][1], **proof_rows[surah]}
            for surah in sorted(TARGETS)
        },
        "changes": changes,
        "selection": "Use each unsnapped CTC start only where the full-file CTC boundary, heard anchor, heard occurrence, and both measured neighbours agree within pinned limits.",
        "limits": [
            "Only the two measured starts and their preceding ends changed; original confidence and flags remain untouched.",
            "The unchanged final-SHA heard gate must remeasure both targets and their neighbourhoods.",
            "Full census, openers, four random salts, and publication identity checks remain mandatory; this is not 100% certification."
        ],
    }
    transform = C.repaired_transform(parent, candidate, sorted(TARGETS), PARENT_SHA, PARENT_KEY)
    moved, added, removed = T.entry_change_counts(parent["entries"], candidate["entries"])
    C.require(moved == 4 and added == removed == 0, "unexpected entry change count")
    transform.update(
        op="ctc_heardmap_splice:11,20",
        fromSha256=PARENT_SHA,
        fromKey=PARENT_KEY,
        entriesSha256=T.entries_sha(candidate["entries"]),
        parentEntriesSha256=T.entries_sha(parent["entries"]),
        movedEntries=moved,
        addedEntries=0,
        removedEntries=0,
        by="build_fakhfakh_measured_boundaries",
        reason="Pinned independent CTC/heard repair of two measured late-start boundaries",
        sameSourceRepair=proof,
        unpublishedLocalCandidate=True,
    )
    candidate["transform"] = transform
    why = T.promote.index_gate(candidate, parent=parent, parent_sha=PARENT_SHA)
    C.require(not why, "index gate: " + str(why))
    fatal, warnings, _ = R.structural(candidate, PARENT_KEY, False)
    C.require(not fatal, "structural gate: " + str(fatal))
    C.require({"11", "20"} <= T.promote.census_surahs(candidate),
              "modified surahs escaped full census")
    payload = gzip.compress(json.dumps(candidate, ensure_ascii=False, separators=(",", ":"),
                                       allow_nan=False).encode("utf-8"), mtime=0)
    path = ROOT / "ops/source-repair/candidates/codex-fakhfakh-boundaries-11-20-20261007.jz"
    C.require(not path.exists() or path.read_bytes() == payload, "existing candidate differs")
    if not path.exists():
        path.write_bytes(payload)
    result = {
        "path": str(path.relative_to(ROOT)),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "parentKey": PARENT_KEY,
        "parentSha256": PARENT_SHA,
        "surahs": sorted(TARGETS),
        "changedEntries": moved,
        "addedEntries": added,
        "removedEntries": removed,
        "entryCount": len(candidate["entries"]),
        "changes": changes,
        "proof": proof,
        "warnings": warnings,
        "qualityChecks": "pending",
        "unpublishedLocalCandidate": True,
    }
    out = ROOT / "ops/out/codex-fakhfakh-boundaries-11-20-candidate-20261007.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    report = build()
    print(json.dumps({k: v for k, v in report.items() if k not in ("proof", "changes")}, ensure_ascii=False))
