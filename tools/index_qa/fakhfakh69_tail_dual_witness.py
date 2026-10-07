#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""شاهدُ مدى ثنائيّ مثبت لذيل الحاقة عند الفخفاخ،بلا بناء أو كتابة خارج السجل.

يحاذي النموذجان المثبتان الآيات 69:41–52 معاً من نهاية الآية40 حتى EOF.
لا ينتج فهرساً ولا يعتمد توقيتاً؛يحفظ القياسين الخامَين وحكم الحراس القائمة فقط.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import gc
import gzip
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import resource
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
for relative in ("tools/index_qa", "tools/alignment_v3", "tools/alignment", "tools/ci_fleet"):
    sys.path.insert(0, str(ROOT / relative))

import independent_window_pilot as P  # noqa: E402
import saad_free_decode as S  # noqa: E402

SURAH = 69
FIRST, LAST = 41, 52
TARGET_IDS = [f"{SURAH}:{k}" for k in range(FIRST, LAST + 1)]
CANDIDATE = "ops/source-repair/candidates/codex-fakhfakh-boundaries-11-20-20261007.jz"
CANDIDATE_SHA = "a906d8c1c4d1440884d8cc6917190a7de93c0dfebfe1de69cc1efd6f732b3e90"
SOURCE_URL = "https://archive.org/download/48--kb--alhady--bn--altaher--alfakhfakh--by---qaloon---mp3--full--mushaf--qura/069Al-Hekkah.mp3"
SOURCE_SHA = "758f7383dfee9e1bf6040cf909dacac589f3e3bbc813d6dd67b3d79771e20880"
MAX_SOURCE_BYTES = 32 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_candidate(path=CANDIDATE, digest=CANDIDATE_SHA):
    target = (ROOT / path).resolve()
    require(target.is_relative_to((ROOT / "ops/source-repair/candidates").resolve())
            and target.suffix == ".jz", "candidate path outside pinned directory")
    raw = target.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == digest == CANDIDATE_SHA, "candidate SHA mismatch")
    idx = json.loads(gzip.decompress(raw))
    require(idx.get("reciterId") == "fakhfakh_qalun" and idx.get("riwaya") == "qalun",
            "candidate identity mismatch")
    require(idx.get("audioSha256", [None] * 114)[SURAH - 1] == SOURCE_SHA,
            "candidate source SHA mismatch")
    rows = [e for e in idx.get("entries", []) if str(e.get("ayahId", "")).startswith(f"{SURAH}:")]
    require([e.get("ayahId") for e in rows] == [f"{SURAH}:{k}" for k in range(1, LAST + 1)],
            "surah 69 entries are incomplete, duplicate or unordered")
    require({e.get("fileRef") for e in rows} == {SOURCE_URL}, "candidate source URL mismatch")
    require(all(type(e.get("startMs")) is int and type(e.get("endMs")) is int
                and 0 <= e["startMs"] < e["endMs"] for e in rows), "invalid candidate boundaries")
    return idx, rows, {"path": path, "sha256": digest, "bytes": len(raw)}


def stable_prefix_rate(idx, contract):
    from common import load_index, load_text, norm, surah_slice
    begin, stop, _ = surah_slice(load_index(), SURAH)
    refs = load_text(idx["riwaya"])[begin:stop]
    chars = {f"{SURAH}:{k}": len(norm(text).replace(" ", ""))
             for k, text in enumerate(refs, 1)}
    prefix = [e for e in idx["entries"] if e["ayahId"].startswith(f"{SURAH}:")
              and int(e["ayahId"].split(":")[1]) <= 40]
    rates = [(e["endMs"] - e["startMs"]) / chars[e["ayahId"]] for e in prefix]
    require(len(rates) == 40 and all(math.isfinite(x) and x > 0 for x in rates),
            "stable-prefix rate unavailable")
    import statistics
    return statistics.median(rates), chars, refs


def raw_alignment(backend, name, pcm, texts, start_ms):
    model = backend.configure(name)
    actual = list(texts) if name == "generic" else [backend.reference_text(t) for t in texts]
    raw = list(backend.segment(pcm, actual))
    result = P.raw_result(raw, TARGET_IDS, start_ms, backend.conf)
    result.update({
        "alignmentModel": model,
        "alignmentInputSha256": hashlib.sha256(
            json.dumps(actual, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest(),
        "alignmentInputCount": len(actual),
    })
    return result


def assess(idx, rows, models, total_ms, rate, chars, contract):
    verdicts = []
    by_id = {e["ayahId"]: e for e in rows}
    for aid in TARGET_IDS:
        item = {"ayahId": aid, "accepted": False, "reasons": []}
        measured = {}
        for name in ("generic", "quran"):
            entry = next(e for e in models[name]["entries"] if e["ayahId"] == aid)
            raw = next(e for e in models[name]["rawEntries"] if e["ayahId"] == aid)
            measured[name] = {"startMs": entry["startMs"], "endMs": entry["endMs"],
                              "rawEndMs": raw["endMs"], "conf": entry["conf"]}
            if not math.isfinite(entry["conf"]) or entry["conf"] < contract.TARGET_CONF:
                item["reasons"].append(f"{name}:weak-confidence")
            duration = entry["endMs"] - entry["startMs"]
            expected = rate * chars[aid]
            if not contract.DUR_LO * expected <= duration <= contract.DUR_HI * expected:
                item["reasons"].append(f"{name}:duration-outside-bounds")
        start_spread = abs(measured["generic"]["startMs"] - measured["quran"]["startMs"])
        end_spread = abs(measured["generic"]["endMs"] - measured["quran"]["endMs"])
        if start_spread > contract.START_TOL:
            item["reasons"].append("models-disagree-start")
        if end_spread > contract.END_TOL:
            item["reasons"].append("models-disagree-end")
        current = by_id[aid]
        item.update(models=measured, startSpreadMs=start_spread, endSpreadMs=end_spread,
                    candidate={"startMs": current["startMs"], "endMs": current["endMs"]},
                    candidateStartDeltaMs={name: measured[name]["startMs"] - current["startMs"]
                                           for name in measured})
        if aid == TARGET_IDS[-1]:
            gaps = {name: total_ms - measured[name]["rawEndMs"] for name in measured}
            item["decodedEofGapMs"] = gaps
            if any(gap < 0 or gap > contract.TAIL_PAD_MS for gap in gaps.values()):
                item["reasons"].append("final-ayah-not-witnessed-through-eof")
        item["accepted"] = not item["reasons"]
        verdicts.append(item)
    return verdicts


def measure(idx, rows, pcm, contract, backend, report, checkpoint=lambda *_: None):
    from common import load_index, load_text, surah_slice
    from spoken_letters import alignment_text
    begin, stop, _ = surah_slice(load_index(), SURAH)
    refs = load_text(idx["riwaya"])[begin:stop]
    texts = [alignment_text(SURAH, k, refs[k - 1]) for k in range(FIRST, LAST + 1)]
    total_ms = len(pcm) // 16
    start_ms = rows[39]["endMs"]
    require(0 < start_ms < total_ms and total_ms - start_ms <= 120_000,
            "tail window outside fixed bound")
    rate, chars, _ = stable_prefix_rate(idx, contract)
    report.update(windowMs=[start_ms, total_ms], decodedDurationMs=total_ms,
                  stablePrefix="69:1-40", stablePrefixRateMsPerChar=rate,
                  thresholds={"targetConf": contract.TARGET_CONF, "startTolMs": contract.START_TOL,
                              "endTolMs": contract.END_TOL, "durLo": contract.DUR_LO,
                              "durHi": contract.DUR_HI, "tailPadMs": contract.TAIL_PAD_MS})
    measured = {}
    for name in ("generic", "quran"):
        try:
            measured[name] = raw_alignment(backend, name, pcm[start_ms * 16:total_ms * 16], texts, start_ms)
            checkpoint(name, measured[name])
        finally:
            backend.clear()
    report["models"] = measured
    report["perAyah"] = assess(idx, rows, measured, total_ms, rate, chars, contract)
    report["measurementComplete"] = all(len(measured[name]["entries"]) == len(TARGET_IDS)
                                         for name in ("generic", "quran"))
    report["acceptedAyahs"] = [x["ayahId"] for x in report["perAyah"] if x["accepted"]]
    report["rejectedAyahs"] = [x["ayahId"] for x in report["perAyah"] if not x["accepted"]]
    report["rangeWitnessAccepted"] = report["measurementComplete"] and not report["rejectedAyahs"]
    return report


def emit(value, prefix):
    from emit_probe_map import payload_lines
    for line in payload_lines(P.json_safe(value), prefix):
        print(line, flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-policy", choices=("cache-only", "quran-pinned-ephemeral"),
                        default="quran-pinned-ephemeral")
    args = parser.parse_args(argv)
    report = {"schema": 1, "kind": "fakhfakh69-tail-dual-witness", "surah": SURAH,
              "range": [FIRST, LAST], "candidateChanged": False, "productionChanged": False,
              "qualityClaim": False, "measurementComplete": False, "rangeWitnessAccepted": False,
              "errors": [], "provenance": {"runId": os.environ.get("GITHUB_RUN_ID", ""),
              "runSha": os.environ.get("GITHUB_SHA", ""), "toolSha256": P.sha_file(__file__)}}
    started = time.perf_counter()
    resources = contextlib.ExitStack()
    try:
        contract = P.load_contract()
        idx, rows, report["candidate"] = read_candidate()
        require(os.environ.get("CTC_INT8") == "0" and os.environ.get("CTC_THREADS") == "2",
                "fixed float32/two-thread runtime required")
        require(os.environ.get("PILOT_CACHE_EXACT_HIT") == "true", "generic model cache exact hit required")
        import huggingface_hub as hub
        specs = P.model_specs(contract)
        cache_root = Path(os.environ.get("HF_HOME", ROOT / ".hf")).resolve()
        report["modelPolicy"] = args.model_policy
        report["modelAcquisition"] = []
        snapshots = {}
        P.require_cached_models(hub, [s for s in specs if s["name"] == "generic"],
                                cache_root, report["modelAcquisition"])
        if args.model_policy == "cache-only":
            P.require_cached_models(hub, [s for s in specs if s["name"] == "quran"],
                                    cache_root, report["modelAcquisition"])
        else:
            from pinned_ephemeral_models import quran_ephemeral_download
            evidence = resources.enter_context(quran_ephemeral_download(allow_download=True))
            spec = next(s for s in specs if s["name"] == "quran")
            require(all(evidence[k] == spec[k] for k in ("id", "revision", "weightsSha256", "weightFile")),
                    "ephemeral quran model differs from pinned contract")
            snapshots[(spec["id"], spec["revision"])] = evidence["snapshot"]
            report["modelAcquisition"].append({k: v for k, v in evidence.items() if k != "snapshot"})
        assets = ROOT / "core/quran/src/main/assets/quran"
        report["referenceSha256"] = {name: P.sha_file(assets / name)
                                      for name in ("index.jz", "text_qalun.jz")}
        with tempfile.TemporaryDirectory(prefix="fakhfakh69-tail-", dir=os.environ.get("RUNNER_TEMP")) as tmp:
            audio = Path(tmp) / "069.mp3"
            receipt = S.metadata.fetch(SOURCE_URL, audio, limit=MAX_SOURCE_BYTES)
            require(receipt["sha256"] == SOURCE_SHA, "downloaded source SHA mismatch")
            report["source"] = {"url": SOURCE_URL, "sha256": SOURCE_SHA, "bytes": receipt["bytes"]}
            run = importlib.import_module("run")
            pcm = run._full_decode_pcm(audio)
            require(P.sha_file(audio) == SOURCE_SHA, "source changed during decode")
            witness = importlib.import_module("ci_spoken_census")
            with P.offline_model_loads(hub, specs, snapshots):
                measure(idx, rows, pcm, contract, P.Backend(witness), report,
                        checkpoint=lambda name, result: emit({"kind": report["kind"], "model": name,
                            "candidateSha256": CANDIDATE_SHA, "sourceSha256": SOURCE_SHA,
                            "windowMs": report["windowMs"], "result": result,
                            "qualityClaim": False}, "FAKHFAKH69_TAIL_MODEL"))
            require(P.sha_file(audio) == SOURCE_SHA, "source changed after measurement")
    except Exception as exc:
        report["errors"].append(f"{type(exc).__name__}: {exc}")
        report["measurementComplete"] = False
        report["rangeWitnessAccepted"] = False
    finally:
        resources.close()
        report["elapsedSeconds"] = time.perf_counter() - started
        report["peakRssKiB"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        emit(report, "FAKHFAKH69_TAIL_DUAL_WITNESS")
    return 0 if report["measurementComplete"] and not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
