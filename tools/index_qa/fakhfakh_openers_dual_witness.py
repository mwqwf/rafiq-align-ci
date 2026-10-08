#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""شاهدٌ مستقل ثنائيّ مثبت لمطالع الفخفاخ الأربعة التي بقيت ``unknown``.

يقيس 7:1 و13:1 و27:1 و70:1 من المصادر المطابقة لبصمات المرشح، مع البسملة
والآية التالية، ولا يغيّر المرشح أو الإنتاج ولا يحوّل الرفض إلى توقيت مخمّن.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import gzip
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
for relative in ("tools/index_qa", "tools/alignment_v3", "tools/alignment", "tools/ci_fleet"):
    sys.path.insert(0, str(ROOT / relative))

import independent_window_pilot as P  # noqa: E402
import saad_free_decode as S  # noqa: E402
from archive_node import fetch_verified as archive_fetch_verified  # noqa: E402
from channel_mix import mono_filter  # noqa: E402

CANDIDATE = "ops/source-repair/candidates/codex-fakhfakh-boundaries-11-20-20261007.jz"
CANDIDATE_SHA = "a906d8c1c4d1440884d8cc6917190a7de93c0dfebfe1de69cc1efd6f732b3e90"
TARGETS = {
    "7:1": {
        "surah": 7,
        "url": "https://archive.org/download/48--kb--alhady--bn--altaher--alfakhfakh--by---qaloon---mp3--full--mushaf--qura/007Al-aaraf.mp3",
        "sha256": "421e0a5d50d5ef72bad9b815c3ee2bcbbb96a3c3f100c4dbf0631ee046ab7fcb",
        "originalTiny": {"surah": 7, "startMs": 6780,
                         "url": "https://archive.org/download/48--kb--alhady--bn--altaher--alfakhfakh--by---qaloon---mp3--full--mushaf--qura/007Al-aaraf.mp3",
                         "endMs": 16890, "verdict": "unknown", "heard": "الم"},
    },
    "13:1": {
        "surah": 13,
        "url": "https://archive.org/download/48--kb--alhady--bn--altaher--alfakhfakh--by---qaloon---mp3--full--mushaf--qura/013Arraad.mp3",
        "sha256": "0e8cab1bf1769f93770ea6f1ee952153df1b2873ef711a857b6f1dbe9a91e1ac",
        "originalTiny": {"surah": 13, "startMs": 7220,
                         "url": "https://archive.org/download/48--kb--alhady--bn--altaher--alfakhfakh--by---qaloon---mp3--full--mushaf--qura/013Arraad.mp3",
                         "endMs": 35440, "verdict": "unknown", "heard": "الم"},
    },
    "27:1": {
        "surah": 27,
        "url": "https://archive.org/download/48--kb--alhady--bn--altaher--alfakhfakh--by---qaloon---mp3--full--mushaf--qura/027Annaml.mp3",
        "sha256": "3e5ab2eef6c851e105f6e97bb401c1f3ef641469e515d83f766e8a7ada81f23d",
        "originalTiny": {"surah": 27, "startMs": 6560,
                         "url": "https://archive.org/download/48--kb--alhady--bn--altaher--alfakhfakh--by---qaloon---mp3--full--mushaf--qura/027Annaml.mp3",
                         "endMs": 19490, "verdict": "unknown", "heard": "طسم"},
    },
    "70:1": {
        "surah": 70,
        "url": "https://archive.org/download/48--kb--alhady--bn--altaher--alfakhfakh--by---qaloon---mp3--full--mushaf--qura/070Al-Maarij.mp3",
        "sha256": "641913ae2ff67ee36d9e8ac32616c5789963deff3b601fe8682065b07eee28fb",
        "originalTiny": {"surah": 70, "startMs": 7220,
                         "url": "https://archive.org/download/48--kb--alhady--bn--altaher--alfakhfakh--by---qaloon---mp3--full--mushaf--qura/070Al-Maarij.mp3",
                         "endMs": 12425, "verdict": "unknown",
                         "heard": "سان سايل بعذاب واقع"},
    },
}
MAX_SOURCE_BYTES = 64 * 1024 * 1024
RATE = 16_000


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
    shas = idx.get("audioSha256")
    require(isinstance(shas, list) and len(shas) == 114, "candidate source inventory missing")
    from common import load_index, surah_slice
    reference = load_index()
    inventory = {}
    for aid, spec in TARGETS.items():
        surah = spec["surah"]
        begin, stop, _ = surah_slice(reference, surah)
        count = stop - begin
        rows = [e for e in idx.get("entries", [])
                if str(e.get("ayahId", "")).startswith(f"{surah}:")]
        require([e.get("ayahId") for e in rows] == [f"{surah}:{k}" for k in range(1, count + 1)],
                f"surah {surah} entries are incomplete, duplicate or unordered")
        require(shas[surah - 1] == spec["sha256"], f"surah {surah} source SHA mismatch")
        require({e.get("fileRef") for e in rows} == {spec["url"]},
                f"surah {surah} source URL mismatch")
        require(all(type(e.get("startMs")) is int and type(e.get("endMs")) is int
                    and 0 <= e["startMs"] < e["endMs"] for e in rows),
                f"surah {surah} has invalid candidate boundaries")
        inventory[aid] = rows
    return idx, inventory, {"path": path, "sha256": digest, "bytes": len(raw)}


def fetch_source(spec, path):
    """ينزّل المصدر العام، ثم يستخدم عقدة Archive الموثقة فقط عند تعذره."""
    try:
        receipt = S.metadata.fetch(spec["url"], path, limit=MAX_SOURCE_BYTES)
        transport = "archive-download-primary"
    except Exception as primary:
        verified = archive_fetch_verified(spec["url"], path)
        if not verified:
            raise primary
        _, size = verified
        require(size <= MAX_SOURCE_BYTES, "verified source exceeds fixed byte limit")
        receipt = {"sha256": P.sha_file(path), "bytes": size}
        transport = "archive-node-publisher-size-md5"
    require(receipt["sha256"] == spec["sha256"] == P.sha_file(path),
            "downloaded source SHA mismatch")
    return {"url": spec["url"], "sha256": spec["sha256"], "bytes": receipt["bytes"],
            "transport": transport}


def strict_duration_ms(path):
    result = subprocess.run([
        "ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe",
        "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path),
    ], capture_output=True, timeout=30, check=False)
    require(result.returncode == 0 and not result.stderr.strip(), "strict duration probe failed")
    try:
        seconds = float(result.stdout.strip())
    except ValueError:
        raise ValueError("strict duration is not numeric") from None
    require(math.isfinite(seconds) and 0 < seconds <= 4 * 60 * 60, "strict duration outside bound")
    return int(seconds * 1000)


def decode_head(path, end_ms):
    """يفك من البدء إلى ما بعد النافذة قليلاً، ثم يقص العينات المطلوبة بالضبط."""
    require(type(end_ms) is int and 0 < end_ms <= 180_000, "opener head outside fixed bound")
    result = subprocess.run([
        "ffmpeg", "-nostdin", "-v", "error", "-i", str(path), *mono_filter(str(path)),
        "-t", f"{(end_ms + 250) / 1000:.3f}", "-f", "f32le", "-ac", "1", "-ar", str(RATE),
        "pipe:1",
    ], capture_output=True, timeout=180, check=False)
    require(result.returncode == 0 and not result.stderr.strip(), "strict opener decode failed")
    require(result.stdout and len(result.stdout) % 4 == 0, "invalid opener PCM bytes")
    pcm = np.frombuffer(result.stdout, dtype="<f4")
    needed = end_ms * RATE // 1000
    require(len(pcm) >= needed, "decoded PCM does not cover opener window")
    pcm = pcm[:needed].copy()
    require(np.isfinite(pcm).all(), "decoded opener contains NaN/Inf")
    return pcm


def prepare(idx, contract, sources):
    rows = {}
    for aid, spec in TARGETS.items():
        total_ms = sources[aid]["totalMs"]
        ids, window, texts = contract.plan(idx, aid, total_ms)
        require(window[1] <= len(sources[aid]["pcm"]) * 1000 // RATE,
                f"decoded head does not cover {aid}")
        rows[aid] = {"status": "pending", "originalTinyRow": copy.deepcopy(spec["originalTiny"]),
                     "proof": {"target": aid, "sourceSha256": spec["sha256"],
                     "canonicalTextChanged": False, "contextAyahIds": ids, "windowMs": window,
                     "totalMs": total_ms, "canonicalAlignmentInput": texts,
                     "runtime": dict(contract.RUNTIME), "models": {}}}
    return rows


def measure(idx, contract, backend, sources, report, checkpoint=lambda *_: None,
            clock=time.perf_counter):
    rows = prepare(idx, contract, sources)
    report["rows"] = rows
    report["modelTiming"] = {}
    for name in ("generic", "quran"):
        began = clock()
        try:
            model = backend.configure(name)
            loaded = clock()
            report["modelTiming"][name] = {"configureSeconds": loaded - began, "windows": 0}
            for aid, row in rows.items():
                proof = row["proof"]
                start, end = proof["windowMs"]
                result = {"alignmentModel": model}
                stamp = clock()
                try:
                    texts = proof["canonicalAlignmentInput"]
                    actual = list(texts) if name == "generic" else [backend.reference_text(t) for t in texts]
                    result["alignmentInput"] = actual
                    pcm = sources[aid]["pcm"][start * RATE // 1000:end * RATE // 1000]
                    raw = list(backend.segment(pcm, actual))
                    result["rawSegments"] = [[float(v) for v in segment] for segment in raw]
                    result.update(P.raw_result(raw, proof["contextAyahIds"], start, backend.conf))
                except Exception as exc:
                    result.update(entries=[], error=f"{type(exc).__name__}: {exc}")
                result["elapsedSeconds"] = clock() - stamp
                proof["models"][name] = result
                report["modelTiming"][name]["windows"] += 1
                checkpoint(aid, name, row)
            report["modelTiming"][name]["measureSeconds"] = clock() - loaded
        finally:
            backend.clear()
    for aid, row in rows.items():
        error = contract.witness_error(row["proof"], idx, aid)
        row.update(status="rejected" if error else "verified", reason=error)
    report["measurementComplete"] = all(
        set(row["proof"]["models"]) == {"generic", "quran"}
        and all(row["proof"]["models"][name].get("entries") for name in ("generic", "quran"))
        for row in rows.values())
    report["verifiedOpeners"] = [aid for aid, row in rows.items() if row["status"] == "verified"]
    report["notVerified"] = [aid for aid, row in rows.items() if row["status"] != "verified"]
    report["allUnknownOpenersResolved"] = report["measurementComplete"] and not report["notVerified"]
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
    report = {"schema": 1, "kind": "fakhfakh-openers-dual-witness",
              "targets": list(TARGETS), "candidateChanged": False, "productionChanged": False,
              "qualityClaim": False, "measurementComplete": False,
              "allUnknownOpenersResolved": False, "errors": [],
              "thresholds": {}, "provenance": {"runId": os.environ.get("GITHUB_RUN_ID", ""),
              "runSha": os.environ.get("GITHUB_SHA", ""), "toolSha256": P.sha_file(__file__)}}
    started = time.perf_counter()
    resources = contextlib.ExitStack()
    try:
        contract = P.load_contract()
        report["thresholds"] = {"targetConf": contract.TARGET_CONF,
            "anchorConf": contract.ANCHOR_CONF, "startTolMs": contract.START_TOL,
            "endTolMs": contract.END_TOL, "durLo": contract.DUR_LO,
            "durHi": contract.DUR_HI, "openerPadMs": contract.OPENER_PAD_MS}
        idx, _, report["candidate"] = read_candidate()
        require(os.environ.get("CTC_INT8") == "0" and os.environ.get("CTC_THREADS") == "2",
                "fixed float32/two-thread runtime required")
        require(os.environ.get("PILOT_CACHE_EXACT_HIT") == "true",
                "generic model cache exact hit required")
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
        sources = {}
        with tempfile.TemporaryDirectory(prefix="fakhfakh-openers-", dir=os.environ.get("RUNNER_TEMP")) as tmp:
            for aid, spec in TARGETS.items():
                audio = Path(tmp) / f"{spec['surah']:03d}.mp3"
                receipt = fetch_source(spec, audio)
                total_ms = strict_duration_ms(audio)
                _, window, _ = contract.plan(idx, aid, total_ms)
                pcm = decode_head(audio, window[1])
                require(P.sha_file(audio) == spec["sha256"], "source changed during opener decode")
                sources[aid] = {"receipt": receipt, "totalMs": total_ms, "pcm": pcm,
                                "decodedHeadMs": len(pcm) * 1000 // RATE}
            report["sources"] = {aid: {k: v for k, v in source.items() if k != "pcm"}
                                 for aid, source in sources.items()}
            witness = importlib.import_module("ci_spoken_census")
            with P.offline_model_loads(hub, specs, snapshots):
                measure(idx, contract, P.Backend(witness), sources, report,
                        checkpoint=lambda aid, name, row: emit({
                            "kind": report["kind"], "qualityClaim": False,
                            "candidateSha256": CANDIDATE_SHA, "target": aid, "model": name,
                            "originalTinyRow": row["originalTinyRow"],
                            "sourceSha256": TARGETS[aid]["sha256"],
                            "contextAyahIds": row["proof"]["contextAyahIds"],
                            "windowMs": row["proof"]["windowMs"],
                            "runtime": row["proof"]["runtime"],
                            "result": row["proof"]["models"][name]},
                            "FAKHFAKH_OPENERS_MODEL"))
            require(all(P.sha_file(Path(tmp) / f"{spec['surah']:03d}.mp3") == spec["sha256"]
                        for spec in TARGETS.values()), "source changed after measurement")
    except Exception as exc:
        report["errors"].append(f"{type(exc).__name__}: {exc}")
        report["measurementComplete"] = False
        report["allUnknownOpenersResolved"] = False
    finally:
        resources.close()
        report["elapsedSeconds"] = time.perf_counter() - started
        report["peakRssKiB"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        emit(report, "FAKHFAKH_OPENERS_DUAL_WITNESS")
    return 0 if report.get("allUnknownOpenersResolved") and not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
