"""Pure final-stage heard tests: fake storage, fake probes, no model or network."""
import base64
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.index_qa import post_stage_heard as P


SHA = "a" * 64
PARENT_SHA = "b" * 64
KEY = f"timings-staging/hafs/peshawa.{SHA[:8]}.jz"
PROVENANCE = {"run_id": "123", "commit": "c" * 40, "ctc_int8": 0, "ctc_threads": 2}


class MemoryClient:
    def __init__(self):
        self.writes = []
        self.body = None
        self.corrupt = False

    def put_object(self, **kwargs):
        self.writes.append(kwargs)
        self.body = kwargs["Body"]

    def get_object(self, **kwargs):
        return {"Body": io.BytesIO(b"{}" if self.corrupt else self.body)}


class PostStageHeardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name)
        self.client = MemoryClient()
        self.cand = {"riwaya": "hafs", "reciterId": "peshawa", "entries": [],
                     "audioSha256": [f"{s:064x}" for s in range(1, 115)]}
        for s in [1, 2, 3, 4, 5, 6, 7, 63]:
            self.cand["entries"].append({"ayahId": f"{s}:1", "startMs": 10000,
                                         "endMs": 20000,
                                         "fileRef": f"https://audio.example/{s:03d}.mp3"})
        self.parent = copy.deepcopy(self.cand)
        self.parent["entries"][-1]["startMs"] = 5000
        self.loads = []
        self.probes = []

    def tearDown(self):
        self.tmp.cleanup()

    def loader(self, key, sha, parent_sha):
        self.loads.append((key, sha, parent_sha))
        return self.client, "bucket", copy.deepcopy(self.cand), copy.deepcopy(self.parent)

    def probe(self, surah, url, riwaya, out):
        self.probes.append(surah)
        return {"surah": surah, "fileRef": url, "riwaya": riwaya,
                "sha256": self.cand["audioSha256"][surah - 1], "engine": "ctc-heardmap-1",
                "entries": [], "totalMs": 25000,
                "heardMap": {"1": {"anchorMs": [10000, 19000], "anchorQuality": .9,
                                   "occurrences": []}}}

    def run_gate(self, **kwargs):
        options = dict(loader=self.loader, probe_fn=self.probe, provenance=PROVENANCE)
        options.update(kwargs)
        return P.run(KEY, SHA, PARENT_SHA, self.out, **options)

    def report(self):
        return json.loads((self.out / "heard-report.json").read_text())

    def extract_payload(self, output, prefix):
        lines = [line for line in output.splitlines() if line.startswith(prefix + "_")]
        begin = dict(item.split("=", 1) for item in lines[0].split()[1:])
        chunks = lines[1:-1]
        self.assertEqual(len(chunks), int(begin["chunks"]))
        for i, line in enumerate(chunks, 1):
            self.assertEqual(line.split()[1], f"{i}/{len(chunks)}")
        payload = base64.b64decode("".join(line.split()[2] for line in chunks))
        self.assertEqual(len(payload), int(begin["bytes"]))
        self.assertEqual(hashlib.sha256(payload).hexdigest(), begin["sha256"])
        self.assertEqual(lines[-1], f"{prefix}_END sha256={begin['sha256']}")
        return json.loads(payload)

    def test_incomplete_measurement_emits_full_report_without_official_write(self):
        def failing(surah, *args):
            if surah == 63:
                raise RuntimeError("تعذر تنزيل السورة كاملة")
            return self.probe(surah, *args)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(self.run_gate(probe_fn=failing), 1)
        report = self.extract_payload(output.getvalue(), "POST_STAGE_HEARD_REPORT")
        self.assertEqual(report, self.report())
        self.assertFalse(report["measurementComplete"])
        self.assertIn("تعذر تنزيل", report["measurementErrors"]["63"])
        self.assertEqual(len(report["maps"]), 4)
        self.assertEqual(self.client.writes, [])

    def test_failed_probe_emits_entire_log_and_preserves_original_error(self):
        def fail(cmd, **kwargs):
            kwargs["stdout"].write("تفصيل فشل النموذج\nسطر أخير\n")
            raise RuntimeError("السبب الأصلي")
        output = io.StringIO()
        with patch.object(P.subprocess, "run", side_effect=fail), contextlib.redirect_stdout(output):
            with self.assertRaisesRegex(RuntimeError, "السبب الأصلي"):
                P.probe(63, "https://audio.example/063.mp3", "hafs", self.out)
        evidence = self.extract_payload(output.getvalue(), "POST_STAGE_HEARD_PROBE_FAILURE")
        self.assertEqual(evidence["log"], "تفصيل فشل النموذج\nسطر أخير\n")
        self.assertFalse(evidence["measurementComplete"])

    def test_large_evidence_failure_is_explicit_and_does_not_mask_measurement(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            P.emit_evidence({"large": "a" * (513 * 1024)}, "POST_STAGE_HEARD_REPORT")
        failure = json.loads(output.getvalue())
        self.assertFalse(failure["logEvidenceComplete"])
        self.assertIn("لم تُطبع نسخة مبتورة", failure["emissionError"])

    def test_exact_sha_sample_all_required_rebound_and_written(self):
        self.assertEqual(self.run_gate(), 0)
        report = self.report()
        expected = P.H.judge(self.cand, self.parent, SHA, {})
        self.assertEqual(self.probes, expected["required"])
        self.assertEqual(len(report["sample"]), 4)
        self.assertEqual(report["modified"], [63])
        self.assertEqual(set(report["maps"]), {str(s) for s in expected["required"]})
        self.assertEqual(self.loads, [(KEY, SHA, PARENT_SHA)] * 2)
        self.assertEqual(self.client.writes[0]["Key"], P.H.state_key(KEY))
        self.assertEqual(json.loads(self.client.body), report)
        self.assertEqual(report["source"], "ci")
        self.assertEqual(report["provenance"], PROVENANCE)
        self.assertIn("rows", report["surahs"]["63"])
        self.assertIsNone(P.H.gate_error(self.cand, self.parent, SHA, report))

    def test_final_sha_changes_sample(self):
        first = P.required_sources(self.cand, self.parent, SHA)
        second = P.required_sources(self.cand, self.parent, "d" * 64)
        self.assertNotEqual([x[0] for x in first], [x[0] for x in second])

    def test_modified_quality_rejection_writes_complete_official_failure(self):
        def bad(*args):
            raw = self.probe(*args)
            if raw["surah"] == 63:
                raw["heardMap"]["1"]["anchorMs"] = [15000, 19000]
            return raw
        self.assertEqual(self.run_gate(probe_fn=bad), 1)
        report = self.report()
        self.assertTrue(report["measurementComplete"])
        self.assertFalse(report["ok"])
        self.assertEqual(len(self.client.writes), 1)
        self.assertIn("بوّابة", report["gateError"])

    def test_sample_quality_findings_remain_nonblocking(self):
        def bad_sample(*args):
            raw = self.probe(*args)
            if raw["surah"] != 63:
                raw["heardMap"]["1"]["anchorMs"] = [15000, 19000]
            return raw
        self.assertEqual(self.run_gate(probe_fn=bad_sample), 0)
        self.assertEqual(len(self.report()["sampleFindings"]), 4)

    def test_missing_sample_is_not_published_even_when_gate_allows_it(self):
        sample = P.H.judge(self.cand, self.parent, SHA, {})["sample"][0]
        def missing(*args):
            if args[0] == sample:
                self.probes.append(sample)
                raise RuntimeError("probe failed")
            return self.probe(*args)
        self.assertEqual(self.run_gate(probe_fn=missing), 1)
        report = self.report()
        self.assertIsNone(report["gateError"])
        self.assertFalse(report["measurementComplete"])
        self.assertIn(str(sample), report["measurementErrors"])
        self.assertEqual(len(self.probes), 5)
        self.assertEqual(self.client.writes, [])

    def test_wrong_audio_url_surah_or_nonprobe_results_are_not_published(self):
        for field, value in (("sha256", "0" * 64), ("fileRef", "https://other/063.mp3"),
                             ("surah", 64), ("entries", [{"startMs": 0}]),
                             ("riwaya", "warsh"), ("engine", "another-engine")):
            with self.subTest(field=field):
                def wrong(*args):
                    raw = self.probe(*args)
                    if args[0] == 63:
                        raw[field] = value
                    return raw
                self.assertEqual(self.run_gate(probe_fn=wrong), 1)
                self.assertEqual(self.client.writes, [])

    def test_post_measurement_binding_failure_never_writes(self):
        def changed(*args):
            if self.loads:
                raise ValueError("published SHA changed")
            return self.loader(*args)
        with self.assertRaisesRegex(ValueError, "published SHA changed"):
            self.run_gate(loader=changed)
        self.assertEqual(self.client.writes, [])
        self.assertIn("published SHA changed", self.report()["bindingError"])

    def test_initial_binding_failure_never_probes_or_writes(self):
        def unbound(*args):
            raise ValueError("wrong candidate SHA")
        with self.assertRaisesRegex(ValueError, "wrong candidate SHA"):
            self.run_gate(loader=unbound)
        self.assertEqual(self.probes, [])
        self.assertEqual(self.client.writes, [])

    def test_readback_must_match_exact_report_bytes(self):
        self.client.corrupt = True
        with self.assertRaisesRegex(ValueError, "read-back"):
            self.run_gate()

    def test_invalid_candidate_sources_fail_before_probing(self):
        for field, value in (("fileRef", "http://audio.example/063.mp3"),
                             ("fileRef", "https://user:secret@audio.example/063.mp3")):
            with self.subTest(value=value):
                self.cand["entries"][-1][field] = value
                with self.assertRaises(ValueError):
                    self.run_gate()
                self.assertEqual(self.probes, [])
        self.cand["entries"][-1]["fileRef"] = "https://audio.example/063.mp3"
        self.cand["audioSha256"][62] = "short"
        with self.assertRaises(ValueError):
            self.run_gate()
        self.assertEqual(self.client.writes, [])

    def test_probe_float32_offline_fresh_directories_and_audio_cleanup(self):
        directories = []
        def fake_run(cmd, **kwargs):
            self.assertEqual(kwargs["env"]["CTC_INT8"], "0")
            self.assertEqual(kwargs["env"]["CTC_THREADS"], "2")
            self.assertEqual(kwargs["env"]["HF_HUB_OFFLINE"], "1")
            self.assertEqual(kwargs["env"]["TRANSFORMERS_OFFLINE"], "1")
            self.assertIn("--probe", cmd)
            work = Path(cmd[cmd.index("--out-dir") + 1])
            directories.append(work)
            (work / "063.mp3").write_bytes(b"audio")
            (work / "063.wav").write_bytes(b"wav")
            (work / "heard_s063.json").write_text('{"surah":63}')
        with patch.object(P.subprocess, "run", side_effect=fake_run):
            for _ in range(2):
                self.assertEqual(P.probe(63, "https://audio.example/063.mp3", "hafs", self.out),
                                 {"surah": 63})
        self.assertNotEqual(*directories)
        self.assertFalse(list(self.out.rglob("*.mp3")))
        self.assertFalse(list(self.out.rglob("*.wav")))

    def test_official_provenance_rejects_non_ci(self):
        with patch.dict(P.os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "GitHub Actions"):
                P.ci_provenance()


if __name__ == "__main__":
    unittest.main()
