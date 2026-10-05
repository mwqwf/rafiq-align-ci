"""اختبارات المنتج على الحارس الحقيقي بمرجع اصطناعي؛ بلا شبكة أو نموذج صوتي."""
import base64
import copy
import gzip
import hashlib
import io
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from tools.index_qa import independent_window_pilot as P


class PCM:
    def __init__(self, start=0, end=120000 * 16):
        self.start, self.end = start, end

    def __len__(self):
        return self.end - self.start

    def __getitem__(self, cut):
        return PCM(cut.start, cut.stop)


class FakeBackend:
    def __init__(self, idx, contract):
        self.idx, self.contract = idx, contract
        self.calls, self.clears, self.configure_calls = [], 0, []
        self.weak = None
        self.repeat_first_end = False

    def configure(self, name):
        self.name = name
        self.configure_calls.append(name)
        _, ident, revision, weights = next(m for m in self.contract.MODELS if m[0] == name)
        return {"id": ident, "revision": revision, "weightsSha256": weights, "license": "Apache-2.0"}

    def reference_text(self, text):
        return text

    def segment(self, pcm, texts):
        self.calls.append((self.name, list(texts), len(pcm)))
        out = []
        for text in texts:
            if text == self.contract.BASMALA:
                st, en, aid = 200, 3000, "63:basmala"
            else:
                aid = "63:" + str(int(text.rsplit(" ", 1)[1]))
                row = next(e for e in self.idx["entries"] if e["ayahId"] == aid)
                st, en = row["startMs"], row["endMs"]
                if aid != "63:11":
                    en -= 1000
                if aid == "63:10" and self.repeat_first_end:
                    en = st + 3000  # كلام أول التكرار؛ التالية بعد التكرار كله.
            score = .59 if aid == self.weak and self.name == "quran" else .9
            out.append(((st - pcm.start / 16) / 1000, (en - pcm.start / 16) / 1000, score))
        return out

    def conf(self, score):
        return score

    def clear(self):
        self.clears += 1


class PilotTest(unittest.TestCase):
    def setUp(self):
        self.contract = P.load_contract()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.patch_root = patch.object(P, "ROOT", self.root)
        self.patch_root.start()
        self.addCleanup(self.patch_root.stop)
        self.addCleanup(self.tmp.cleanup)
        common = types.SimpleNamespace(load_index=lambda: {}, load_text=lambda riw: [f"verse {n:02}" for n in range(1, 12)],
                                       surah_slice=lambda idx, surah: (0, 11, None), norm=lambda text: text)
        spoken = types.SimpleNamespace(alignment_text=lambda s, a, text: text)
        self.module_patch = patch.dict("sys.modules", {"common": common, "spoken_letters": spoken})
        self.module_patch.start()
        self.addCleanup(self.module_patch.stop)
        self.idx = {"reciterId": "peshawa", "riwaya": "hafs", "audioSha256": [P.SOURCE_SHA] * 114,
                    "entries": [{"ayahId": f"63:{a}", "startMs": 4000 + (a - 1) * 10000,
                                 "endMs": 4000 + a * 10000, "fileRef": P.SOURCE_URL, "conf": .092}
                                for a in range(1, 12)]}

    def run_measure(self, **kwargs):
        backend = FakeBackend(self.idx, self.contract)
        for k, v in kwargs.items():
            setattr(backend, k, v)
        original = copy.deepcopy(self.idx)
        report = P.measure(self.idx, PCM(end=140000 * 16), self.contract, backend, {})
        self.assertEqual(self.idx, original)
        return report, backend

    def test_all_eleven_including_middle_and_tail_and_both_models(self):
        report, backend = self.run_measure()
        self.assertTrue(report["pilotBoundariesVerified"])
        self.assertEqual(report["verified"], P.EXPECTED_IDS)
        self.assertEqual(len(backend.calls), 22)
        self.assertEqual(backend.configure_calls, ["generic", "quran"])
        self.assertEqual(backend.clears, 2)
        self.assertGreater(report["inputWindowMsPerModel"], 114000)
        for a in (1, 6, 11):
            proof = report["rows"][f"63:{a}"]["proof"]
            self.assertIsNone(self.contract.witness_error(proof, self.idx, f"63:{a}"))
            self.assertEqual(set(proof["models"]), {"generic", "quran"})

    def test_missing_middle_keeps_last_ayah_in_scope(self):
        self.idx["entries"] = [e for e in self.idx["entries"] if e["ayahId"] != "63:5"]
        report, backend = self.run_measure()
        self.assertEqual(list(report["rows"]), P.EXPECTED_IDS)
        self.assertEqual(report["rows"]["63:5"]["status"], "missing")
        self.assertEqual(report["rows"]["63:4"]["status"], "unmeasured")
        self.assertEqual(report["rows"]["63:6"]["status"], "unmeasured")
        self.assertEqual(report["rows"]["63:11"]["status"], "verified")
        self.assertFalse(report["pilotBoundariesVerified"])

    def test_missing_tail_is_not_shortened_scope(self):
        self.idx["entries"].pop()
        report, _ = self.run_measure()
        self.assertEqual(report["rows"]["63:11"]["status"], "missing")
        self.assertEqual(report["rows"]["63:10"]["status"], "unmeasured")
        self.assertFalse(report["pilotBoundariesVerified"])

    def test_end_contract_preserves_raw_gap_and_uses_next_start(self):
        report, _ = self.run_measure()
        proof = report["rows"]["63:6"]["proof"]
        result = proof["models"]["generic"]
        raw = next(e for e in result["rawEntries"] if e["ayahId"] == "63:6")
        final = next(e for e in result["entries"] if e["ayahId"] == "63:6")
        self.assertEqual(final["endMs"] - raw["endMs"], 1000)
        tail = report["rows"]["63:11"]["proof"]["models"]["generic"]
        self.assertEqual(tail["rawEntries"][-1], tail["entries"][-1])

    def test_low_independent_target_confidence_rejects_without_lowering_threshold(self):
        report, _ = self.run_measure(weak="63:6")
        self.assertEqual(report["rows"]["63:6"]["status"], "rejected")
        self.assertIn("confidence", report["rows"]["63:6"]["reason"])
        self.assertFalse(report["pilotBoundariesVerified"])
        self.assertEqual(self.contract.TARGET_CONF, .60)

    def test_repeat_remains_in_audio_window_and_raw_text_not_duplicated(self):
        self.idx["entries"][9]["endMs"] += 10000
        for name in ("startMs", "endMs"):
            self.idx["entries"][10][name] += 10000
        report, backend = self.run_measure(repeat_first_end=True)
        self.assertTrue(report["pilotBoundariesVerified"])
        proof = report["rows"]["63:10"]["proof"]
        self.assertEqual(proof["contextAyahIds"], ["63:9", "63:10", "63:11"])
        for model in proof["models"].values():
            self.assertEqual(model["alignmentInput"].count("verse 10"), 1)
            self.assertEqual(model["rawEntries"][1]["endMs"], 97000)
            self.assertEqual(model["entries"][1]["endMs"], 114000)
        self.assertIn(("generic", ["verse 09", "verse 10", "verse 11"], 40000 * 16), backend.calls)

    def test_model_failure_retains_other_model_and_raw_context(self):
        backend = FakeBackend(self.idx, self.contract)
        original = backend.segment
        def fail(pcm, texts):
            if backend.name == "quran" and texts == ["verse 10", "verse 11"]:
                raise RuntimeError("intentional test failure")
            return original(pcm, texts)
        backend.segment = fail
        report = P.measure(self.idx, PCM(), self.contract, backend, {})
        row = report["rows"]["63:11"]
        self.assertEqual(row["status"], "rejected")
        self.assertIn("rawEntries", row["proof"]["models"]["generic"])
        self.assertEqual(row["proof"]["models"]["quran"]["error"], "intentional test failure")

    def test_wrong_source_and_different_end_do_not_certify(self):
        report, _ = self.run_measure()
        proof = report["rows"]["63:11"]["proof"]
        proof["sourceSha256"] = "a" * 64
        self.assertIsNotNone(self.contract.witness_error(proof, self.idx, "63:11"))
        proof["sourceSha256"] = P.SOURCE_SHA
        proof["models"]["quran"]["entries"][-1]["endMs"] -= 900
        self.assertIn("boundary", self.contract.witness_error(proof, self.idx, "63:11"))

    def candidate_file(self):
        file = self.root / P.DEFAULT_CANDIDATE
        file.parent.mkdir(parents=True, exist_ok=True)
        raw = gzip.compress(json.dumps(self.idx).encode())
        file.write_bytes(raw)
        return file, hashlib.sha256(raw).hexdigest()

    def test_candidate_sha_source_url_and_duplicates_checked_before_measurement(self):
        file, sha = self.candidate_file()
        idx, meta = P.read_candidate(file, sha, P.SOURCE_SHA)
        self.assertEqual(idx, self.idx)
        with self.assertRaisesRegex(ValueError, "SHA"):
            P.read_candidate(file, "f" * 64, P.SOURCE_SHA)
        for mutation in ("url", "duplicate", "audio"):
            with self.subTest(mutation=mutation):
                changed = copy.deepcopy(self.idx)
                if mutation == "url": changed["entries"][0]["fileRef"] = "https://example.org/other.mp3"
                if mutation == "duplicate": changed["entries"].append(changed["entries"][0])
                if mutation == "audio": changed["audioSha256"][62] = "f" * 64
                raw = gzip.compress(json.dumps(changed).encode()); file.write_bytes(raw)
                with self.assertRaises(ValueError):
                    P.read_candidate(file, hashlib.sha256(raw).hexdigest(), P.SOURCE_SHA)

    def test_candidate_path_escape_and_missing_are_explicit(self):
        with self.assertRaises(ValueError):
            P.read_candidate("../elsewhere.jz", "f" * 64, P.SOURCE_SHA)
        with self.assertRaises(FileNotFoundError):
            P.read_candidate(P.DEFAULT_CANDIDATE, "f" * 64, P.SOURCE_SHA)

    def test_full_log_round_trip_is_lossless_and_hash_checked(self):
        report, _ = self.run_measure()
        with patch("sys.stdout", new_callable=io.StringIO) as out:
            P.emit_report(report, self.root / "ops/out/pilot.json")
        lines = out.getvalue().splitlines()
        encoded = "".join(line.split(" ", 2)[2] for line in lines if "_CHUNK " in line)
        raw = base64.b64decode(encoded)
        self.assertEqual(json.loads(raw), report)
        self.assertIn("bytes=" + str(len(raw)), lines[0])
        self.assertIn("sha256=" + hashlib.sha256(raw).hexdigest(), lines[-1])

    def test_raw_nonfinite_is_rejected_and_explicitly_encoded(self):
        with self.assertRaises(ValueError):
            P.raw_result([(0, 1, float("nan"))], ["63:1"], 0, lambda x: x)
        self.assertEqual(P.json_safe({"score": float("nan")}), {"score": {"nonFinite": "nan"}})

    def test_each_completed_window_is_logged_with_identity_before_next_measurement(self):
        report = {"candidate": {"sha256": "b" * 64}, "provenance": {"runId": "123"}}
        parts = []
        def checkpoint(report, aid, name):
            with patch("sys.stdout", new_callable=io.StringIO) as out:
                P.emit_window(report, aid, name)
            chunks = [line.split(" ", 2)[2] for line in out.getvalue().splitlines() if "_CHUNK " in line]
            parts.append(json.loads(base64.b64decode("".join(chunks))))
        P.measure(self.idx, PCM(), self.contract, FakeBackend(self.idx, self.contract), report, checkpoint)
        self.assertEqual(len(parts), 22)
        self.assertEqual([(p["model"], p["target"]) for p in parts],
                         [(name, aid) for name in ("generic", "quran") for aid in P.EXPECTED_IDS])
        self.assertEqual(parts[-1]["candidateSha256"], "b" * 64)
        self.assertFalse(parts[-1]["qualityClaim"])
        self.assertIn("rawSegments", parts[-1]["result"])


class CacheOnlyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.snap = self.root / "hub/models--test/snapshots/pinned"
        self.snap.mkdir(parents=True)
        for f in ("config.json", "vocab.json", "preprocessor_config.json"):
            (self.snap / f).write_text("{}")
        (self.snap / "model.safetensors").write_bytes(b"test pinned weights")
        self.spec = {"id": "test/model", "revision": "pinned", "name": "quran",
                     "weightFile": "model.safetensors", "weightsSha256": P.sha_file(self.snap / "model.safetensors")}
        self.hub = types.SimpleNamespace(snapshot_download=Mock(return_value=str(self.snap)))

    def test_preflight_is_local_only_and_hashes_actual_cached_weights(self):
        inv = P.require_cached_models(self.hub, [self.spec], self.root)
        self.assertTrue(self.hub.snapshot_download.call_args.kwargs["local_files_only"])
        self.assertTrue(inv[0]["localOnly"])
        (self.snap / "model.safetensors").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "بصمة"):
            P.require_cached_models(self.hub, [self.spec], self.root)

    def test_missing_cache_never_retries_online(self):
        self.hub.snapshot_download.side_effect = FileNotFoundError("not cached")
        with self.assertRaisesRegex(ValueError, "لم يُنزّل"):
            P.require_cached_models(self.hub, [self.spec], self.root)
        self.assertEqual(self.hub.snapshot_download.call_count, 1)
        self.assertTrue(self.hub.snapshot_download.call_args.kwargs["local_files_only"])

    def test_partial_cache_and_external_symlink_fail(self):
        file = self.snap / "vocab.json"
        file.unlink()
        with self.assertRaisesRegex(ValueError, "ناقص"):
            P.require_cached_models(self.hub, [self.spec], self.root)
        file.symlink_to("/etc/hosts")
        with self.assertRaises(ValueError):
            P.require_cached_models(self.hub, [self.spec], self.root)

    def test_original_configurers_are_forced_offline_and_pin_checked(self):
        original = self.hub.snapshot_download
        with P.offline_model_loads(self.hub, [self.spec]):
            self.hub.snapshot_download("test/model", revision="pinned", local_files_only=False)
            self.assertTrue(original.call_args.kwargs["local_files_only"])
            with self.assertRaises(ValueError):
                self.hub.snapshot_download("test/model", revision="other")
            self.assertEqual(original.call_count, 1)
        self.assertIs(self.hub.snapshot_download, original)

    def test_main_cache_miss_emits_failure_before_audio_or_model(self):
        contract = P.load_contract()
        with patch.object(P, "ROOT", self.root), patch.object(P, "load_contract", return_value=contract), \
             patch.object(P, "read_candidate", return_value=({}, {})), \
             patch.dict("os.environ", {"CTC_THREADS": "2", "CTC_INT8": "0", "PILOT_CACHE_EXACT_HIT": "true"}), \
             patch.dict("sys.modules", {"huggingface_hub": self.hub}), \
             patch.object(P, "require_cached_models", side_effect=ValueError("missing quran cache")), \
             patch.object(P, "download_source") as download, patch.object(P, "emit_report") as emit:
            self.assertEqual(P.main([]), 1)
        download.assert_not_called()
        report = emit.call_args.args[0]
        self.assertFalse(report["pilotBoundariesVerified"])
        self.assertFalse(report["globalReady"])
        self.assertEqual(report["notVerified"], P.EXPECTED_IDS)
        self.assertIn("missing quran cache", report["errors"][0])


if __name__ == "__main__":
    unittest.main()
