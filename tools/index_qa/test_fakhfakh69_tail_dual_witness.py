import copy
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from tools.index_qa import fakhfakh69_tail_dual_witness as W


class PCM:
    def __init__(self, start=0, end=435638 * 16):
        self.start, self.end = start, end
    def __len__(self):
        return self.end - self.start
    def __getitem__(self, cut):
        return PCM(self.start + cut.start, self.start + cut.stop)


class Backend:
    def __init__(self, starts, contract, weak=None, eof_gap=500):
        self.starts, self.contract, self.weak, self.eof_gap = starts, contract, weak, eof_gap
        self.name = None
    def configure(self, name):
        self.name = name
        _, ident, revision, weights = next(x for x in self.contract.MODELS if x[0] == name)
        return {"id": ident, "revision": revision, "weightsSha256": weights, "license": "Apache-2.0"}
    def reference_text(self, text):
        return text
    def segment(self, pcm, texts):
        shift = 150 if self.name == "quran" else 0
        out = []
        for i, _ in enumerate(texts):
            start = self.starts[i] + shift
            end = (self.starts[i + 1] + shift if i + 1 < len(texts) else 435638 - self.eof_gap)
            score = .59 if f"69:{41+i}" == self.weak and self.name == "quran" else .9
            out.append(((start - 344189) / 1000, (end - 344189) / 1000, score))
        return out
    def conf(self, score):
        return score
    def clear(self):
        pass


class WitnessTest(unittest.TestCase):
    def setUp(self):
        self.contract = W.P.load_contract()
        self.starts = [344500, 352000, 360000, 368000, 376000, 384000,
                       392000, 400000, 408000, 416000, 423000, 428000]
        self.idx = {"riwaya": "qalun", "entries": [
            {"ayahId": f"69:{k}", "startMs": 4000 + (k - 1) * 8500,
             "endMs": 4000 + k * 8500, "fileRef": W.SOURCE_URL}
            for k in range(1, 53)]}
        self.idx["entries"][39]["endMs"] = 344189
        for i, k in enumerate(range(41, 53)):
            self.idx["entries"][k - 1]["startMs"] = 344189 + i * 4000
            self.idx["entries"][k - 1]["endMs"] = 344189 + (i + 1) * 4000
        common = types.SimpleNamespace(
            load_index=lambda: {}, load_text=lambda riw: ["كلمة كلمة كلمة كلمة"] * 52,
            surah_slice=lambda idx, surah: (0, 52, None), norm=lambda text: text)
        spoken = types.SimpleNamespace(alignment_text=lambda s, k, text: text + str(k))
        self.modules = patch.dict("sys.modules", {"common": common, "spoken_letters": spoken})
        self.modules.start(); self.addCleanup(self.modules.stop)

    def test_complete_two_model_range_and_eof_is_accepted(self):
        report = W.measure(copy.deepcopy(self.idx), copy.deepcopy(self.idx["entries"]), PCM(),
                           self.contract, Backend(self.starts, self.contract), {})
        self.assertTrue(report["measurementComplete"])
        self.assertTrue(report["rangeWitnessAccepted"])
        self.assertEqual(report["acceptedAyahs"], W.TARGET_IDS)
        self.assertEqual(report["thresholds"]["targetConf"], .60)
        self.assertEqual(report["perAyah"][-1]["decodedEofGapMs"], {"generic": 500, "quran": 500})

    def test_weak_model_and_large_eof_gap_reject_without_lowering_guards(self):
        for backend, reason in ((Backend(self.starts, self.contract, weak="69:47"), "weak-confidence"),
                                (Backend(self.starts, self.contract, eof_gap=4000), "final-ayah")):
            report = W.measure(copy.deepcopy(self.idx), copy.deepcopy(self.idx["entries"]), PCM(),
                               self.contract, backend, {})
            self.assertTrue(report["measurementComplete"])
            self.assertFalse(report["rangeWitnessAccepted"])
            self.assertTrue(any(reason in r for row in report["perAyah"] for r in row["reasons"]))
        self.assertEqual(self.contract.TARGET_CONF, .60)
        self.assertEqual(self.contract.TAIL_PAD_MS, 3000)

    def test_model_disagreement_rejects(self):
        class Disagree(Backend):
            def segment(self, pcm, texts):
                rows = super().segment(pcm, texts)
                if self.name == "quran":
                    rows[3] = (rows[3][0] + 1.0, rows[3][1] + 1.0, rows[3][2])
                return rows
        report = W.measure(copy.deepcopy(self.idx), copy.deepcopy(self.idx["entries"]), PCM(),
                           self.contract, Disagree(self.starts, self.contract), {})
        self.assertFalse(report["rangeWitnessAccepted"])
        self.assertIn("models-disagree-start", report["perAyah"][3]["reasons"])

    def test_candidate_identity_sha_url_and_order_are_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); path = root / W.CANDIDATE; path.parent.mkdir(parents=True)
            idx = copy.deepcopy(self.idx)
            idx.update(reciterId="fakhfakh_qalun", audioSha256=[W.SOURCE_SHA] * 114)
            raw = gzip.compress(json.dumps(idx).encode()); path.write_bytes(raw)
            digest = hashlib.sha256(raw).hexdigest()
            with patch.object(W, "ROOT", root), patch.object(W, "CANDIDATE_SHA", digest):
                _, rows, _ = W.read_candidate(W.CANDIDATE, digest)
                self.assertEqual(len(rows), 52)
                idx["entries"][0]["fileRef"] = "https://example.org/other.mp3"
                changed = gzip.compress(json.dumps(idx).encode()); path.write_bytes(changed)
                with self.assertRaises(ValueError):
                    W.read_candidate(W.CANDIDATE, hashlib.sha256(changed).hexdigest())


if __name__ == "__main__":
    unittest.main()
