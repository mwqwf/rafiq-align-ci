import copy
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

import numpy as np

from tools.index_qa import fakhfakh_openers_dual_witness as W


class Contract:
    TARGET_CONF = .60
    ANCHOR_CONF = .45
    START_TOL = 500
    END_TOL = 800
    DUR_LO = .5
    DUR_HI = 2.0
    OPENER_PAD_MS = 8000
    RUNTIME = {"precision": "float32", "threads": 2}

    def plan(self, idx, aid, total_ms):
        s = int(aid.split(":")[0])
        row = next(e for e in idx["entries"] if e["ayahId"] == aid)
        nxt = next(e for e in idx["entries"] if e["ayahId"] == f"{s}:2")
        return [f"{s}:basmala", aid, f"{s}:2"], [0, nxt["endMs"]], ["ب", "هدف", "تال"]

    def witness_error(self, proof, idx, aid):
        if set(proof["models"]) != {"generic", "quran"}:
            return "missing model"
        if any(len(proof["models"][name].get("entries", [])) != 3
               for name in ("generic", "quran")):
            return "incomplete context"
        return None


class Backend:
    def __init__(self, fail=None):
        self.name = None
        self.fail = fail

    def configure(self, name):
        self.name = name
        return {"id": name, "revision": "r", "weightsSha256": "0" * 64,
                "license": "Apache-2.0"}

    def reference_text(self, text):
        return text

    def segment(self, pcm, texts):
        if self.fail == self.name:
            raise RuntimeError("synthetic failure")
        return [(0, .5, .9), (.5, 1.2, .9), (1.2, 2.0, .9)]

    def conf(self, score):
        return score

    def clear(self):
        pass


class OpenersWitnessTest(unittest.TestCase):
    def setUp(self):
        self.idx = {"reciterId": "fakhfakh_qalun", "riwaya": "qalun",
                    "audioSha256": ["x"] * 114, "entries": []}
        self.sources = {}
        for aid, spec in W.TARGETS.items():
            s = spec["surah"]
            self.idx["entries"].extend([
                {"ayahId": f"{s}:1", "startMs": spec["originalTiny"]["startMs"],
                 "endMs": spec["originalTiny"]["endMs"], "fileRef": spec["url"]},
                {"ayahId": f"{s}:2", "startMs": spec["originalTiny"]["endMs"],
                 "endMs": 40_000, "fileRef": spec["url"]},
            ])
            self.idx["audioSha256"][s - 1] = spec["sha256"]
            self.sources[aid] = {"totalMs": 60_000,
                                 "pcm": np.zeros(60_000 * 16, dtype="<f4")}

    def test_two_models_verify_all_four_without_changing_thresholds(self):
        report = W.measure(copy.deepcopy(self.idx), Contract(), Backend(), self.sources, {})
        self.assertTrue(report["measurementComplete"])
        self.assertTrue(report["allUnknownOpenersResolved"])
        self.assertEqual(report["verifiedOpeners"], list(W.TARGETS))
        self.assertEqual(Contract.TARGET_CONF, .60)
        self.assertEqual(Contract.START_TOL, 500)

    def test_any_model_failure_remains_unresolved(self):
        report = W.measure(copy.deepcopy(self.idx), Contract(), Backend(fail="quran"),
                           self.sources, {})
        self.assertFalse(report["measurementComplete"])
        self.assertFalse(report["allUnknownOpenersResolved"])
        self.assertEqual(report["notVerified"], list(W.TARGETS))

    def test_candidate_identity_source_url_sha_and_order_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / W.CANDIDATE
            path.parent.mkdir(parents=True)
            idx = copy.deepcopy(self.idx)
            # اختبر بسورتين مرجعيتين اصطناعيتين لكل هدف.
            raw = gzip.compress(json.dumps(idx).encode())
            path.write_bytes(raw)
            digest = hashlib.sha256(raw).hexdigest()
            common = types.SimpleNamespace(load_index=lambda: {},
                surah_slice=lambda index, surah: (0, 2, None))
            with patch.object(W, "ROOT", root), patch.object(W, "CANDIDATE_SHA", digest), \
                 patch.dict("sys.modules", {"common": common}):
                _, inventory, _ = W.read_candidate(W.CANDIDATE, digest)
                self.assertEqual(set(inventory), set(W.TARGETS))
                idx["entries"][0]["fileRef"] = "https://example.invalid/other.mp3"
                changed = gzip.compress(json.dumps(idx).encode())
                path.write_bytes(changed)
                changed_digest = hashlib.sha256(changed).hexdigest()
                with patch.object(W, "CANDIDATE_SHA", changed_digest), \
                     self.assertRaisesRegex(ValueError, "source URL mismatch"):
                    W.read_candidate(W.CANDIDATE, changed_digest)

    def test_primary_and_verified_fallback_both_require_exact_sha(self):
        spec = {"url": "https://archive.org/a.mp3", "sha256": hashlib.sha256(b"ok").hexdigest()}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.mp3"
            path.write_bytes(b"ok")
            with patch.object(W.S.metadata, "fetch", return_value={"sha256": spec["sha256"], "bytes": 2}), \
                 patch.object(W, "archive_fetch_verified") as fallback:
                self.assertEqual(W.fetch_source(spec, path)["transport"], "archive-download-primary")
                fallback.assert_not_called()
            path.unlink()
            def verified(url, target):
                Path(target).write_bytes(b"ok")
                return url, 2
            with patch.object(W.S.metadata, "fetch", side_effect=RuntimeError("HTTP 500")), \
                 patch.object(W, "archive_fetch_verified", side_effect=verified):
                self.assertEqual(W.fetch_source(spec, path)["transport"],
                                 "archive-node-publisher-size-md5")

    def test_decode_head_rejects_short_or_error_output(self):
        result = types.SimpleNamespace(returncode=0, stderr=b"", stdout=b"\0" * 16)
        with patch.object(W.subprocess, "run", return_value=result), \
             patch.object(W, "mono_filter", return_value=[]):
            with self.assertRaisesRegex(ValueError, "does not cover"):
                W.decode_head("x.mp3", 1000)
        result = types.SimpleNamespace(returncode=0, stderr=b"decoder warning", stdout=b"\0" * 64000)
        with patch.object(W.subprocess, "run", return_value=result), \
             patch.object(W, "mono_filter", return_value=[]):
            with self.assertRaisesRegex(ValueError, "strict opener decode failed"):
                W.decode_head("x.mp3", 1000)


if __name__ == "__main__":
    unittest.main()
