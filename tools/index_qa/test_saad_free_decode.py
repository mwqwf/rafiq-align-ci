"""اختبارات دليل حر بصوت اصطناعي فقط؛ لا تنزيل نموذج أو قرآن."""
import array
import base64
import contextlib
import hashlib
import io
import json
import math
import signal
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
import urllib.error
import urllib.request
from unittest import mock
import wave

from tools.index_qa import saad_free_decode as S


class SourceTests(unittest.TestCase):
    def fixture(self, root, channels=2):
        path = Path(root) / "synthetic.wav"
        left = [int(12000 * math.sin(2 * math.pi * 440 * i / S.RATE)) for i in range(S.RATE * 2)]
        values = array.array("h", (v for sample in left for v in ((sample, -sample) if channels == 2 else (sample,))))
        if sys.byteorder != "little":
            values.byteswap()
        with wave.open(str(path), "wb") as stream:
            stream.setnchannels(channels)
            stream.setsampwidth(2)
            stream.setframerate(S.RATE)
            stream.writeframes(values.tobytes())
        spec = {"surah": 45, "url": "https://example.org/synthetic.wav", "sha256": S.sha_file(path),
                "bytes": path.stat().st_size, "windowSeconds": [0.25, 1.5]}
        return path, spec, values.tobytes()

    def test_real_stereo_decode_preserves_channels_and_exact_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, spec, raw = self.fixture(tmp)
            before = path.read_bytes()
            report, channels = S.decode_source(path, spec)
            samples = array.array("h", raw)
            if sys.byteorder != "little":
                samples.byteswap()
            for name, offset in (("L", 0), ("R", 1)):
                expected = samples[offset::2][4000:24000]
                if sys.byteorder != "little":
                    expected.byteswap()
                self.assertEqual(channels[name], expected.tobytes())
            self.assertEqual(report["window"]["samplesPerChannel"], 20000)
            self.assertEqual(report["fullRecordingNativeStereo"]["frames"], 32000)
            self.assertEqual(report["fullRecordingNativeStereo"]["correlationLR"], -1)
            self.assertTrue(report["fullRecordingNativeStereo"]["phaseCancellationSuspected"])
            self.assertTrue(report["fullRecordingNativeStereo"]["decodedWithoutErrors"])
            self.assertFalse(report["verseCoverageCertified"])
            self.assertEqual(before, path.read_bytes())

    def test_mono_is_rejected_without_artificial_second_channel(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, spec, _ = self.fixture(tmp, channels=1)
            with self.assertRaisesRegex(S.metadata.ProbeError, "قناتين أصليتين"):
                S.decode_source(path, spec)

    def test_changed_source_rejected_before_probe(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, spec, _ = self.fixture(tmp)
            spec["sha256"] = "0" * 64
            with mock.patch.object(S, "strict_metadata") as probe:
                with self.assertRaises(S.metadata.ProbeError):
                    S.decode_source(path, spec)
                probe.assert_not_called()

    def test_truncated_wav_is_not_accepted_as_complete_pcm(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, spec, _ = self.fixture(tmp)
            path.write_bytes(path.read_bytes()[:-513])
            spec.update(sha256=S.sha_file(path), bytes=path.stat().st_size)
            with self.assertRaises(S.metadata.ProbeError):
                S.decode_source(path, spec)

    def test_ffprobe_success_with_error_stderr_is_rejected_without_leaking_url(self):
        result = subprocess.CompletedProcess([], 0, b'{}', b'https://example.org/x?token=secret')
        with mock.patch.object(S.subprocess, "run", return_value=result):
            with self.assertRaises(S.metadata.ProbeError) as raised:
                S.strict_metadata(Path("unused"))
        self.assertNotIn("secret", str(raised.exception))

    def test_decoder_error_after_window_capture_never_returns_measurement(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, spec, raw = self.fixture(tmp)
            def failed_decode(path, collector, **kwargs):
                collector.feed(raw)
                raise S.metadata.ProbeError("أخطاء فك؛ الخرج مرفوض")
            with mock.patch.object(S.metadata, "_decode_pcm", side_effect=failed_decode):
                with self.assertRaises(S.metadata.ProbeError):
                    S.decode_source(path, spec)


class WindowTests(unittest.TestCase):
    def test_unaligned_pipe_blocks_keep_exact_sample_boundaries(self):
        values = array.array("h", [v for i in range(100) for v in (i, -i)])
        if sys.byteorder != "little":
            values.byteswap()
        raw = values.tobytes()
        collector = S.WindowCollector(11, 88)
        for start in range(0, len(raw), 13):
            collector.feed(raw[start:start + 13])
        self.assertEqual(collector.finish()["frames"], 100)
        self.assertEqual(collector.window, raw[44:352])
        self.assertEqual(len(collector.channels()["L"]), 77 * 2)

    def test_missing_tail_and_dangling_channel_byte_are_rejected(self):
        collector = S.WindowCollector(0, 10)
        collector.feed(b'\0' * 36)
        with self.assertRaises(S.metadata.ProbeError):
            collector.channels()
        collector.feed(b'\0' * 5)
        with self.assertRaises(S.metadata.ProbeError):
            collector.finish()

    def test_source_duration_limit_precedes_buffer_growth(self):
        with mock.patch.object(S, "MAX_SOURCE_SECONDS", 1):
            collector = S.WindowCollector(0, 10)
            with self.assertRaises(S.metadata.ProbeError):
                collector.feed(b'\0' * (S.RATE * 4 + 1))
            self.assertEqual(len(collector.window), 0)

    def test_fixed_plan_has_95_seconds_no_gap_and_max_29_second_inputs(self):
        total, input_samples = 0, 0
        for source in S.SOURCES:
            length = (source["windowSeconds"][1] - source["windowSeconds"][0]) * S.RATE
            plans = S.chunk_plan(length)
            self.assertEqual(plans[0]["coreStartSample"], 0)
            self.assertEqual(plans[-1]["coreEndSampleExclusive"], length)
            for previous, current in zip(plans, plans[1:]):
                self.assertEqual(previous["coreEndSampleExclusive"], current["coreStartSample"])
            for chunk in plans:
                self.assertLessEqual(chunk["inputStartSample"], chunk["coreStartSample"])
                self.assertGreaterEqual(chunk["inputEndSampleExclusive"], chunk["coreEndSampleExclusive"])
                self.assertLessEqual(chunk["inputEndSampleExclusive"] - chunk["inputStartSample"], 29 * S.RATE)
                total += chunk["coreEndSampleExclusive"] - chunk["coreStartSample"]
                input_samples += chunk["inputEndSampleExclusive"] - chunk["inputStartSample"]
        self.assertEqual(total, 95 * S.RATE)
        self.assertEqual(input_samples, 103 * S.RATE)

    def test_entire_raw_transcript_and_all_contexts_preserved_without_prompt(self):
        raw = (b'\x01\x00\xff\xff' * (70 * S.RATE // 2))
        seen, checkpoints = [], []
        class Backend:
            def infer(self, piece):
                seen.append(piece)
                return {"text": "صوت تجريبي مكرر مكرر " * 500, "frames": 1, "argmaxRuns": [[0, 0, 1, 1.0, 1.0]]}
        report = S.measure_window(Backend(), raw, S.SOURCES[1], "L", "generic", checkpoint=checkpoints.append)
        self.assertEqual(len(seen), 3)
        self.assertEqual(report["windowSamplesCovered"], 70 * S.RATE)
        self.assertEqual([r["absoluteInputStartSeconds"] for r in report["rawChunks"]], [620, 643, 668])
        self.assertEqual([r["absoluteInputEndSeconds"] for r in report["rawChunks"]], [647, 672, 690])
        self.assertTrue(all(r["text"].count("مكرر") == 1000 for r in report["rawChunks"]))
        self.assertFalse(report["mergedTranscriptProduced"])
        self.assertFalse(report["canonicalTextInput"])
        self.assertIsNone(report["versePresenceDecision"])
        self.assertEqual(len(checkpoints), 3)
        for chunk, piece, part in zip(report["rawChunks"], seen, checkpoints):
            self.assertEqual(chunk["inputPcmSha256"], hashlib.sha256(piece).hexdigest())
            self.assertEqual(piece, raw[chunk["inputStartSample"] * 2:chunk["inputEndSampleExclusive"] * 2])
            self.assertEqual(part["rawChunk"]["argmaxRuns"], [[0, 0, 1, 1.0, 1.0]])
            serialized = json.dumps(part, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
            self.assertEqual(chunk["rawPartSha256"], hashlib.sha256(serialized).hexdigest())
            self.assertEqual(chunk["rawPartBytes"], len(serialized))


class EvidenceTests(unittest.TestCase):
    def test_rle_preserves_blanks_repeats_and_even_low_posterior_frames(self):
        ids = [0, 0, 4, 4, 0, 4, 7, 7, 0]
        report = S.argmax_runs(ids, [0.01] * len(ids), 0)
        restored = [run[0] for run in report["argmaxRuns"] for _ in range(run[1], run[2])]
        self.assertEqual(restored, ids)
        self.assertEqual(report["frames"], 9)
        self.assertFalse(report["posteriorIsCalibratedConfidence"])

    def test_nonfinite_probabilities_and_missing_frames_are_rejected(self):
        for ids, probabilities in (([], []), ([1, 2], [.5]), ([1], [float('nan')]), ([1], [1.01])):
            with self.assertRaises(S.metadata.ProbeError):
                S.argmax_runs(ids, probabilities, 0)

    def test_frame_clock_uses_actual_convolution_geometry(self):
        result = S.frame_geometry(25 * S.RATE, [10, 3, 3, 3, 3, 2, 2], [5, 2, 2, 2, 2, 2, 2])
        self.assertEqual(result["strideSamples"], 320)
        self.assertEqual(result["receptiveFieldSamples"], 400)
        self.assertEqual(result["firstFrameCenterSample"], 199.5)
        self.assertEqual(result["expectedFrames"], 1249)

    def test_log_envelope_roundtrips_full_unicode_and_validates_sha(self):
        data = {"text": "تفريغ اصطناعي كامل مكرر " * 1000, "coverageCertified": False}
        target = io.StringIO()
        with contextlib.redirect_stdout(target):
            S.emit(data)
        lines = target.getvalue().splitlines()
        raw = base64.b64decode(''.join(line.split(' ', 2)[2] for line in lines if '_CHUNK ' in line))
        self.assertEqual(json.loads(raw), data)
        self.assertIn(hashlib.sha256(raw).hexdigest(), lines[0])
        self.assertIn(hashlib.sha256(raw).hexdigest(), lines[-1])

    def test_wrong_library_version_fails_closed(self):
        with mock.patch.object(S.importlib.metadata, "version", side_effect=lambda name: S.VERSIONS[name]):
            self.assertEqual(S.validate_versions(), S.VERSIONS)
        with mock.patch.object(S.importlib.metadata, "version", return_value="wrong"):
            with self.assertRaises(S.metadata.ProbeError):
                S.validate_versions()


class FreeInferenceTests(unittest.TestCase):
    def backend(self, frame_count=4, dtype="float32", finite=True):
        import numpy as np
        calls = []
        class Tensor:
            def __init__(self, data, tensor_dtype=dtype):
                self.data, self.dtype = np.asarray(data), tensor_dtype
            def __getitem__(self, item):
                return Tensor(self.data[item], self.dtype)
            def softmax(self, dim):
                values = np.exp(self.data - self.data.max(axis=dim, keepdims=True))
                return Tensor(values / values.sum(axis=dim, keepdims=True))
            def max(self, dim):
                return Tensor(self.data.max(axis=dim)), Tensor(self.data.argmax(axis=dim), "int64")
            def tolist(self):
                return self.data.tolist()
        class Processor:
            tokenizer = types.SimpleNamespace(pad_token_id=0)
            def __call__(self, samples, **kwargs):
                calls.append((samples.copy(), kwargs))
                return {"input_values": samples}
        processor = Processor()
        processor.tokenizer.decode = mock.Mock(return_value="synthetic repeated repeated")
        backend = S.FreeCTC.__new__(S.FreeCTC)
        backend.np = np
        backend.torch = types.SimpleNamespace(float32="float32", inference_mode=contextlib.nullcontext,
            isfinite=lambda values: types.SimpleNamespace(all=lambda: finite))
        backend.processor = processor
        logits = [[[3, 1], [1, 3], [1, 3], [3, 1]][:frame_count]]
        def model(**kwargs):
            self.assertEqual(set(kwargs), {"input_values"})
            return types.SimpleNamespace(logits=Tensor(logits))
        backend.model = model
        backend.geometry = {"kernel": [1], "stride": [1]}
        return backend, calls

    def test_actual_free_adapter_receives_only_unmixed_audio_and_keeps_raw_repeats(self):
        backend, calls = self.backend()
        samples = array.array('h', [1000, -1000, 0, 3000])
        if sys.byteorder != 'little':
            samples.byteswap()
        result = backend.infer(samples.tobytes())
        self.assertEqual(calls[0][1], {"sampling_rate": 16000, "return_tensors": "pt", "padding": False})
        self.assertEqual(str(calls[0][0].dtype), "float32")
        self.assertEqual(calls[0][0].tolist(), [1000 / 32768, -1000 / 32768, 0, 3000 / 32768])
        backend.processor.tokenizer.decode.assert_called_once_with([0, 1, 1, 0], group_tokens=True,
            skip_special_tokens=False, clean_up_tokenization_spaces=False)
        self.assertEqual(result["text"], "synthetic repeated repeated")
        self.assertEqual(result["frameTiming"]["expectedFrames"], 4)
        self.assertEqual([r[:3] for r in result["argmaxRuns"]], [[0, 0, 1], [1, 1, 3], [0, 3, 4]])

    def test_partial_frame_count_wrong_dtype_and_nonfinite_output_fail_closed(self):
        for kwargs in ({"frame_count": 3}, {"dtype": "float16"}, {"finite": False}):
            backend, _ = self.backend(**kwargs)
            with self.assertRaises(S.metadata.ProbeError):
                backend.infer(b'\0' * 8)


class ModelPolicyTests(unittest.TestCase):
    def test_real_download_helper_accepts_bounded_response_interface(self):
        from tools.alignment_v3 import pinned_ephemeral_models as E
        url = "https://huggingface.co/model/resolve/pinned/config.json"
        response = mock.Mock(status=200, headers={"Content-Length": "2"})
        response.geturl.return_value = url
        response.read1.side_effect = [b"{}", b""]
        opener = S.BoundedModelOpener(S.time.monotonic() + 5, E.checked_public_url)
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(S.metadata, "open_response", return_value=response):
            target = Path(directory) / "config.json"
            result = E.download_file(opener, url, target, limit=100, started=S.time.monotonic())
            self.assertEqual(target.read_bytes(), b"{}")
            self.assertEqual(result["sha256"], hashlib.sha256(b"{}").hexdigest())
        response.close.assert_called_once()

    def test_partial_model_response_is_closed_before_body_read(self):
        for status, headers in ((206, {}), (200, {"Content-Range": "bytes 0-3/10"})):
            response = mock.Mock(status=status, headers=headers)
            response.geturl.return_value = "https://huggingface.co/model/file"
            inner = mock.Mock()
            inner.open.return_value = response
            checked = mock.Mock()
            opener = S.BoundedModelOpener(S.time.monotonic() + 5, checked, inner)
            with mock.patch.object(S.metadata, "validate_url"):
                with self.assertRaises(S.metadata.ProbeError):
                    opener.open(urllib.request.Request("https://huggingface.co/model/file"))
            response.close.assert_called_once()
            response.read1.assert_not_called()

    def test_redirect_body_not_read_and_each_destination_checked(self):
        url = "https://huggingface.co/model/file"
        redirect = urllib.error.HTTPError(url, 302, "Found", {"Location": "https://cdn.hf.co/file?secret=hidden"}, io.BytesIO(b'x' * 100))
        redirect_body = redirect.fp
        response = mock.Mock(status=200, headers={})
        response.geturl.return_value = "https://cdn.hf.co/file?secret=hidden"
        response.read1.return_value = b'abcd'
        inner = mock.Mock()
        inner.open.side_effect = [redirect, response]
        checked = mock.Mock()
        opener = S.BoundedModelOpener(S.time.monotonic() + 5, checked, inner)
        with mock.patch.object(S.metadata, "validate_url"):
            with opener.open(urllib.request.Request(url)) as result:
                self.assertEqual(result.read(1024), b'abcd')
        self.assertTrue(redirect_body.closed)
        self.assertEqual(inner.open.call_count, 2)
        self.assertIn(mock.call("https://cdn.hf.co/file?secret=hidden"), checked.call_args_list)
        response.read.assert_not_called()
        response.close.assert_called_once()

    def test_cache_only_never_falls_back_to_download(self):
        import independent_window_pilot as pilot
        hub = types.ModuleType("huggingface_hub")
        helper = types.ModuleType("pinned_ephemeral_models")
        helper.quran_ephemeral_download = mock.Mock(side_effect=AssertionError("لا تنزيل"))
        def cached(hub, specs, cache_root, inventory):
            if specs[0]["name"] == "quran":
                raise ValueError("https://private.invalid/x?secret=hidden")
            inventory.append({"snapshot": "generic"})
        with mock.patch.dict(sys.modules, huggingface_hub=hub, pinned_ephemeral_models=helper), \
                mock.patch.dict(S.os.environ, HF_HOME="/tmp/cache", SAAD_CACHE_EXACT_HIT="true"), \
                mock.patch.object(pilot, "require_cached_models", side_effect=cached):
            with self.assertRaisesRegex(S.metadata.ProbeError, "لا fallback") as raised:
                with S.model_snapshots("cache-only"):
                    self.fail("لا نموذج قرآن")
        self.assertNotIn("secret", str(raised.exception))
        helper.quran_ephemeral_download.assert_not_called()

    def test_explicit_download_uses_exact_identity_and_cleans_context(self):
        import independent_window_pilot as pilot
        hub = types.ModuleType("huggingface_hub")
        helper = types.ModuleType("pinned_ephemeral_models")
        events = []
        helper.checked_public_url = mock.Mock()
        @contextlib.contextmanager
        def download(**kwargs):
            events.append(kwargs)
            try:
                yield {**S.MODELS[1], "snapshot": "/tmp/ephemeral-quran", "totalBytes": 123}
            finally:
                events.append("cleaned")
        helper.quran_ephemeral_download = download
        def cached(hub, specs, cache_root, inventory):
            self.assertEqual([s["name"] for s in specs], ["generic"])
            inventory.append({"snapshot": "generic"})
        with mock.patch.dict(sys.modules, huggingface_hub=hub, pinned_ephemeral_models=helper), \
                mock.patch.dict(S.os.environ, HF_HOME="/tmp/cache", SAAD_CACHE_EXACT_HIT="true", RUNNER_TEMP="/tmp"), \
                mock.patch.object(pilot, "require_cached_models", side_effect=cached):
            with S.model_snapshots("quran-pinned-ephemeral") as (paths, inventory):
                self.assertEqual(signal.getitimer(signal.ITIMER_REAL), (0.0, 0.0))
                self.assertEqual(paths["quran"], Path("/tmp/ephemeral-quran"))
                self.assertNotIn("snapshot", inventory["quranEphemeral"])
                self.assertEqual(inventory["quranEphemeral"]["weightsSha256"], S.MODELS[1]["weightsSha256"])
        self.assertEqual(events[0]["allow_download"], True)
        self.assertEqual(events[0]["parent"], "/tmp")
        self.assertIsInstance(events[0]["opener"], S.BoundedModelOpener)
        self.assertEqual(events[-1], "cleaned")

    def test_slow_download_has_hard_deadline_and_cleanup(self):
        import independent_window_pilot as pilot
        hub = types.ModuleType("huggingface_hub")
        helper = types.ModuleType("pinned_ephemeral_models")
        helper.checked_public_url = mock.Mock()
        events = []
        @contextlib.contextmanager
        def download(**kwargs):
            try:
                S.time.sleep(0.2)
                yield {**S.MODELS[1], "snapshot": "/tmp/unused"}
            finally:
                events.append("cleaned")
        helper.quran_ephemeral_download = download
        def cached(hub, specs, cache_root, inventory):
            inventory.append({"snapshot": "generic"})
        with mock.patch.dict(sys.modules, huggingface_hub=hub, pinned_ephemeral_models=helper), \
                mock.patch.dict(S.os.environ, HF_HOME="/tmp/cache", SAAD_CACHE_EXACT_HIT="true", RUNNER_TEMP="/tmp"), \
                mock.patch.object(pilot, "require_cached_models", side_effect=cached), \
                mock.patch.object(S, "MODEL_DOWNLOAD_SECONDS", 0.03):
            with self.assertRaisesRegex(S.metadata.ProbeError, "مهلة التنزيل"):
                with S.model_snapshots("quran-pinned-ephemeral"):
                    self.fail("انتهت المهلة قبل اكتمال التنزيل")
        self.assertEqual(events, ["cleaned"])
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL), (0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
