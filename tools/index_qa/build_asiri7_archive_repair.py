"""Build an offline Araf candidate from the independently repeated Asiri source.

This does not certify coverage or publish anything.  It preserves the measured
boundaries and confidences, records the rejected short-context result, and
requires the two wider arbitration windows before producing a local candidate.
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
PARENT = "fbf468c05fa3598df3103ce4f1cf53e093e9eb0ac719ad9b051d14c1a0cb1392"
KEY = "timings/hafs/3siri.jz"
SOURCE = "897ad7e2c99472111722247f362d135da0c25c449806260269a792a12f52d3f1"
URL = ("https://archive.org/download/002_20230924_202309/"
       "007%20-%20%D8%B3%D9%88%D8%B1%D8%A9%20%D8%A7%D9%84%D8%A3%D8%B9%D8%B1%D8%A7%D9%81.mp3")
PARENT_PATH = "ops/source-repair/parents/identity-3siri.jz"
METADATA = ("ops/out/codex-asiri7-archive-4917-metadata-20261006.json",
            "3b8b08f02c7fa2575eb35791fc8fa750d94b1adff7b48eb9b49f9697e2bd0a6f")
PRIMARY = ("ops/out/codex-asiri7-left-context-alignment-success-37433349375.json",
           "9426b3718b5b6a955ae6926263beeb66424a2dcad534c8b95172bbafdcdc8bac")
INDEPENDENT = ("ops/out/codex-asiri7-independent-29x5-success-37435925698.json",
               "1bb5ae038f42bc29ac27308946602809c844afece2badb36dde53ed150360853")
COMPARISON = ("ops/out/codex-asiri7-independent-comparison-20261006.json",
              "1857b0b5d6d2ea416a5c1ac500d15fcf6d0ec148cebf2424c07a02da9b0b378b")
TARGETED = ("ops/out/codex-asiri7-low-five-targeted-rejection-37439371822.json",
            "1d51139908b8e5b2a3fb3d13ca7862a30706cfa4bf64c5f8bb957b61d2b6dbb1")
EXPANDED = ("ops/out/codex-asiri7-ayah48-expanded-success-37442850692.json",
            "6c91c2e891042c940aa19d56078558f6758dffb8210450993a1fc4e6cc5bde5a")


def checked(spec, packed=False):
    path, expected = spec
    blob = (ROOT / path).read_bytes()
    C.require(hashlib.sha256(blob).hexdigest() == expected, "changed evidence: " + path)
    return json.loads(gzip.decompress(blob) if packed else blob)


def validate_evidence(primary, independent, comparison, targeted, expanded, metadata):
    for report in (primary, independent, expanded):
        C.require(report["measurementComplete"] and not report["errors"], "incomplete accepted measurement")
        C.require(report["textGenerationDisabled"], "Quran text generation was not disabled")
        C.require(report["source"]["sha256"] == SOURCE and report["source"]["url"] == URL,
                  "measurement source changed")
        alignment = report["alignment"]
        C.require(alignment["surah"] == 7 and alignment["riwaya"] == "hafs"
                  and alignment["engine"] == "ctc-quran-surah-1"
                  and len(alignment["entries"]) == 206, "alignment identity or population changed")
    pa, ia = primary["alignment"], independent["alignment"]
    C.require(pa["entries"] == ia["entries"], "independent full alignments disagree")
    for alignment, groups, overlap in ((pa, 8, 28), (ia, 9, 40)):
        chunked = alignment["chunkedAlignment"]
        C.require(len(chunked["groups"]) == groups and len(chunked["overlapAyahs"]) == overlap,
                  "full alignment grouping evidence changed")
        C.require(chunked["maxStartDisagreementSeconds"] <= 5
                  and chunked["maxEndDisagreementSeconds"] <= 5,
                  "full alignment overlap exceeds five seconds")
    exact = comparison["comparison"]
    C.require(exact == {"entriesCompared": 206, "exactStarts": 206, "exactEnds": 206,
                        "exactConfidences": 206, "maxStartDeltaMs": 0,
                        "maxEndDeltaMs": 0, "maxConfidenceDelta": 0,
                        "startEvidenceSeparated": True, "endEvidenceSeparated": True},
              "independent comparison changed")
    C.require({(w["name"], w["entries"]) for w in comparison["witnesses"]}
              >= {("opening", 10), ("middle-7:123-159", 37), ("ending", 8)},
              "head, middle, or ending witness missing")
    C.require(not targeted["measurementComplete"] and targeted["textGenerationDisabled"]
              and targeted["errors"] == [{"type": "ProbeError",
                                           "message": "targeted low-confidence boundary differs by more than five seconds"}],
              "rejected short-context evidence changed")
    td = {row["ayah"]: (row["startDeltaMs"], row["endDeltaMs"])
          for row in targeted["targetedLowConfidenceComparison"]}
    C.require(td == {13: (0, 0), 48: (0, 53535), 54: (0, 0), 131: (0, 0), 188: (0, 0)},
              "targeted low-confidence evidence changed")
    C.require(len(expanded["alignment"]["numericWindowAudit"]) == 2,
              "two expanded windows are required")
    C.require([row["ayah"] for row in expanded["expandedAyah48Comparison"]] == [48, 49, 50]
              and all(row["crossWindowStartDisagreementMs"] == 0
                      and row["crossWindowEndDisagreementMs"] == 0
                      and row["fullStartDeltaMs"] == 0
                      and row["fullEndDeltaMs"] == 0
                      for row in expanded["expandedAyah48Comparison"]),
              "expanded ayah-48 arbitration disagrees")
    for window in expanded["alignment"]["numericWindowAudit"]:
        for target in (47, 48, 49):
            local = next(e for e in window["entries"] if e["ayahIdx"] == target)
            full = pa["entries"][target]
            C.require((local["startMs"], local["endMs"]) == (full["startMs"], full["endMs"]),
                      "expanded window no longer matches the full boundary")
    C.require(metadata["file"]["sha256"] == SOURCE and metadata["requestedUrl"] == URL
              and metadata["decodedPcmMono16k"]["decodedWithoutErrors"]
              and not metadata["decodedPcmMono16k"]["longSilences"]
              and metadata["identityVerifiedAgainstKnownPerformance"],
              "source health or reader evidence changed")
    return copy.deepcopy(pa)


def build():
    metadata = checked(METADATA)
    primary, independent = checked(PRIMARY), checked(INDEPENDENT)
    comparison, targeted, expanded = checked(COMPARISON), checked(TARGETED), checked(EXPANDED)
    alignment = validate_evidence(primary, independent, comparison, targeted, expanded, metadata)
    alignment.update(fileRef=URL, sourceUrl=URL, sha256=SOURCE, audioSha256=SOURCE)

    parent_blob = (ROOT / PARENT_PATH).read_bytes()
    C.require(hashlib.sha256(parent_blob).hexdigest() == PARENT, "parent changed")
    parent = json.loads(gzip.decompress(parent_blob))
    C.require(parent["reciterId"] == "3siri" and parent["riwaya"] == "hafs"
              and len(parent["entries"]) == 6030
              and parent["missing"]["ids"] == [f"7:{n}" for n in range(1, 207)],
              "parent is not the measured Araf-drop index")
    source = C.source_registry.registered_source("hafs", "3siri", 7)
    C.require(source["url"] == URL and source["audio_sha256"] == SOURCE,
              "full Araf source is not registered exactly")

    with tempfile.TemporaryDirectory() as directory:
        directory = Path(directory)
        aligned = directory / "aligned.json"
        aligned.write_text(json.dumps(alignment, ensure_ascii=False), encoding="utf-8")
        merged = directory / "merged.jz"
        old = sys.argv
        sys.argv = [C.splice_surah.__file__, "--index", str(ROOT / PARENT_PATH),
                    "--surah", "7", "--aligned", str(aligned), "--url", URL,
                    "--registered-sources", "--alt-source", "--engine-tag", alignment["engine"],
                    "--out", str(merged)]
        try:
            C.splice_surah.main()
        finally:
            sys.argv = old
        C.require(Path(str(merged) + ".taken").read_text(encoding="utf-8") == "7",
                  "Araf was not spliced completely")
        candidate = json.loads(gzip.decompress(merged.read_bytes()))

    outside = lambda rows: [e for e in rows if not e["ayahId"].startswith("7:")]
    C.require(outside(candidate["entries"]) == parent["entries"], "entry outside Araf changed")
    C.require(len(candidate["entries"]) == 6236, "candidate is not complete")
    candidate["missing"] = {"count": 0, "byReason": {}, "ids": [],
                            "note": "سورة الأعراف مستعادة بقياس المصدر الكامل؛ يلزم QA قبل الاعتماد."}
    expected_shas = list(parent["audioSha256"])
    expected_shas[6] = SOURCE
    C.require(candidate["audioSha256"] == expected_shas
              and candidate["sourceBySurah"]["7"] == URL
              and candidate["engineBySurah"]["7"] == alignment["engine"],
              "source or engine declaration changed")
    rows = [e for e in candidate["entries"] if e["ayahId"].startswith("7:")]
    C.require(len(rows) == 206 and all(e["ayahId"] == f"7:{n}" for n, e in enumerate(rows, 1)),
              "Araf ids are incomplete")
    C.require(all((e["startMs"], e["endMs"], e["conf"])
                  == (m["startMs"], m["endMs"], m["conf"])
                  for e, m in zip(rows, alignment["entries"])),
              "measured boundary or confidence changed after splice")
    if "lowCount" in candidate:
        candidate["lowCount"] = sum(e.get("confBand") == "LOW" for e in candidate["entries"])
    moved, added, removed = T.entry_change_counts(parent["entries"], candidate["entries"])
    C.require(moved == removed == 0 and added == 206, "unexpected entry changes")
    proof = {
        "qualityClaim": False,
        "coverageCertified": False,
        "sourceUrl": URL,
        "audioSha256": SOURCE,
        "metadata": {"path": METADATA[0], "sha256": METADATA[1]},
        "primary": {"path": PRIMARY[0], "sha256": PRIMARY[1], "runId": 37433349375},
        "independent": {"path": INDEPENDENT[0], "sha256": INDEPENDENT[1], "runId": 37435925698},
        "comparison": {"path": COMPARISON[0], "sha256": COMPARISON[1]},
        "rejectedShortContext": {"path": TARGETED[0], "sha256": TARGETED[1], "runId": 37439371822},
        "expandedArbitration": {"path": EXPANDED[0], "sha256": EXPANDED[1], "runId": 37442850692},
        "alignmentIssues": copy.deepcopy(alignment["issues"]),
        "limits": [
            "Exact repeated forced boundaries are repeatability evidence, not 100% acoustic certification.",
            "Five LOW-confidence verses keep their measured confidences; none is upgraded.",
            "The rejected short window is preserved; two wider windows show that its 7:48 end drift was context-induced.",
            "Final-SHA audio QA, heard gate, public/manifest/frozen checks, and a stable general audit remain mandatory."
        ],
    }
    transform = C.repaired_transform(parent, candidate, [7], PARENT, KEY)
    transform.update(op="ctc_quran_surah_splice:7", fromSha256=PARENT, fromKey=KEY,
                     entriesSha256=T.entries_sha(candidate["entries"]),
                     parentEntriesSha256=T.entries_sha(parent["entries"]),
                     movedEntries=moved, addedEntries=added, removedEntries=removed,
                     by="build_asiri7_archive_repair",
                     reason="استعادة الأعراف كاملة من مصدر مطابق وهوية أداء مقيسة وإعادتين مستقلتين وتحكيم موسع",
                     sourceRepair=proof, unpublishedLocalCandidate=True)
    candidate["transform"] = transform
    why = T.promote.index_gate(candidate, parent=parent, parent_sha=PARENT)
    C.require(not why, "index gate: " + str(why))
    fatal, warnings, _ = R.structural(candidate, KEY, False)
    C.require(not fatal, "structural gate: " + str(fatal))
    C.require("7" in T.promote.census_surahs(candidate), "Araf omitted from census")

    payload = gzip.compress(json.dumps(candidate, ensure_ascii=False, separators=(",", ":"),
                                       allow_nan=False).encode("utf-8"), mtime=0)
    path = ROOT / "ops/source-repair/candidates/codex-asiri7-archive-20261006.jz"
    C.require(not path.exists() or path.read_bytes() == payload, "existing candidate differs")
    if not path.exists():
        path.write_bytes(payload)
    result = {
        "path": str(path.relative_to(ROOT)),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "key": f"timings-staging/hafs/3siri.{hashlib.sha256(payload).hexdigest()[:8]}.jz",
        "parentKey": KEY,
        "parentSha256": PARENT,
        "addedEntries": added,
        "changedEntries": moved,
        "proof": proof,
        "warnings": warnings,
        "qualityChecks": "pending",
        "heardGate": "pending",
        "unpublishedLocalCandidate": True,
    }
    out = ROOT / "ops/out/codex-asiri7-archive-candidate-20261006.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    report = build()
    print(json.dumps({k: v for k, v in report.items() if k != "proof"}, ensure_ascii=False))
