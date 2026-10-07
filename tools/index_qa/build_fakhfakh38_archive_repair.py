"""Build a read-only Sad candidate from two matching Fakhfakh measurements.

No network, model, bucket, artifact, or cache write is performed here.  The
builder pins the production parent and every evidence file, then delegates the
row construction to the repository's guarded surah splicer.
"""
from __future__ import annotations

import copy
import gzip
import hashlib
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_registered_candidate as C
import run as R
import stage_transform as T

ROOT = Path(__file__).resolve().parents[2]
PARENT = "5bad920fd4994019caacc00b9edd6662941abae720ba0b3a2b41281016c23eef"
KEY = "timings/qalun/fakhfakh_qalun.jz"
PARENT_PATH = "ops/source-repair/parents/codex-short-tail-qalun-fakhfakh_qalun-5bad920f.jz"
SOURCE = "fded733764386de895b63df4b067f44accee12186785396a3f61928a0fa3c212"
URL = "https://archive.org/download/al-hadi-al-fakhfakh/038.mp3"
AUDIT = ("ops/source-repair/fakhfakh-qalun-38-archive-mirror-audit-20261006.json",
         "c1652760ce7c54ef19211e3f2cbbb725412b77425e3f03b5ca620a7938a9e3dc")
PRIMARY = ("ops/out/codex-fakhfakh38-archive-recovery-37544489570.json",
           "6fcad5cb6bd1354aae5d754274a3461b1ddf5ae4e6396f6464ce0776fb370c08")
INDEPENDENT = ("ops/out/codex-fakhfakh38-independent-audit-37546764143.json",
               "ef80882e5e9379323459688e43072ed8fe44ea0428fe2e8ad41b0093db1489db")


def checked(spec, packed=False):
    path, expected = spec
    blob = (ROOT / path).read_bytes()
    C.require(hashlib.sha256(blob).hexdigest() == expected, "changed evidence: " + path)
    return json.loads(gzip.decompress(blob) if packed else blob)


def validate_evidence(primary, independent, audit):
    for report in (primary, independent):
        C.require(report["measurementComplete"] and not report["errors"],
                  "incomplete accepted measurement")
        C.require(report["sourceId"].startswith("fakhfakh38_archive_2025")
                  and report["source"]["url"] == URL
                  and report["source"]["sha256"] == SOURCE,
                  "measurement source changed")
        alignment = report["alignment"]
        C.require(alignment["surah"] == 38 and alignment["riwaya"] == "qalun"
                  and alignment["engine"] == "ctc-quran-surah-1"
                  and alignment["totalMs"] == 973344
                  and not alignment["issues"]
                  and len(alignment["entries"]) == 88,
                  "alignment identity or population changed")
    pa, ia = primary["alignment"], independent["alignment"]
    C.require(pa["entries"] == ia["entries"], "independent full alignments disagree")
    chunked = ia["chunkedAlignment"]
    C.require(chunked["groupSize"] == 29 and chunked["overlap"] == 5
              and len(chunked["groups"]) == 4 and len(chunked["overlapAyahs"]) == 15
              and chunked["maxStartDisagreementSeconds"] <= 5
              and chunked["maxEndDisagreementSeconds"] <= 5,
              "independent overlap evidence changed")
    C.require({(row["witness"], row["ayah"]) for row in independent["boundaryComparisons"]}
              == {("opening-boundary", 1), ("ending-boundary", 88)}
              and all(row["primaryVsAuditStartDeltaMs"] == 0
                      and row["primaryVsAuditEndDeltaMs"] == 0
                      for row in independent["boundaryComparisons"]),
              "separate opening or ending boundary witness changed")
    witness_rows = independent["openingMiddleEndingComparison"]
    C.require({row["witness"] for row in witness_rows}
              == {"opening-1-5", "middle-40-48", "ending-81-88"}
              and {row["ayah"] for row in witness_rows}
              == {2, 3, 4, 43, 44, 45, 84, 85, 86, 87}
              and all(row["windowVsAuditStartDeltaMs"] == 0
                      and row["windowVsAuditEndDeltaMs"] == 0
                      and row["primaryVsAuditStartDeltaMs"] == 0
                      and row["primaryVsAuditEndDeltaMs"] == 0
                      for row in witness_rows),
              "opening, middle, or ending witness changed")
    C.require(audit["scope"] == {"riwaya": "qalun", "reciterId": "fakhfakh_qalun",
                                  "surah": 38}
              and audit["archive2025Mirror"]["url"] == URL
              and audit["archive2025Mirror"]["container"]["sha256"] == SOURCE
              and audit["archive2025Mirror"]["decodedMono16k"]["decodedWithoutErrors"]
              and audit["comparisons"]["archive2025EqualsPublisherDecodedMono16k"]
              and audit["comparisons"]["archive2025PublisherPcmBytesEqual"]
              and audit["comparisons"]["productionAndArchive2025DecodedDurationsEqual"],
              "source identity or decoded equality changed")
    windows = audit["comparisons"]["productionVersusArchive2025Mono8kCrossCorrelation"]["windows"]
    C.require([w["label"] for w in windows] == ["opener", "early", "middle", "late", "tail"]
              and all(abs(w["bestLagSamples"]) <= 1 and w["correlation"] >= .96 for w in windows),
              "production-performance comparison changed")
    return copy.deepcopy(pa)


def build():
    audit, primary, independent = checked(AUDIT), checked(PRIMARY), checked(INDEPENDENT)
    alignment = validate_evidence(primary, independent, audit)
    alignment.update(fileRef=URL, sourceUrl=URL, sha256=SOURCE, audioSha256=SOURCE)

    parent_blob = (ROOT / PARENT_PATH).read_bytes()
    C.require(hashlib.sha256(parent_blob).hexdigest() == PARENT, "parent changed")
    parent = json.loads(gzip.decompress(parent_blob))
    C.require(parent["reciterId"] == "fakhfakh_qalun" and parent["riwaya"] == "qalun"
              and len(parent["entries"]) == 6236 and len(parent["audioSha256"]) == 114,
              "parent identity changed")
    registered = C.source_registry.registered_source("qalun", "fakhfakh_qalun", 38)
    C.require(registered["url"] == URL and registered["audio_sha256"] == SOURCE,
              "measured source is not registered exactly")

    with tempfile.TemporaryDirectory() as directory:
        directory = Path(directory)
        aligned = directory / "aligned.json"
        aligned.write_text(json.dumps(alignment, ensure_ascii=False), encoding="utf-8")
        merged = directory / "merged.jz"
        previous = sys.argv
        sys.argv = [C.splice_surah.__file__, "--index", str(ROOT / PARENT_PATH),
                    "--surah", "38", "--aligned", str(aligned), "--url", URL,
                    "--registered-sources", "--alt-source", "--engine-tag", alignment["engine"],
                    "--out", str(merged)]
        try:
            C.splice_surah.main()
        finally:
            sys.argv = previous
        C.require(Path(str(merged) + ".taken").read_text(encoding="utf-8") == "38",
                  "Sad was not spliced completely")
        candidate = json.loads(gzip.decompress(merged.read_bytes()))

    outside = lambda rows: [e for e in rows if not e["ayahId"].startswith("38:")]
    C.require(outside(candidate["entries"]) == outside(parent["entries"]),
              "entry outside Sad changed")
    expected_shas = list(parent["audioSha256"])
    expected_shas[37] = SOURCE
    C.require(candidate["audioSha256"] == expected_shas
              and candidate["sourceBySurah"]["38"] == URL
              and candidate["engineBySurah"]["38"] == alignment["engine"],
              "source or engine declaration changed")
    rows = [e for e in candidate["entries"] if e["ayahId"].startswith("38:")]
    C.require(len(rows) == 88 and all(e["ayahId"] == f"38:{n}" for n, e in enumerate(rows, 1)),
              "Sad ids are incomplete")
    C.require(all(e["fileRef"] == URL and (e["startMs"], e["endMs"], e["conf"])
                  == (m["startMs"], m["endMs"], m["conf"])
                  for e, m in zip(rows, alignment["entries"])),
              "measured boundary, confidence, or source changed after splice")
    if "lowCount" in candidate:
        candidate["lowCount"] = sum(e.get("confBand") == "LOW" for e in candidate["entries"])
    moved, added, removed = T.entry_change_counts(parent["entries"], candidate["entries"])
    source_changed = sum(old != new for old, new in zip(
        [e for e in parent["entries"] if e["ayahId"].startswith("38:")], rows))
    C.require(moved == 84 and source_changed == 88 and added == removed == 0,
              "unexpected timing or source changes")
    proof = {
        "qualityClaim": False,
        "coverageCertified": False,
        "sourceUrl": URL,
        "audioSha256": SOURCE,
        "sourceAudit": {"path": AUDIT[0], "sha256": AUDIT[1]},
        "primary": {"path": PRIMARY[0], "sha256": PRIMARY[1], "runId": 37544489570},
        "independent": {"path": INDEPENDENT[0], "sha256": INDEPENDENT[1],
                        "runId": 37546764143},
        "startWitnessesSeparatedFromEnds": True,
        "limits": [
            "Repeated forced boundaries are measurement repeatability, not 100% acoustic certification.",
            "The source mirror is the same reader, riwaya, and performance; no Quran text or audio is generated.",
            "Final-SHA heard/census checks, public/manifest/frozen readback, and a stable general audit remain mandatory."
        ],
    }
    transform = C.repaired_transform(parent, candidate, [38], PARENT, KEY)
    transform.update(op="ctc_quran_surah_splice:38", fromSha256=PARENT, fromKey=KEY,
                     entriesSha256=T.entries_sha(candidate["entries"]),
                     parentEntriesSha256=T.entries_sha(parent["entries"]),
                     movedEntries=moved, addedEntries=added, removedEntries=removed,
                     by="build_fakhfakh38_archive_repair",
                     reason="Measured full Sad repair from matching Fakhfakh/Qalun performance with independent boundary witnesses",
                     sourceRepair=proof, unpublishedLocalCandidate=True)
    candidate["transform"] = transform
    why = T.promote.index_gate(candidate, parent=parent, parent_sha=PARENT)
    C.require(not why, "index gate: " + str(why))
    fatal, warnings, _ = R.structural(candidate, KEY, False)
    C.require(not fatal, "structural gate: " + str(fatal))
    C.require("38" in T.promote.census_surahs(candidate), "Sad omitted from census")

    payload = gzip.compress(json.dumps(candidate, ensure_ascii=False, separators=(",", ":"),
                                       allow_nan=False).encode("utf-8"), mtime=0)
    path = ROOT / "ops/source-repair/candidates/codex-fakhfakh38-archive-20261007.jz"
    C.require(not path.exists() or path.read_bytes() == payload, "existing candidate differs")
    if not path.exists():
        path.write_bytes(payload)
    result = {
        "path": str(path.relative_to(ROOT)),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "key": f"timings-staging/qalun/fakhfakh_qalun.{hashlib.sha256(payload).hexdigest()[:8]}.jz",
        "parentKey": KEY,
        "parentSha256": PARENT,
        "changedEntries": moved,
        "sourceChangedEntries": source_changed,
        "addedEntries": added,
        "removedEntries": removed,
        "entryCount": len(candidate["entries"]),
        "surahEntryCount": len(rows),
        "outsideEntriesPreserved": True,
        "boundarySummary": {
            "first": {k: rows[0][k] for k in ("ayahId", "startMs", "endMs", "conf")},
            "middle": {k: rows[43][k] for k in ("ayahId", "startMs", "endMs", "conf")},
            "last": {k: rows[-1][k] for k in ("ayahId", "startMs", "endMs", "conf")},
        },
        "proof": proof,
        "warnings": warnings,
        "qualityChecks": "pending",
        "heardGate": "pending",
        "unpublishedLocalCandidate": True,
    }
    out = ROOT / "ops/out/codex-fakhfakh38-archive-candidate-20261007.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    report = build()
    print(json.dumps({k: v for k, v in report.items() if k != "proof"}, ensure_ascii=False))
