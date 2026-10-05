#!/usr/bin/env python3
"""تفريغ حر محدود لسعد 45 و28؛ دليل تشخيص في السجل بلا محاذاة أو اعتماد.

نافذتان ثابتتان، وقناتان أصليتان، ونموذجان مستقلان. لا يُقرأ أي نص مرجعي.
كل قطعة تُطبع كاملة بما فيها التداخل؛ لا نخفي فواصل القطع بدمج النصوص.
"""
from __future__ import annotations

import argparse
import array
import contextlib
import gc
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
for _directory in ("tools/ci_fleet", "tools/index_qa", "tools/alignment_v3"):
    sys.path.insert(0, str(ROOT / _directory))
import source_metadata_probe as metadata
from emit_probe_map import payload_lines

RATE = 16000
CACHE_KEY = "ctc-model-jonatasgrosman-xlsr53-ar-v1"
MAX_SOURCE_BYTES = 32 * 1024 * 1024
MAX_SOURCE_SECONDS = 1500
CORE_SECONDS = 25
CONTEXT_SECONDS = 2
MODEL_DOWNLOAD_SECONDS = 600
SOURCES = (
    {"surah": 45, "url": "https://media.way2quran.com/saad-almqren/hafs-an-asim/45.mp3",
     "sha256": "b9963b5982ac331567c162a1481c135e8ffb456a8d62626adda668248801f76f",
     "bytes": 6117972, "windowSeconds": [0, 25]},
    {"surah": 28, "url": "https://media.way2quran.com/saad-almqren/hafs-an-asim/28.mp3",
     "sha256": "85f46007634846518394522eac40893dc2b2da62c27067f124ccc99499ad3f4b",
     "bytes": 21120980, "windowSeconds": [620, 690]},
)
MODELS = (
    {"name": "generic", "id": "jonatasgrosman/wav2vec2-large-xlsr-53-arabic",
     "revision": "af46c2d8531b8dcbb5e23b952f739b372c2e5d2d",
     "weightsSha256": "a0b26f6d9d3edfde1784aef863c192a8cc1e438a23b45910ab648531ebe1857b",
     "weightFile": "pytorch_model.bin"},
    {"name": "quran", "id": "rabah2026/wav2vec2-large-xlsr-53-arabic-quran-v_final",
     "revision": "b03a268c6ba1a693752307325ab376c86c3b12da",
     "weightsSha256": "bf65674a26eb4ef7042cedade96c3c8f8cbd04f3a7d1a68eadceec8ed0f99ecb",
     "weightFile": "model.safetensors"},
)
VERSIONS = {"torch": "2.6.0+cpu", "transformers": "4.49.0", "numpy": "1.26.4",
            "huggingface-hub": "0.29.3", "safetensors": "0.5.3", "tokenizers": "0.21.1"}


def sha_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_source(path, spec):
    if Path(path).stat().st_size != spec["bytes"] or sha_file(path) != spec["sha256"]:
        raise metadata.ProbeError("بايتات المصدر أو بصمته تخالف التسجيل المثبت؛ لا قياس")


class WindowCollector:
    """إحصاء التسجيل كله؛ حفظ النافذة المحددة فقط في RAM، بحدود عينات دقيقة."""
    def __init__(self, start_sample, end_sample):
        if not 0 <= start_sample < end_sample <= MAX_SOURCE_SECONDS * RATE:
            raise metadata.ProbeError("نافذة العينات خارج الحد")
        self.start, self.end = start_sample, end_sample
        self.stats = metadata.StereoPCMStats()
        self.pending = bytearray()
        self.window = bytearray()
        self.frames = 0

    def feed(self, block):
        if self.frames * 4 + len(self.pending) + len(block) > MAX_SOURCE_SECONDS * RATE * 4:
            raise metadata.ProbeError("مدة المصدر المفكوك تجاوزت الحد الثابت")
        self.stats.feed(block)
        self.pending.extend(block)
        size = len(self.pending) // 4 * 4
        next_frame = self.frames + size // 4
        left, right = max(self.start, self.frames), min(self.end, next_frame)
        if left < right:
            self.window.extend(self.pending[(left - self.frames) * 4:(right - self.frames) * 4])
        del self.pending[:size]
        self.frames = next_frame

    def finish(self):
        result = self.stats.finish()
        if self.pending or self.frames < self.end or len(self.window) != (self.end - self.start) * 4:
            raise metadata.ProbeError("المصدر المفكوك لا يغطي النافذة كاملة؛ لا قياس جزئي")
        return result

    def channels(self):
        self.finish()  # يمنع استعمال نافذة ناقصة، حتى خارج مسار التشغيل المعتاد.
        values = array.array("h", self.window)
        if sys.byteorder != "little":
            values.byteswap()
        channels = {}
        for name, offset in (("L", 0), ("R", 1)):
            part = values[offset::2]
            if sys.byteorder != "little":
                part.byteswap()
            channels[name] = part.tobytes()
        return channels


def strict_metadata(path):
    # حتى ffprobe ذي exit=0 لا يجيز أخطاء stderr؛ لا يُطبع stderr الخام.
    try:
        result = subprocess.run(["ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe",
            "-show_entries", "format=duration:stream=codec_type,codec_name,sample_rate,channels,channel_layout",
            "-of", "json", str(path)], capture_output=True, timeout=20, check=False)
        if result.returncode != 0 or result.stderr:
            raise metadata.ProbeError("فشل قياس الحاوية الصارم؛ لا اعتماد للخرج الجزئي")
        raw = json.loads(result.stdout)
        streams = [s for s in raw["streams"] if s.get("codec_type") == "audio"]
        if len(streams) != 1 or streams[0].get("channels") != 2:
            raise metadata.ProbeError("يلزم مسار صوت واحد بقناتين أصليتين؛ لا upmix أو downmix")
        duration = float(raw["format"]["duration"])
        if not math.isfinite(duration) or not 0 < duration <= MAX_SOURCE_SECONDS:
            raise metadata.ProbeError("مدة الحاوية غير صالحة أو تجاوزت الحد")
        return {"durationSeconds": duration, "audioStream": streams[0]}
    except (OSError, subprocess.TimeoutExpired, ValueError, KeyError, TypeError):
        raise metadata.ProbeError("تعذر قياس الحاوية الصارم") from None


def decode_source(path, spec):
    verify_source(path, spec)
    container = strict_metadata(path)
    start, end = [int(t * RATE) for t in spec["windowSeconds"]]
    collector = WindowCollector(start, end)
    # بلا -ss أو -t أو -ac: نثبت نجاح فك الملف كله، ونبقي القناتين الأصليتين.
    full = metadata._decode_pcm(path, collector, channel_arguments=[])
    verify_source(path, spec)
    channels = collector.channels()
    window = {"startSample": start, "endSampleExclusive": end,
              "startSeconds": start / RATE, "endSeconds": end / RATE,
              "samplesPerChannel": end - start, "channels": {}}
    for name, raw in channels.items():
        stats = metadata.PCMStats()
        stats.feed(raw)
        window["channels"][name] = stats.finish()
    report = {**spec, "reciterId": "saad", "riwaya": "hafs", "container": container,
              "fullRecordingNativeStereo": full, "window": window,
              "pcmMinusContainerSeconds": full["durationSeconds"] - container["durationSeconds"],
              "channelOrder": "first-and-second-native-channel", "sourceUnchanged": True,
              "identityCertified": False, "verseCoverageCertified": False}
    return report, channels


def chunk_plan(window_samples):
    if not 0 < window_samples <= 70 * RATE:
        raise metadata.ProbeError("حجم نافذة الاستدلال خارج الحد")
    chunks = []
    for start in range(0, window_samples, CORE_SECONDS * RATE):
        end = min(window_samples, start + CORE_SECONDS * RATE)
        chunks.append({"coreStartSample": start, "coreEndSampleExclusive": end,
                       "inputStartSample": max(0, start - CONTEXT_SECONDS * RATE),
                       "inputEndSampleExclusive": min(window_samples, end + CONTEXT_SECONDS * RATE)})
    return chunks


def argmax_runs(ids, probabilities, blank_id):
    """RLE يغطي كل إطار بما فيه blank؛ لا فلترة ثقة أو إسقاط تكرار خام."""
    if not ids or len(ids) != len(probabilities):
        raise metadata.ProbeError("خرج النموذج فارغ أو غير متسق")
    if any(type(token) is not int or token < 0 for token in ids):
        raise metadata.ProbeError("رمز argmax غير صالح")
    if any(not math.isfinite(p) or not 0 <= p <= 1 for p in probabilities):
        raise metadata.ProbeError("احتمال إطار غير صالح")
    runs = []
    start = 0
    for end in range(1, len(ids) + 1):
        if end == len(ids) or ids[end] != ids[start]:
            scores = probabilities[start:end]
            runs.append([ids[start], start, end, sum(scores) / len(scores), min(scores)])
            start = end
    return {"frames": len(ids), "blankTokenId": blank_id,
            "argmaxRunFields": ["tokenId", "startFrame", "endFrameExclusive", "meanPosterior", "minPosterior"],
            "argmaxRuns": runs,
            "posteriorIsCalibratedConfidence": False}


def frame_geometry(samples, kernels, strides):
    if not kernels or len(kernels) != len(strides) or any(type(v) is not int or v < 1 for v in (*kernels, *strides)):
        raise metadata.ProbeError("هندسة إطارات النموذج غير صالحة")
    frames, receptive, step = samples, 1, 1
    for kernel, stride in zip(kernels, strides):
        frames = (frames - kernel) // stride + 1
        receptive += (kernel - 1) * step
        step *= stride
    if frames < 1:
        raise metadata.ProbeError("القطعة أقصر من المجال الاستقبالي للنموذج")
    return {"expectedFrames": frames, "strideSamples": step, "receptiveFieldSamples": receptive,
            "firstFrameCenterSample": (receptive - 1) / 2,
            "centerRule": "absoluteInputStartSeconds + (firstFrameCenterSample + frame * strideSamples) / sampleRateHz"}


def validate_versions():
    actual = {name: importlib.metadata.version(name) for name in VERSIONS}
    if actual != VERSIONS:
        raise metadata.ProbeError("نسخ مكتبات الاستدلال لا تطابق النسخ المثبتة")
    return actual


def model_files(snapshot, spec):
    snapshot = Path(snapshot).resolve()
    if sha_file(snapshot / spec["weightFile"]) != spec["weightsSha256"]:
        raise metadata.ProbeError("بصمة وزن النموذج غير مطابقة")
    result = {}
    for path in sorted(snapshot.glob("*.json")):
        if path.stat().st_size > 4 * 1024 * 1024:
            raise metadata.ProbeError("ملف إعداد النموذج يتجاوز الحد")
        result[path.name] = {"bytes": path.stat().st_size, "sha256": sha_file(path)}
    for name in ("config.json", "vocab.json", "preprocessor_config.json"):
        if name not in result:
            raise metadata.ProbeError("ملفات النموذج المحلية غير كاملة")
    return result


class BoundedModelOpener:
    """حراس نقل metadata نفسها حول helper القرآني، دون تعديل helper المشترك."""
    def __init__(self, deadline, check_url, opener=None):
        self.deadline, self.check_url = deadline, check_url
        self.opener = opener or metadata.public_opener()

    def open(self, request, timeout=None):
        outer = self
        class CheckedRedirectOpener:
            def open(self, request, timeout):
                outer.check_url(request.full_url)
                return outer.opener.open(request, timeout=timeout)
        response = metadata.open_response(request.full_url, deadline=self.deadline,
                                          opener=CheckedRedirectOpener())
        try:
            self.check_url(response.geturl())
            if response.status != 200 or response.headers.get("Content-Range") is not None:
                raise metadata.ProbeError("ملف النموذج ليس استجابة HTTP200 كاملة")
        except Exception:
            response.close()
            raise
        class CheckedResponse:
            headers = response.headers
            def geturl(self):
                return response.geturl()
            def getcode(self):
                return response.status
            def read(self, size):
                # لا انتظار لملء MiB مع استجابة تنقط؛ والمهلة الصلبة تحيط بالسياق كله.
                return response.read1(size)
            def __enter__(self):
                return self
            def __exit__(self, *args):
                response.close()
        return CheckedResponse()


@contextlib.contextmanager
def model_snapshots(policy):
    """generic من cache فقط؛ القرآن إما cache فقط أو تنزيل صريح مثبت ومؤقت."""
    import huggingface_hub as hub
    from independent_window_pilot import require_cached_models
    cache_root = Path(os.environ["HF_HOME"]).resolve()
    if os.environ.get("SAAD_CACHE_EXACT_HIT") != "true":
        raise metadata.ProbeError("لم يثبت exact hit للـ cache القائم")
    generic = []
    try:
        require_cached_models(hub, [MODELS[0]], cache_root, generic)
    except Exception:
        raise metadata.ProbeError("generic المثبت غير متاح في cache؛ لا تنزيل بديل") from None
    generic_path = cache_root / generic[0]["snapshot"]
    if policy == "cache-only":
        quran = []
        try:
            require_cached_models(hub, [MODELS[1]], cache_root, quran)
        except Exception:
            raise metadata.ProbeError("Quran المثبت غير متاح في cache-only؛ لا fallback") from None
        yield {"generic": generic_path, "quran": cache_root / quran[0]["snapshot"]}, {
            "policy": policy, "cacheKey": CACHE_KEY, "exactHit": True, "models": generic + quran}
    elif policy == "quran-pinned-ephemeral":
        from pinned_ephemeral_models import quran_ephemeral_download, checked_public_url
        with contextlib.ExitStack() as cleanup:
            deadline = time.monotonic() + MODEL_DOWNLOAD_SECONDS
            # المؤقت يغطي التنزيل وحده؛ ينتهي قبل تنزيل الصوت أو الاستدلال، وتبقى
            # ملكية حذف المجلد المؤقت لدى ExitStack طوال القياس.
            with metadata.download_deadline(deadline):
                quran = cleanup.enter_context(quran_ephemeral_download(allow_download=True,
                    parent=os.environ.get("RUNNER_TEMP"),
                    opener=BoundedModelOpener(deadline, checked_public_url)))
            for key in ("id", "revision", "weightsSha256"):
                if quran[key] != MODELS[1][key]:
                    raise metadata.ProbeError("عقد التنزيل القرآني المؤقت يخالف النسخة المثبتة")
            yield {"generic": generic_path, "quran": Path(quran["snapshot"])}, {
                "policy": policy, "cacheKey": CACHE_KEY, "exactHit": True, "models": generic,
                "quranEphemeral": {k: v for k, v in quran.items() if k != "snapshot"}}
    else:
        raise metadata.ProbeError("سياسة تنزيل النموذج غير مسموحة")


class FreeCTC:
    def __init__(self, snapshot, spec):
        import numpy as np
        import torch
        from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
        self.np, self.torch = np, torch
        torch.set_num_threads(2)
        self.processor = Wav2Vec2Processor.from_pretrained(str(snapshot), local_files_only=True)
        if self.processor.feature_extractor.sampling_rate != RATE:
            raise metadata.ProbeError("تردد النموذج يخالف PCM المثبت")
        model, loading = Wav2Vec2ForCTC.from_pretrained(str(snapshot), local_files_only=True,
            torch_dtype=torch.float32, use_safetensors=spec["name"] == "quran",
            weights_only=True, attn_implementation="eager", output_loading_info=True)
        if any(loading.get(key) for key in ("missing_keys", "unexpected_keys", "mismatched_keys", "error_msgs")):
            raise metadata.ProbeError("لم تُحمّل كل أوزان النموذج كما هي؛ لا طبقات عشوائية أو مفاتيح متجاهلة")
        self.model = model.to("cpu").eval()
        if any(p.dtype != torch.float32 or p.device.type != "cpu" for p in self.model.parameters()):
            raise metadata.ProbeError("النموذج ليس CPU float32 كاملاً")
        self.vocabulary = self.processor.tokenizer.get_vocab()
        self.geometry = {"kernel": list(self.model.config.conv_kernel),
                         "stride": list(self.model.config.conv_stride)}

    def infer(self, raw):
        if not raw or len(raw) % 2 or len(raw) > (CORE_SECONDS + 2 * CONTEXT_SECONDS) * RATE * 2:
            raise metadata.ProbeError("حجم قطعة الاستدلال خارج الحد")
        # إعادة تمثيل عينات القناة فقط؛ لا جمع قناتين أو gain أو denoise أو time stretch.
        samples = self.np.frombuffer(raw, dtype="<i2").astype(self.np.float32) / 32768.0
        inputs = self.processor(samples, sampling_rate=RATE, return_tensors="pt", padding=False)
        with self.torch.inference_mode():
            logits = self.model(**inputs).logits[0]
            if logits.dtype != self.torch.float32 or not self.torch.isfinite(logits).all():
                raise metadata.ProbeError("خرج النموذج ليس float32 منتهيًا")
            probabilities, ids = logits.softmax(dim=-1).max(dim=-1)
            ids, probabilities = ids.tolist(), probabilities.tolist()
        evidence = argmax_runs(ids, probabilities, self.processor.tokenizer.pad_token_id)
        geometry = frame_geometry(len(samples), self.geometry["kernel"], self.geometry["stride"])
        if evidence["frames"] != geometry["expectedFrames"]:
            raise metadata.ProbeError("عدد إطارات النموذج لا يغطي هندسة المدخل كاملة")
        evidence["text"] = self.processor.tokenizer.decode(ids, group_tokens=True,
            skip_special_tokens=False, clean_up_tokenization_spaces=False)
        evidence["textMethod"] = "CTC-greedy-collapse-without-reference-or-language-model"
        evidence["frameTiming"] = {"method": "convolution-stride-and-receptive-field",
            **self.geometry, **geometry, "notWordOrVerseBoundaries": True}
        return evidence


def measure_window(backend, raw, source, channel, model_name, checkpoint=None):
    if len(raw) != int((source["windowSeconds"][1] - source["windowSeconds"][0]) * RATE * 2):
        raise metadata.ProbeError("عدد عينات النافذة لا يطابق الخطة")
    result = {"surah": source["surah"], "sourceSha256": source["sha256"], "channel": channel,
              "model": model_name, "windowSeconds": source["windowSeconds"],
              "pcmSha256": hashlib.sha256(raw).hexdigest(), "rawChunks": [],
              "canonicalTextInput": False, "forcedAlignment": False,
              "mergedTranscriptProduced": False, "versePresenceDecision": None,
              "rawEvidenceStorage": "complete-per-chunk-log-envelopes" if checkpoint else "inline"}
    for position, plan in enumerate(chunk_plan(len(raw) // 2), 1):
        piece = raw[plan["inputStartSample"] * 2:plan["inputEndSampleExclusive"] * 2]
        started = time.monotonic()
        inference = backend.infer(piece)
        item = {"chunk": position, **plan,
                "absoluteInputStartSeconds": source["windowSeconds"][0] + plan["inputStartSample"] / RATE,
                "absoluteInputEndSeconds": source["windowSeconds"][0] + plan["inputEndSampleExclusive"] / RATE,
                "inputPcmSha256": hashlib.sha256(piece).hexdigest(),
                "inferenceSeconds": time.monotonic() - started, **inference}
        if checkpoint:
            part = {**{k: v for k, v in result.items() if k != "rawChunks"}, "rawChunk": item,
                    "completeMeasurement": False}
            serialized = json.dumps(part, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
            checkpoint(part)
            # كل الإطارات في envelope القطعة أعلاه؛ التقرير النهائي manifest ذو بصمات
            # ونصوص كاملة، فلا يكرر RLE الضخم أو يتجاوز سقف أداة السجل مع صوت سريع.
            item = {k: v for k, v in item.items() if k != "argmaxRuns"}
            item["rawPartSha256"] = hashlib.sha256(serialized).hexdigest()
            item["rawPartBytes"] = len(serialized)
        result["rawChunks"].append(item)
    result["windowSamplesCovered"] = sum(c["coreEndSampleExclusive"] - c["coreStartSample"]
                                          for c in result["rawChunks"])
    return result


def emit(report, prefix="SAAD_FREE_ASR_REPORT"):
    for line in payload_lines(report, prefix):
        print(line, flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-policy", choices=("cache-only", "quran-pinned-ephemeral"), default="cache-only")
    args = parser.parse_args(argv)
    report = {"schema": 1, "kind": "saad-bounded-free-asr", "ok": False,
        "qualityClaim": False, "productionChanged": False, "coverageCertified": False,
        "uniqueWindowSeconds": 95, "nativeChannelsPerWindow": 2, "independentModels": 2,
        "inputSecondsWithContextPerModelChannel": 103, "totalModelInputSeconds": 412,
        "modelIndependence": "separate-pinned-checkpoints-and-forward-passes; shared-XLSR-family",
        "canonicalTextRead": False, "forcedAlignment": False, "modelSpecs": MODELS,
        "sampleRateHz": RATE, "modelDtype": "float32", "device": "cpu", "threads": 2,
        "limits": {"maxSourceBytes": MAX_SOURCE_BYTES, "maxSourceSeconds": MAX_SOURCE_SECONDS,
                   "coreSeconds": CORE_SECONDS, "contextSeconds": CONTEXT_SECONDS,
                   "workflowMinutes": 45, "modelPolicy": args.model_policy},
        "interpretation": ["الناتج تفريغ حر للنوافذ المحددة فقط؛ ليس شهادة حضور أو غياب آية",
            "كل قطعة وسياقها مطبوعان كاملين؛ النصوص المتداخلة لم تدمج ولم تختزل",
            "توقيت الإطار مشتق من عينات PCM؛ ليس حد كلمة أو آية معتمداً",
            "نموذجان منفصلان من عائلة XLSR نفسها؛ اتفاقهما لا يثبت وحده صحة التفريغ",
            "L/R تسميتان لترتيب القناتين الأصليتين؛ لا شهادة هوية أو تغطية من الإشارة وحدها"],
        "provenance": {"toolSha256": sha_file(__file__), "runId": os.environ.get("GITHUB_RUN_ID", ""),
                       "runSha": os.environ.get("GITHUB_SHA", ""),
                       "decoderHelperSha256": sha_file(metadata.__file__)},
        "sources": [], "models": [], "results": []}
    started = time.monotonic()
    phase = "environment"
    try:
        for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_HUB_DISABLE_XET"):
            os.environ[name] = "1"
        if os.environ.get("CTC_INT8") != "0" or os.environ.get("CTC_THREADS") != "2":
            raise metadata.ProbeError("يلزم CTC_INT8=0 وCTC_THREADS=2")
        report["versions"] = validate_versions()
        report["versions"]["python"] = sys.version.split()[0]
        report["decoderVersion"] = metadata.decoder_version()
        report["decoderBinariesSha256"] = {name: sha_file(shutil.which(name)) for name in ("ffmpeg", "ffprobe")}
        phase = "models"
        with model_snapshots(args.model_policy) as (snapshots, inventory):
            report["modelAcquisition"] = inventory
            for spec in MODELS:
                report["models"].append({**spec, "files": model_files(snapshots[spec["name"]], spec)})
            phase = "sources"
            windows = []
            with tempfile.TemporaryDirectory(prefix="rafiq-saad-free-", dir=os.environ.get("RUNNER_TEMP")) as tmp:
                for spec in SOURCES:
                    path = Path(tmp) / f"{spec['surah']}.mp3"
                    receipt = metadata.fetch(spec["url"], path, limit=MAX_SOURCE_BYTES)
                    if receipt["sha256"] != spec["sha256"] or receipt["bytes"] != spec["bytes"]:
                        raise metadata.ProbeError("التنزيل الحالي يخالف المصدر المثبت؛ لم تُصرف النماذج عليه")
                    proof, channels = decode_source(path, spec)
                    proof["download"] = receipt
                    report["sources"].append(proof)
                    windows.append((spec, channels))
                phase = "inference"
                for spec in MODELS:
                    backend = FreeCTC(snapshots[spec["name"]], spec)
                    report["models"][[s["name"] for s in MODELS].index(spec["name"])]["vocabulary"] = backend.vocabulary
                    # تسبق القطعَ هويّةُ الوزن/الأداة/المصدر والقاموس؛ تُحفظ حتى لو توقف العداء لاحقاً.
                    emit({k: v for k, v in report.items() if k != "results"}, "SAAD_FREE_ASR_PROVENANCE")
                    for source, channels in windows:
                        for channel in ("L", "R"):
                            result = measure_window(backend, channels[channel], source, channel, spec["name"],
                                checkpoint=lambda part: emit(part, "SAAD_FREE_ASR_PART"))
                            report["results"].append(result)
                    del backend
                    gc.collect()
                for spec in SOURCES:
                    verify_source(Path(tmp) / f"{spec['surah']}.mp3", spec)
        if len(report["results"]) != 8:
            raise metadata.ProbeError("عدد قياسات النماذج والقنوات غير كامل")
        report["ok"] = True
    except Exception as exc:
        # الاستثناء الخارجي قد يحمل رابط تنزيل موقعاً؛ نطبع نوعه والمرحلة فقط.
        report["error"] = {"phase": phase, "type": type(exc).__name__,
            "message": str(exc) if isinstance(exc, metadata.ProbeError) else "تعذر إكمال القياس؛ لم يعتمد الخرج الجزئي"}
    finally:
        report["elapsedSeconds"] = time.monotonic() - started
        report["peakRssKiB"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        emit(report)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
