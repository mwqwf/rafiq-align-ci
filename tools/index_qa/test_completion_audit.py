"""اختبارات منع شهادة اكتمال كاذبة: النقص والذيل والبصمة وأدلة النهاية."""
import copy
import importlib.util
import math
import pathlib
import unittest
import gzip
import hashlib
import io
import json
import types
from unittest.mock import patch

PATH = pathlib.Path(__file__).with_name("completion_audit.py")
SPEC = importlib.util.spec_from_file_location("completion_audit", PATH)
C = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(C)

KEY, INDEX_SHA, AUDIO_SHA = "timings/hafs/test.jz", "a" * 64, "b" * 64


def fixture():
    entries, maps, audio = [], {}, []
    for s, count in enumerate(C.COUNTS, 1):
        url = f"https://publisher.test/{s:03d}.mp3"
        anchors = {}
        for a in range(1, count + 1):
            st = a * 5000
            entries.append({"ayahId": f"{s}:{a}", "startMs": st, "endMs": st + 4000, "fileRef": url})
            anchors[str(a)] = [[st, st + 3500], 0.9, []]
        maps[str(s)] = {"surah": s, "sha256": AUDIO_SHA, "fileRef": url, "anchors": anchors}
        audio.append(AUDIO_SHA)
    idx = {"riwaya": "hafs", "reciterId": "test", "entries": entries, "audioSha256": audio}
    record = {"sha256": INDEX_SHA, "publicSha": INDEX_SHA, "index": idx}
    manifest = {KEY: {"sha256": INDEX_SHA, "entries": len(entries)}}
    report = {"src": "timings-staging/hafs/test.aaaaaaaa.jz", "sha256": INDEX_SHA,
              "ts": 100, "ok": True, "maps": maps, "sampleFindings": [], "version": "heard-gate-1"}
    return record, manifest, {KEY: INDEX_SHA}, [("state-heard/test.json", report)]


class CompletionAuditTest(unittest.TestCase):
    def test_counts_are_complete_quran(self):
        self.assertEqual(len(C.COUNTS), 114)
        self.assertEqual(sum(C.COUNTS), 6236)

    def test_all_starts_do_not_prove_ends(self):
        record, manifest, frozen, reports = fixture()
        result = C.audit_index(KEY, record, manifest, frozen, reports)
        self.assertTrue(result["startsReady"])
        self.assertEqual(result["unmeasuredStarts"], 0)
        self.assertEqual(result["missingEndEvidence"], 6236)
        self.assertFalse(result["ready"])

    def test_one_unmeasured_tail_is_not_complete(self):
        record, manifest, frozen, reports = fixture()
        reports[0][1]["maps"]["114"]["anchors"]["6"][1] = 0.49
        result = C.audit_index(KEY, record, manifest, frozen, reports)
        self.assertFalse(result["startsReady"])
        self.assertEqual(result["surahs"][-1]["unmeasured"], ["114:6"])

    def test_unmeasured_middle_is_not_complete(self):
        record, manifest, frozen, reports = fixture()
        del reports[0][1]["maps"]["2"]["anchors"]["140"]
        result = C.audit_index(KEY, record, manifest, frozen, reports)
        self.assertEqual(result["surahs"][1]["unmeasured"], ["2:140"])
        self.assertFalse(result["startsReady"])

    def test_missing_surah_not_hidden_by_complete_present_rows(self):
        record, manifest, frozen, reports = fixture()
        record["index"]["entries"] = [e for e in record["index"]["entries"] if not e["ayahId"].startswith("114:")]
        record["index"]["audioSha256"].pop()
        manifest[KEY]["entries"] -= 6
        result = C.audit_index(KEY, record, manifest, frozen, reports)
        self.assertEqual(result["missingAyahCount"], 6)
        self.assertFalse(result["startsReady"])

    def test_fixed_114_audio_slots_after_missing_middle_surah(self):
        record, manifest, frozen, reports = fixture()
        record["index"]["entries"] = [e for e in record["index"]["entries"] if not e["ayahId"].startswith("2:")]
        manifest[KEY]["entries"] -= 286
        record["index"]["audioSha256"][2] = "c" * 64
        result = C.audit_index(KEY, record, manifest, frozen, reports)
        self.assertEqual(result["missingAyahCount"], 286)
        self.assertEqual(result["surahs"][2]["evidenceBinding"], "missing")
        self.assertEqual(result["surahs"][3]["evidenceBinding"], "exactIndexSha")
        self.assertEqual(result["unmeasuredStarts"], 200)

    def test_all_surahs_required_despite_sample_findings(self):
        record, manifest, frozen, reports = fixture()
        reports[0][1]["maps"]["100"]["anchors"]["5"][0] = [50000, 54000]
        result = C.audit_index(KEY, record, manifest, frozen, reports)
        self.assertEqual(result["deviations"], 1)
        self.assertFalse(result["startsReady"])

    def test_reuse_same_audio_recomputes_current_start(self):
        record, manifest, frozen, reports = fixture()
        reports[0][1]["sha256"] = "c" * 64
        record["index"]["entries"][0]["startMs"] = 7001
        record["index"]["entries"][0]["endMs"] = 9000
        result = C.audit_index(KEY, record, manifest, frozen, reports)
        self.assertEqual(result["surahs"][0]["evidenceBinding"], "recomputedOnSameAudioSha")
        self.assertEqual(result["deviations"], 1)

    def test_changed_audio_never_inherits_old_proof(self):
        record, manifest, frozen, reports = fixture()
        record["index"]["audioSha256"][0] = "c" * 64
        result = C.audit_index(KEY, record, manifest, frozen, reports)
        self.assertEqual(result["surahs"][0]["evidenceBinding"], "missing")
        self.assertEqual(result["unmeasuredStarts"], 7)

    def test_other_reciter_cannot_supply_proof(self):
        record, manifest, frozen, reports = fixture()
        reports[0][1]["src"] = "timings-staging/hafs/other.aaaaaaaa.jz"
        result = C.audit_index(KEY, record, manifest, frozen, reports)
        self.assertEqual(result["unmeasuredStarts"], 6236)

    def test_invalid_map_surah_and_file_ref_fail_closed(self):
        record, manifest, frozen, reports = fixture()
        reports[0][1]["maps"]["1"]["surah"] = 2
        reports[0][1]["maps"]["2"]["fileRef"] = "https://publisher.test/003.mp3"
        result = C.audit_index(KEY, record, manifest, frozen, reports)
        self.assertEqual(result["unmeasuredStarts"], 7 + 286)

    def test_conflicting_good_and_bad_maps_not_cherry_picked(self):
        record, manifest, frozen, reports = fixture()
        old = copy.deepcopy(reports[0][1])
        old["sha256"], old["ts"] = "c" * 64, 50
        old["maps"]["1"]["anchors"]["1"][0] = [10000, 14000]
        reports.append(("state-heard/old.json", old))
        result = C.audit_index(KEY, record, manifest, frozen, reports)
        self.assertEqual(result["deviations"], 0)
        self.assertTrue(result["surahs"][0]["conflictingEvidence"])
        self.assertFalse(result["startsReady"])

    def test_nan_confidence_cannot_certify(self):
        record, manifest, frozen, reports = fixture()
        reports[0][1]["maps"]["1"]["anchors"]["1"][1] = math.nan
        result = C.audit_index(KEY, record, manifest, frozen, reports)
        self.assertEqual(result["unmeasuredStarts"], 1)

    def test_genuine_repeat_is_recognized(self):
        entry = {"ayahId": "1:1", "startMs": 10000}
        cmap = {"anchors": {"1": [[1000, 5000], 0.9, [[10000, 14000, 0.8]]]}}
        self.assertEqual(C.start_row(entry, cmap)["status"], "repeat")

    def test_manifest_and_public_mismatches_block_starts_readiness(self):
        record, manifest, frozen, reports = fixture()
        record["publicSha"] = "c" * 64
        manifest[KEY]["entries"] -= 1
        result = C.audit_index(KEY, record, manifest, frozen, reports)
        self.assertIn("publicShaMismatchOrMissing", result["errors"])
        self.assertIn("manifestEntryCountMismatch", result["errors"])
        self.assertFalse(result["startsReady"])

    def test_partial_or_unstable_snapshot_cannot_be_ready(self):
        record, manifest, frozen, reports = fixture()
        snap = {"indexes": {KEY: record}, "side": {"timings/manifest.json": {"indexes": [
            dict(manifest[KEY], riwaya="hafs", reciterId="test")]}, "timings/frozen.txt": frozen}}
        result = C.audit(snap, reports)
        self.assertIn("expected180Indexes", result["errors"])
        self.assertIn("liveStabilityNotVerified", result["errors"])
        self.assertFalse(result["ready"])

    def test_export_snapshot_format_supported(self):
        record, manifest, frozen, reports = fixture()
        entries = record["index"].pop("entries")
        files = [f"https://publisher.test/{s:03d}.mp3" for s in range(1, 115)]
        record["header"] = record.pop("index")
        record["files"] = files
        record["rows"] = [[*map(int, e["ayahId"].split(":")), e["startMs"], e["endMs"],
                           int(e["ayahId"].split(":")[0]) - 1] for e in entries]
        result = C.audit_index(KEY, record, manifest, frozen, reports)
        self.assertTrue(result["startsReady"])

    def test_opener_unknown_and_census_uncertainty_are_preserved(self):
        record, manifest, frozen, reports = fixture()
        reports.append(("state/openers.json", {"sha256": INDEX_SHA, "kind": "openers", "checked": 114,
                        "scope": "full", "late": [], "unknown": [1], "_completionToolTrusted": True}))
        reports.append(("state-census/report.json", {"sha256": INDEX_SHA, "census": {"surahs": [1]},
                        "sample": {"rows": [{"aid": "1:1", "kind": "غير حاسم"}]}}))
        result = C.audit_index(KEY, record, manifest, frozen, reports)
        self.assertFalse(result["openers"]["ready"])
        self.assertEqual(result["openers"]["unresolved"], [{"field": "unknown", "surahs": [1]}])
        self.assertEqual(result["census"]["unresolved"][0]["ayahId"], "1:1")

    def test_full_opener_scope_checks_112_basmala_not_114_surahs(self):
        record, manifest, frozen, reports = fixture()
        op = {"sha256": INDEX_SHA, "kind": "openers", "checked": 112, "scope": "full",
              "late": [], "unknown": [], "_completionToolTrusted": True}
        reports.append(("state/openers.json", op))
        result = C.audit_index(KEY, record, manifest, frozen, reports)
        self.assertTrue(result["openers"]["ready"])
        self.assertEqual(result["openers"]["checked"], 112)
        self.assertFalse(result["ready"])  # شهادة المطالع لا تستبدل شاهد النهاية.
        op["scope"] = "partial"
        self.assertFalse(C.audit_index(KEY, record, manifest, frozen, reports)["openers"]["ready"])

    def test_live_collection_is_read_only_and_detects_races(self):
        record, manifest, frozen, reports = fixture()
        body = gzip.compress(json.dumps(record["index"]).encode())
        sha = hashlib.sha256(body).hexdigest()
        objects = {KEY: body,
                   "timings/manifest.json": json.dumps({"indexes": [{"riwaya": "hafs", "reciterId": "test",
                                                                     "entries": 6236, "sha256": sha}]}).encode(),
                   "timings/frozen.txt": f"{KEY}\t{sha}\n".encode(),
                   reports[0][0]: json.dumps(reports[0][1]).encode()}

        class Client:
            changed = False

            def get_object(self, Bucket, Key):
                return {"Body": io.BytesIO(objects[Key]), "ETag": hashlib.sha256(objects[Key]).hexdigest()}

            def head_object(self, Bucket, Key):
                return {"ETag": "changed" if self.changed and Key == KEY else hashlib.sha256(objects[Key]).hexdigest()}

            def get_paginator(self, kind):
                assert kind == "list_objects_v2"
                return self

            def paginate(self, Bucket, Prefix):
                return [{"Contents": [{"Key": k} for k in objects if k.startswith(Prefix)]}]

        client = Client()
        provider = types.SimpleNamespace(s3=lambda: (client, "test-bucket"), PUBLIC="https://public.test",
                                         STATE_PREFIXES=("state/", "qa-state/"))

        def public_read(request, **kwargs):
            self.assertEqual(request.get_header("User-agent"), "Mozilla/5.0 (rafiq-completion-audit/1)")
            self.assertTrue(request.full_url.startswith("https://"))
            self.assertNotIn("context", kwargs)  # TLS الافتراضي، بلا تعطيل التحقق.
            return io.BytesIO(body)

        with patch.dict("sys.modules", {"promote": provider}), patch.object(
                C.urllib.request, "urlopen", side_effect=public_read):
            snapshot, evidence = C.collect_live()
            self.assertTrue(snapshot["stableRead"])
            self.assertEqual(snapshot["indexes"][KEY]["publicSha"], sha)
            self.assertEqual(len(evidence), 1)
            # تقرير قديم ذو مخطط غير صالح لا يستدعي حارساً ولا يضيع الجرد.
            objects["state/old.openers.json"] = json.dumps({"sha256": "f" * 64, "kind": "openers", "openers": 42}).encode()
            old, _ = C.collect_live()
            self.assertTrue(old["stableRead"])
            # JSON فاسد يُعلَن، لكن بيانات الفهارس والأدلة السليمة تبقى.
            objects["state/invalid.openers.json"] = b"{broken"
            broken, evidence = C.collect_live()
            self.assertFalse(broken["stableRead"])
            self.assertIn(KEY, broken["indexes"])
            self.assertEqual(len(evidence), 1)
            self.assertTrue(any("invalid.openers.json" in e for e in broken["errors"]))
            wrong = dict(reports[0][1], kind="openers")
            objects["state-heard/wrong-kind.json"] = json.dumps(wrong).encode()
            wrong_kind, evidence = C.collect_live()
            self.assertEqual(len(evidence), 1)
            self.assertTrue(any("wrong-kind.json" in e for e in wrong_kind["errors"]))
            client.changed = True
            changed, _ = C.collect_live()
            self.assertFalse(changed["stableRead"])
            self.assertIn(f"changedDuringAudit:{KEY}", changed["errors"])

    def test_range_encoding_round_trip_preserves_gaps_duplicates_and_order(self):
        ids = ["1:1", "1:2", "1:2", "1:4", "2:1", "2:2", "1:7"]
        packed = C.ayah_ranges(ids)
        unpacked = [f"{s}:{a}" for s, first, last in packed for a in range(first, last + 1)]
        self.assertEqual(unpacked, ids)

    def test_compact_report_preserves_every_unknown_and_deviation(self):
        record, manifest, frozen, _ = fixture()
        index = C.audit_index(KEY, record, manifest, frozen, [])
        index["surahs"][0]["deviations"] = [{"ayahId": "1:1", "deviationMs": 2000}]
        packed = C.compact_report({"indexes": [index]})["indexes"][0]
        restored = [f"{s}:{a}" for sr in packed["surahs"] for s, first, last in sr["unmeasuredRanges"]
                    for a in range(first, last + 1)]
        self.assertEqual(len(restored), 6236)
        self.assertEqual(sum(sr["unmeasuredCount"] for sr in packed["surahs"]), 6236)
        self.assertEqual(set(restored), {e["ayahId"] for e in record["index"]["entries"]})
        self.assertEqual(packed["surahs"][0]["deviations"], [{"ayahId": "1:1", "deviationMs": 2000}])

    def test_census_compaction_preserves_row_order_and_status(self):
        original = [{"ayahId": "1:1", "kind": "غير حاسم", "verdict": None},
                    {"ayahId": "1:2", "kind": "غير حاسم", "verdict": None},
                    {"ayahId": "1:4", "kind": "جسيم", "verdict": None},
                    {"ayahId": "1:7", "kind": "غير حاسم", "verdict": None},
                    {"ayahId": None, "kind": "غير حاسم", "verdict": "تعذّر"}]
        report = {"indexes": [{"census": {"unresolved": copy.deepcopy(original)}}]}
        result = C.compact_report(report)["indexes"][0]["census"]
        recovered = []
        for group in result["unresolvedGroups"]:
            if "raw" in group:
                recovered.append(group["raw"])
            else:
                recovered.extend(dict(group["status"], ayahId=f"{s}:{a}")
                                 for s, first, last in group["ayahRanges"] for a in range(first, last + 1))
        self.assertEqual(result["unresolvedCount"], len(original))
        self.assertEqual(recovered, original)


if __name__ == "__main__":
    unittest.main()
