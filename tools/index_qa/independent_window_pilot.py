#!/usr/bin/env python3
"""شاهد مستقل لجميع آيات المنافقون في مرشح Git، بلا تعديل census أو نشر.

يعيد استعمال خطة window_census وحارسها ونموذجيها المثبتين حرفياً. نهاية المقطع
الداخلي تشمل الوقفة حتى بدء التالية؛ الخام قبل هذا التحويل محفوظ أيضاً. هذا
pilot على مرشح واحد، وليس شهادة الإنتاج أو دقة مطلقة خارج عتبات الحارس.
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
import re
import resource
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
SURAH = 63
EXPECTED_IDS = [f"63:{a}" for a in range(1, 12)]
SOURCE_URL = "https://download.quranicaudio.com/quran/peshawa_qadir_al-kurdi/mp3/063.mp3"
SOURCE_SHA = "bbfc9570680b5172ad15e417ce0ef5b8aaf8d15e16ec6f12fe46ea1752243301"
CACHE_KEY = "ctc-model-jonatasgrosman-xlsr53-ar-v1"
DEFAULT_CANDIDATE = "ops/source-repair/candidates/codex-peshawa-s63-20261005-v2.jz"
DEFAULT_CANDIDATE_SHA = "00fbc75a874d45f80600ccf8f1f7bfe774aae5bffaba89cad3f37eb381997aee"
MAX_SOURCE_BYTES = 64 * 1024 * 1024
LIMITS = [
    "شهادة حدود 11 آية في مرشح Git واحد؛ لا شهادة نشر أو اكتمال 180 فهرساً",
    "نافذة مستقلة لكل آية بنموذجين وفق عتبات window_census القائمة، وليست دقة سمعية مطلقة",
    "النهاية الداخلية قد تشمل الوقفة حتى بدء التالية؛ نهاية anchor من heard ليست شاهداً هنا",
    "الرفض أو غياب القياس لا يثبت وحده أن التوقيت خاطئ؛ الأدلة الخام محفوظة",
    "التكرار لا يُحذف أو يُختزل؛ يظل في الصوت الأصلي وتفصل النماذج والحارس في نافذته",
    "لا census مصطنع ولا تغيير نص أو توقيت أو حارس أو كتابة للدلو",
    "كل نافذة تُحفظ في السجل قبل التالية؛ لا checkpoint دائم خارجه ولا استئناف حسابي تلقائي",
]


def sha_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def confined(path, directory, suffix):
    target = (ROOT / path).resolve()
    if not target.is_relative_to((ROOT / directory).resolve()) or target.suffix != suffix:
        raise ValueError(f"المسار يجب أن يكون داخل {directory} وبلاحقة {suffix}")
    return target


def read_candidate(path, digest, source_sha):
    if not re.fullmatch(r"[0-9a-f]{64}", digest or "") or source_sha != SOURCE_SHA:
        raise ValueError("تلزم بصمة مرشح كاملة وبصمة مصدر المنافقون المقيسة")
    path = confined(path, "ops/source-repair/candidates", ".jz")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("بايتات مرشح Git تخالف SHA المطلوبة")
    idx = json.loads(gzip.decompress(raw))
    if idx.get("reciterId") != "peshawa" or idx.get("riwaya") != "hafs":
        raise ValueError("هذا pilot مخصص لبيشوا، حفص، المنافقون فقط")
    shas = idx.get("audioSha256")
    if not isinstance(shas, list) or len(shas) != 114 or shas[62] != source_sha:
        raise ValueError("بصمة المصدر في موضع السورة 63 غير مطابقة")
    rows = [e for e in idx["entries"] if str(e.get("ayahId", "")).startswith("63:")]
    ids = [e.get("ayahId") for e in rows]
    if len(set(ids)) != len(ids) or not set(ids) <= set(EXPECTED_IDS):
        raise ValueError("مداخل المنافقون مكررة أو خارج عدّها المرجعي")
    if any(e.get("fileRef") != SOURCE_URL for e in rows):
        raise ValueError("مصدر إحدى آيات المنافقون لا يطابق التسجيل المقيس")
    # الغياب ليس نجاحاً ولا سبباً لإسقاط آيات الذيل من قائمة العمل.
    return idx, {"path": str(path.relative_to(ROOT)), "sha256": digest, "bytes": len(raw),
                 "sourceSha256": source_sha, "sourceUrl": SOURCE_URL, "rows": copy.deepcopy(rows)}


def load_contract():
    for relative in ("tools/alignment", "tools/alignment_v3", "tools/index_qa", "tools/ci_fleet"):
        directory = str(ROOT / relative)
        if directory not in sys.path:
            sys.path.insert(0, directory)
    return importlib.import_module("window_census_witness")


def model_specs(contract):
    return [dict(name=name, id=ident, revision=revision, weightsSha256=weights,
                 weightFile="pytorch_model.bin" if name == "generic" else "model.safetensors")
            for name, ident, revision, weights in contract.MODELS]


def require_cached_models(hub, specs, cache_root, inventory=None):
    """كل الاستدعاءات local_files_only=True، وبصمة كل وزن قبل تنزيل الصوت."""
    cache_root = Path(cache_root).resolve()
    if inventory is None:
        inventory = []
    for spec in specs:
        try:
            snapshot = Path(hub.snapshot_download(
                spec["id"], revision=spec["revision"], local_files_only=True,
                allow_patterns=["*.json", spec["weightFile"], "README.md"])).resolve()
        except Exception as exc:
            raise ValueError(f"cache النموذج {spec['name']} غير متاح محلياً؛ لم يُنزّل: {exc}") from exc
        if not snapshot.is_relative_to(cache_root):
            raise ValueError("snapshot خارج cache المستعاد")
        for filename in ("config.json", "vocab.json", "preprocessor_config.json", spec["weightFile"]):
            f = snapshot / filename
            if not f.is_file() or not f.resolve().is_relative_to(cache_root):
                raise ValueError(f"cache ناقص أو خارج جذره: {spec['name']}/{filename}")
        weight = snapshot / spec["weightFile"]
        if sha_file(weight) != spec["weightsSha256"]:
            raise ValueError(f"بصمة أوزان cache غير مطابقة: {spec['name']}")
        inventory.append({**spec, "snapshot": str(snapshot.relative_to(cache_root)),
                          "weightBytes": weight.stat().st_size, "localOnly": True})
    return inventory


@contextlib.contextmanager
def offline_model_loads(hub, specs, snapshots=None):
    """حتى configure القائم لا يستطيع طلب نموذج/نسخة أخرى أو الاتصال للتنزيل."""
    original = hub.snapshot_download
    allowed = {(s["id"], s["revision"]) for s in specs}
    snapshots = snapshots or {}
    if not set(snapshots).issubset(allowed):
        raise ValueError("snapshot مؤقت لنموذج غير مثبت")

    def local_snapshot(repo_id, *args, **kwargs):
        if args or (repo_id, kwargs.get("revision")) not in allowed:
            raise ValueError("تحميل نموذج غير مثبت في عقد pilot")
        identity = (repo_id, kwargs.get("revision"))
        if identity in snapshots:
            return str(snapshots[identity])
        kwargs["local_files_only"] = True
        return original(repo_id, **kwargs)

    hub.snapshot_download = local_snapshot
    try:
        yield
    finally:
        hub.snapshot_download = original


def download_source(directory):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "063.mp3"
    if path.exists():
        if sha_file(path) != SOURCE_SHA:
            raise ValueError("الصوت المحلي يخالف بصمة المصدر؛ لم يُستبدل بصمت")
        return path
    part = path.with_suffix(".part")
    request = urllib.request.Request(SOURCE_URL, headers={
        "User-Agent": "Mozilla/5.0 (rafiq-independent-window-pilot/1)"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response, part.open("wb") as out:
            if not response.geturl().startswith("https://"):
                raise ValueError("تحويل مصدر الصوت خارج HTTPS")
            size = 0
            while chunk := response.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_SOURCE_BYTES:
                    raise ValueError("تجاوز الصوت سقف pilot")
                out.write(chunk)
        if sha_file(part) != SOURCE_SHA:
            raise ValueError("الصوت المنزّل يخالف بصمة المصدر المطلوبة")
        part.replace(path)
        return path
    finally:
        part.unlink(missing_ok=True)


def raw_result(raw, ids, start, conf_fn):
    """احتفظ بالخام وبالنهاية النصية قبل إسناد نهاية المقطع إلى بدء التالية."""
    segments = [[float(st), float(en), float(score)] for st, en, score in raw]
    if len(segments) != len(ids) or any(not math.isfinite(v) for row in segments for v in row):
        raise ValueError("عدد المقاطع الخام أو قيمها غير صالح")
    original = [{"ayahId": aid, "startMs": start + int(st * 1000),
                 "endMs": start + int(en * 1000), "conf": conf_fn(score)}
                for aid, (st, en, score) in zip(ids, segments)]
    entries = copy.deepcopy(original)
    for i in range(len(entries) - 1):
        entries[i]["endMs"] = entries[i + 1]["startMs"]
    return {"rawSegments": segments, "rawEntries": original, "entries": entries}


def prepare_proofs(idx, total_ms, contract):
    rows = {}
    for aid in EXPECTED_IDS:
        if not any(e.get("ayahId") == aid and e.get("startMs") is not None for e in idx["entries"]):
            rows[aid] = {"status": "missing", "reason": "target has no timed entry"}
            continue
        try:
            ids, window, texts = contract.plan(idx, aid, total_ms)
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            rows[aid] = {"status": "unmeasured", "reason": str(exc)}
            continue
        rows[aid] = {"status": "pending", "proof": {
            "target": aid, "sourceSha256": SOURCE_SHA, "canonicalTextChanged": False,
            "contextAyahIds": ids, "windowMs": window, "totalMs": total_ms,
            "canonicalAlignmentInput": texts, "runtime": dict(contract.RUNTIME), "models": {}}}
    return rows


def measure(idx, pcm, contract, backend, report, checkpoint=lambda report, aid, name: None, clock=time.perf_counter):
    """النموذج خارج الحلقة، والآيات المرجعية الإحدى عشرة لا عدد المداخل الموجود."""
    total_ms = len(pcm) // 16
    rows = prepare_proofs(idx, total_ms, contract)
    report.update(rows=rows, totalMs=total_ms, pcmSamples=len(pcm), pcmBytes=len(pcm) * 4)
    report["inputWindowMsPerModel"] = sum(r["proof"]["windowMs"][1] - r["proof"]["windowMs"][0]
                                             for r in rows.values() if "proof" in r)
    report["modelTiming"] = {}
    for name in ("generic", "quran"):
        begin = clock()
        try:
            model = backend.configure(name)
            loaded = clock()
            report["modelTiming"][name] = {"configureSeconds": loaded - begin, "windows": 0}
            for aid, row in rows.items():
                proof = row.get("proof")
                if proof is None:
                    continue
                start, end = proof["windowMs"]
                actual = None
                stamp = clock()
                result = {"alignmentModel": model}
                try:
                    texts = proof["canonicalAlignmentInput"]
                    actual = list(texts) if name == "generic" else [backend.reference_text(t) for t in texts]
                    result["alignmentInput"] = actual
                    raw = list(backend.segment(pcm[start * 16:end * 16], actual))
                    # rawSegments محفوظة حتى عند رفض عددها/قيمها؛ NaN يُرمّز صراحة في السجل.
                    result["rawSegments"] = [[float(v) for v in segment] for segment in raw]
                    result.update(raw_result(raw, proof["contextAyahIds"], start, backend.conf))
                except Exception as exc:
                    result.update(entries=[], error=str(exc))
                result["elapsedSeconds"] = clock() - stamp
                proof["models"][name] = result
                report["modelTiming"][name]["windows"] += 1
                checkpoint(report, aid, name)
            report["modelTiming"][name]["measureSeconds"] = clock() - loaded
        finally:
            backend.clear()
    for aid, row in rows.items():
        if "proof" not in row:
            continue
        error = contract.witness_error(row["proof"], idx, aid)
        row.update(status="rejected" if error else "verified", reason=error)
    report["verified"] = [aid for aid in EXPECTED_IDS if rows[aid]["status"] == "verified"]
    report["notVerified"] = [aid for aid in EXPECTED_IDS if rows[aid]["status"] != "verified"]
    report["pilotBoundariesVerified"] = len(report["verified"]) == 11
    return report


class Backend:
    def __init__(self, witness):
        self.w = witness

    def configure(self, name):
        model = self.w.configure_generic() if name == "generic" else self.w.Q.configure()
        return {k: model[k] for k in ("id", "revision", "weightsSha256", "license")}

    def reference_text(self, text):
        return self.w.Q.reference_text(text)

    def segment(self, pcm, texts):
        return self.w.C._segment(self.w.C._emissions(pcm), len(pcm), texts)

    def conf(self, score):
        return self.w.C._conf(score)

    def clear(self):
        self.w.C._M.clear()
        gc.collect()


def json_safe(value):
    if isinstance(value, float) and not math.isfinite(value):
        return {"nonFinite": repr(value)}
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return value


def emit_report(report, path):
    from emit_probe_map import payload_lines
    safe = json_safe(report)
    # Validate the entire size before writing or printing a partial envelope.
    lines = list(payload_lines(safe, "INDEPENDENT_WINDOW_PILOT"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(safe, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    for line in lines:
        print(line, flush=True)


def emit_window(report, aid, name):
    """الشاهد الخام محفوظ فوراً حتى لو انقطع العمل؛ لا يُعد شهادة مقبولة منفرداً."""
    from emit_probe_map import payload_lines
    proof = report["rows"][aid]["proof"]
    partial = {"kind": "independent-window-pilot-part", "qualityClaim": False,
               "candidateSha256": report["candidate"]["sha256"],
               "sourceSha256": SOURCE_SHA, "provenance": report["provenance"],
               "target": aid, "model": name,
               "contextAyahIds": proof["contextAyahIds"], "windowMs": proof["windowMs"],
               "totalMs": proof["totalMs"], "canonicalAlignmentInput": proof["canonicalAlignmentInput"],
               "runtime": proof["runtime"], "result": proof["models"][name]}
    for line in payload_lines(json_safe(partial), "INDEPENDENT_WINDOW_PILOT_WINDOW"):
        print(line, flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", default=DEFAULT_CANDIDATE)
    parser.add_argument("--candidate-sha256", default=DEFAULT_CANDIDATE_SHA)
    parser.add_argument("--source-sha256", default=SOURCE_SHA)
    parser.add_argument("--out", default="ops/out/independent-window-pilot-peshawa-s63.json")
    parser.add_argument("--model-policy", choices=("cache-only", "quran-pinned-ephemeral"),
                        default="cache-only")
    args = parser.parse_args(argv)
    out = confined(args.out, "ops/out", ".json")
    for key in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_HUB_DISABLE_XET"):
        os.environ[key] = "1"
    started = time.perf_counter()
    resources = contextlib.ExitStack()
    report = {"schema": 1, "kind": "independent-window-pilot", "surah": SURAH,
              "expectedAyahs": EXPECTED_IDS, "readOnly": True, "productionChanged": False,
              "globalReady": False, "pilotBoundariesVerified": False, "errors": [], "limits": LIMITS,
              "provenance": {"runId": os.environ.get("GITHUB_RUN_ID", ""),
                             "runSha": os.environ.get("GITHUB_SHA", ""),
                             "toolSha256": sha_file(__file__)}}
    try:
        contract = load_contract()
        idx, report["candidate"] = read_candidate(args.candidate, args.candidate_sha256, args.source_sha256)
        if os.environ.get("CTC_INT8") != "0" or os.environ.get("CTC_THREADS") != "2":
            raise ValueError("يلزم float32 وCTC_THREADS=2 وفق العقد القائم")
        if os.environ.get("PILOT_CACHE_EXACT_HIT") != "true":
            raise ValueError("لم يثبت exact hit لمفتاح cache الموجود؛ لا تنزيل بديل")
        import huggingface_hub as hub
        specs = model_specs(contract)
        report["requiredModels"] = specs
        report["provenance"]["validatorSha256"] = sha_file(contract.__file__)
        cache_root = Path(os.environ.get("HF_HOME", str(ROOT / ".hf"))).resolve()
        t = time.perf_counter()
        report["cache"] = {"key": CACHE_KEY, "exactHit": True, "models": []}
        snapshots = {}
        report["modelPolicy"] = args.model_policy
        if args.model_policy == "cache-only":
            require_cached_models(hub, specs, cache_root, report["cache"]["models"])
        else:
            require_cached_models(hub, [s for s in specs if s["name"] == "generic"],
                                  cache_root, report["cache"]["models"])
            from pinned_ephemeral_models import quran_ephemeral_download
            evidence = resources.enter_context(quran_ephemeral_download(allow_download=True))
            spec = next(s for s in specs if s["name"] == "quran")
            if any(evidence[k] != spec[k] for k in ("id", "revision", "weightsSha256", "weightFile")):
                raise ValueError("النموذج المؤقت لا يطابق عقد الشاهد")
            snapshots[(spec["id"], spec["revision"])] = evidence["snapshot"]
            report["ephemeralModel"] = evidence
        report["cacheCheckSeconds"] = time.perf_counter() - t
        assets = ROOT / "core/quran/src/main/assets/quran"
        report["referenceSha256"] = {name: sha_file(assets / name) for name in ("index.jz", "text_hafs.jz")}
        t = time.perf_counter()
        audio = download_source(ROOT / "scratch/independent-window-pilot" / SOURCE_SHA)
        report["audioBytes"] = audio.stat().st_size
        report["downloadSeconds"] = time.perf_counter() - t
        run = importlib.import_module("run")
        t = time.perf_counter()
        pcm = run._full_decode_pcm(audio)
        report["decodeSeconds"] = time.perf_counter() - t
        if sha_file(audio) != SOURCE_SHA:
            raise ValueError("تغير الصوت أثناء الفك")
        witness = importlib.import_module("ci_spoken_census")
        with offline_model_loads(hub, specs, snapshots):
            measure(idx, pcm, contract, Backend(witness), report, checkpoint=emit_window)
        if sha_file(ROOT / args.candidate) != args.candidate_sha256 or sha_file(audio) != SOURCE_SHA:
            raise ValueError("تغير المرشح أو الصوت أثناء القياس")
    except Exception as exc:
        report["errors"].append(f"{type(exc).__name__}: {exc}")
        report["pilotBoundariesVerified"] = False
    finally:
        resources.close()
        report["elapsedSeconds"] = time.perf_counter() - started
        usage = resource.getrusage(resource.RUSAGE_SELF)
        report["processUsage"] = {"userSeconds": usage.ru_utime, "systemSeconds": usage.ru_stime,
                                  "peakRssKiB": usage.ru_maxrss, "platform": sys.platform}
        report["rawEvidenceBytes"] = len(json.dumps(json_safe(report.get("rows", {})),
                                                       ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        report["measuredWindowCount"] = sum(m.get("windows", 0) for m in report.get("modelTiming", {}).values())
        report.setdefault("notVerified", [a for a in EXPECTED_IDS if a not in report.get("verified", [])])
        # local imports work even if the contract could not be loaded.
        sys.path.insert(0, str(ROOT / "tools/ci_fleet"))
        emit_report(report, out)
    return 0 if report["pilotBoundariesVerified"] and not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
