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
import tempfile
import contextlib
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
                raise AssertionError("HEAD must be replaced by final LIST")

            def get_paginator(self, kind):
                assert kind == "list_objects_v2"
                return self

            def paginate(self, Bucket, Prefix):
                return [{"Contents": [{"Key": k, "ETag": "changed" if self.changed and k == KEY
                                       else hashlib.sha256(objects[k]).hexdigest()}
                                      for k in objects if k.startswith(Prefix)]}]

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

    def test_final_list_keeps_stable_reads_and_detects_change_delete_new_and_failure(self):
        record, _, _, reports = fixture()
        body = gzip.compress(json.dumps(record["index"]).encode())
        sha = hashlib.sha256(body).hexdigest()
        objects = {KEY: body, "timings/manifest.json": json.dumps({"indexes": []}).encode(),
                   "timings/frozen.txt": f"{KEY}\t{sha}\n".encode(),
                   reports[0][0]: json.dumps(reports[0][1]).encode()}

        class Client:
            def __init__(self, mode):
                self.mode, self.calls = mode, {}

            def get_object(self, Bucket, Key):
                return {"Body": io.BytesIO(objects[Key]), "ETag": hashlib.sha256(objects[Key]).hexdigest()}

            def head_object(self, **kwargs):
                raise AssertionError("HEAD is forbidden in this read path")

            def get_paginator(self, kind):
                return self

            def paginate(self, Bucket, Prefix):
                self.calls[Prefix] = self.calls.get(Prefix, 0) + 1
                final = self.calls[Prefix] == 2
                rows = [{"Key": key, "ETag": hashlib.sha256(value).hexdigest()}
                        for key, value in objects.items() if key.startswith(Prefix)]
                if final and Prefix == "timings/":
                    if self.mode == "change":
                        next(row for row in rows if row["Key"] == KEY)["ETag"] = "changed"
                    elif self.mode == "delete":
                        rows = [row for row in rows if row["Key"] != KEY]
                    elif self.mode == "new":
                        rows.append({"Key": "timings/hafs/new.jz", "ETag": "new"})
                    elif self.mode == "no-etag":
                        del next(row for row in rows if row["Key"] == KEY)["ETag"]
                if final and Prefix == "state-heard/" and self.mode == "new-evidence":
                    rows.append({"Key": "state-heard/new.json", "ETag": "new"})
                if final and Prefix == "state-census/" and self.mode == "failure":
                    raise RuntimeError("LIST unavailable")
                # صفحتان للاختبار؛ لا يفترض الفاحص أن القائمة صفحة واحدة.
                return [{"Contents": rows[:1]}, {"Contents": rows[1:]}]

        for mode, expected in (("stable", None), ("change", f"changedDuringAudit:{KEY}"),
                               ("delete", f"deletedDuringAudit:{KEY}"),
                               ("new", "newObjectDuringAudit:timings/hafs/new.jz"),
                               ("new-evidence", "newObjectDuringAudit:state-heard/new.json"),
                               ("no-etag", f"changedDuringAudit:{KEY}"),
                               ("failure", "stabilityListError:state-census/:RuntimeError")):
            with self.subTest(mode=mode):
                client = Client(mode)
                provider = types.SimpleNamespace(s3=lambda: (client, "test"), PUBLIC="https://public.test",
                                                 STATE_PREFIXES=("state/", "qa-state/"))
                with patch.dict("sys.modules", {"promote": provider}), patch.object(
                        C.urllib.request, "urlopen", side_effect=lambda *a, **kw: io.BytesIO(body)):
                    snapshot, evidence = C.collect_live()
                self.assertIn(KEY, snapshot["indexes"])
                self.assertEqual(len(evidence), 1)
                self.assertFalse(snapshot["stability"]["atomicSnapshot"])
                self.assertEqual(snapshot["stability"]["method"], "get-etag-versus-final-list")
                self.assertTrue(all(count == 2 for count in client.calls.values()))
                if expected:
                    self.assertFalse(snapshot["stableRead"])
                    self.assertIn(expected, snapshot["errors"])
                else:
                    self.assertTrue(snapshot["stableRead"])
                    self.assertEqual(snapshot["errors"], [])

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


class ExistingWindowWitnessIntegrationTest(unittest.TestCase):
    """الحارسان الحقيقيان بلا نموذج: مرجع اصطناعي مستقل وخطة/ثقة/حدود فعلية."""

    def setUp(self):
        self.X = C.load_window_witness()
        self.record, self.manifest, self.frozen, self.reports = fixture()
        self.idx = self.record["index"]
        for entry in self.idx["entries"]:
            if entry["ayahId"].startswith("1:"):
                entry["endMs"] = entry["startMs"] + 5000
        refs = [f"synthetic text {n}" for n in range(7)]
        common = types.SimpleNamespace(load_index=lambda: {}, load_text=lambda riwaya: refs,
                                       surah_slice=lambda index, surah: (0, 7, None), norm=lambda text: text)
        spoken = types.SimpleNamespace(alignment_text=lambda surah, ayah, text: text)
        self.modules = patch.dict("sys.modules", {"common": common, "spoken_letters": spoken})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        aid = "1:3"
        ids, window, texts = self.X.plan(self.idx, aid, 50000)
        tool = pathlib.Path(self.X.__file__).parents[1] / "index_qa/ci_window_census.py"
        self.proof = {"target": aid, "sourceSha256": AUDIO_SHA, "canonicalTextChanged": False,
                      "contextAyahIds": ids, "windowMs": window, "totalMs": 50000,
                      "runtime": dict(self.X.RUNTIME), "models": {},
                      "provenance": {"kind": "audio", "source": "ci", "run_id": "12345",
                                     "tool": "tools/index_qa/ci_window_census.py",
                                     "tool_sha": hashlib.sha256(tool.read_bytes()).hexdigest()}}
        for name, ident, revision, weights in self.X.MODELS:
            entries = []
            for cid in ids:
                e = next(e for e in self.idx["entries"] if e["ayahId"] == cid)
                entries.append({"ayahId": cid, "startMs": e["startMs"], "endMs": e["endMs"], "conf": .8})
            self.proof["models"][name] = {"alignmentModel": {"id": ident, "revision": revision,
                                                                 "weightsSha256": weights, "license": "Apache-2.0"},
                                                  "alignmentInput": list(texts), "entries": entries}
        self.census = {"key": KEY, "kind": "splice-census", "sha256": INDEX_SHA,
                       "census": {"surahs": [1]}, "sample": {"errors": 0, "rows": [
                           {"aid": aid, "kind": "بريء", "verdict": "بريء",
                            "originalTinyRow": {"aid": aid, "kind": "غير حاسم"},
                            "independentWindowCtc": self.proof}]}}
        self.reports.append(("state-census/current.json", self.census))

    def run_audit(self):
        return C.audit_index(KEY, self.record, self.manifest, self.frozen, self.reports)

    def assert_unverified(self):
        result = self.run_audit()
        self.assertEqual(result["verifiedEndEvidence"], 0)
        self.assertEqual(result["unknownEndEvidence"], 6236)
        self.assertFalse(result["ready"])
        return result

    def test_existing_real_guards_accept_end_at_next_start_including_pause(self):
        result = self.run_audit()
        self.assertEqual(result["verifiedEndEvidence"], 1)
        self.assertEqual(result["unknownEndEvidence"], 6235)
        self.assertEqual(result["surahs"][0]["verifiedEndAyahs"], ["1:3"])
        self.assertFalse(result["endEvidence"]["rejected"])
        packed = C.compact_report({"indexes": [result]})["indexes"][0]
        self.assertEqual(packed["surahs"][0]["verifiedEndAyahsRanges"], [[1, 3, 3]])

    def test_wrong_index_sha_is_not_inherited(self):
        self.census["sha256"] = "d" * 64
        self.assert_unverified()

    def test_changed_current_audio_or_wrong_proof_source_is_rejected(self):
        for which in ("current", "proof"):
            with self.subTest(which=which):
                original = self.idx["audioSha256"][0], self.proof["sourceSha256"]
                if which == "current":
                    self.idx["audioSha256"][0] = "d" * 64
                else:
                    self.proof["sourceSha256"] = "d" * 64
                self.assertTrue(self.assert_unverified()["endEvidence"]["rejected"])
                self.idx["audioSha256"][0], self.proof["sourceSha256"] = original

    def test_changed_current_end_is_compared_again(self):
        next(e for e in self.idx["entries"] if e["ayahId"] == "1:3")["endMs"] -= 1200
        self.assertTrue(self.assert_unverified()["endEvidence"]["rejected"])

    def test_missing_model_is_unknown_not_success(self):
        del self.proof["models"]["quran"]
        self.assert_unverified()

    def test_changed_canonical_input_and_flag_are_rejected(self):
        original = self.proof["models"]["generic"]["alignmentInput"][1]
        self.proof["models"]["generic"]["alignmentInput"][1] = "different reference"
        self.assert_unverified()
        self.proof["models"]["generic"]["alignmentInput"][1] = original
        self.proof["canonicalTextChanged"] = True
        self.assert_unverified()

    def test_weak_target_or_context_confidence_is_rejected(self):
        for position, confidence in ((1, .599), (0, .449), (1, math.nan)):
            entry = self.proof["models"]["generic"]["entries"][position]
            entry["conf"] = confidence
            self.assert_unverified()
            entry["conf"] = .8

    def test_models_with_conflicting_ends_are_rejected(self):
        generic = self.proof["models"]["generic"]["entries"]
        quran = self.proof["models"]["quran"]["entries"]
        generic[1]["endMs"] -= 700
        quran[1]["endMs"] += 700
        quran[2]["startMs"] += 700
        self.assertTrue(self.assert_unverified()["endEvidence"]["rejected"])

    def test_untrusted_producer_and_wrong_census_kind_are_rejected(self):
        original = self.proof["provenance"]["tool_sha"]
        self.proof["provenance"]["tool_sha"] = "f" * 64
        self.assert_unverified()
        self.proof["provenance"]["tool_sha"] = original
        self.census["kind"] = "audio"
        self.assert_unverified()

    def test_cannot_cherry_pick_good_proof_over_conflicting_current_report(self):
        conflicting = copy.deepcopy(self.census)
        conflicting["sample"]["rows"][0]["independentWindowCtc"]["models"]["generic"]["entries"][1]["conf"] = .1
        self.reports.append(("state-census/conflicting.json", conflicting))
        self.assert_unverified()

    def test_missing_validator_preserves_unknown_status(self):
        with patch.object(C, "load_window_witness", side_effect=ImportError("missing")):
            result = self.assert_unverified()
        self.assertEqual(result["endEvidence"]["unavailableReason"], "validatorUnavailable:ImportError")


class SavedReportInterfaceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        (self.root / "ops/out").mkdir(parents=True)
        self.root_patch = patch.object(C, "ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.saved = {"version": "completion-audit-2", "ready": False, "summary": {"indexes": 180},
                      "errors": ["readError:example"], "limits": ["unknown is not a confirmed defect"],
                      "indexes": [{"key": KEY, "sha256": INDEX_SHA, "entries": 6236, "ready": False,
                                   "unmeasuredStarts": 7, "unknownEndEvidence": 6235, "verifiedEndEvidence": 1,
                                   "errors": [], "surahs": [{"surah": 1, "unmeasuredRanges": [[1, 1, 7]]}]}]}
        self.source = self.root / "ops/out/existing.json"
        self.source.write_text(json.dumps(self.saved), encoding="utf-8")

    def command(self, *args):
        with patch.object(C.sys, "argv", ["completion_audit.py", *args]), contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            return C.main()

    def assert_cli_error(self, *args):
        with self.assertRaises(SystemExit) as error:
            self.command(*args)
        self.assertEqual(error.exception.code, 2)

    def test_summary_preserves_counts_errors_and_excludes_surah_details(self):
        before = copy.deepcopy(self.saved)
        summary = C.summary_document(self.saved)
        self.assertEqual(summary["summary"], self.saved["summary"])
        self.assertEqual(summary["errors"], self.saved["errors"])
        self.assertEqual(summary["limits"], self.saved["limits"])
        self.assertEqual(summary["indexes"][0]["unknownEndEvidence"], 6235)
        self.assertNotIn("surahs", summary["indexes"][0])
        self.assertEqual(self.saved, before)

    def test_inspect_retains_all_selected_details_without_network_or_overwrite(self):
        original = self.source.read_bytes()
        with patch.object(C, "collect_live", side_effect=AssertionError("must stay offline")):
            self.assertEqual(self.command("--inspect-report", "ops/out/existing.json", "--index-key", KEY), 0)
        outputs = list((self.root / "ops/out").glob("existing-inspect-*.json"))
        self.assertEqual(len(outputs), 1)
        inspected = C.read_json(outputs[0])
        self.assertEqual(inspected["index"], self.saved["indexes"][0])
        self.assertEqual(inspected["sourceErrors"], self.saved["errors"])
        self.assertEqual(self.source.read_bytes(), original)

    def test_missing_report_missing_key_and_required_key_fail_cleanly(self):
        self.assert_cli_error("--inspect-report", "ops/out/missing.json", "--index-key", KEY)
        self.assert_cli_error("--inspect-report", "ops/out/existing.json", "--index-key", "timings/hafs/absent.jz")
        self.assert_cli_error("--inspect-report", "ops/out/existing.json")
        self.assertEqual(list((self.root / "ops/out").glob("*-inspect-*.json")), [])

    def test_inspection_rejects_path_escape_symlinks_and_overwriting_original(self):
        outside = self.root / "outside.json"
        outside.write_bytes(self.source.read_bytes())
        (self.root / "ops/out/link.json").symlink_to(outside)
        for source in ("outside.json", "ops/out/../../outside.json", "ops/out/link.json"):
            self.assert_cli_error("--inspect-report", source, "--index-key", KEY)
        for out in ("outside.json", "ops/out/../../outside.json", "ops/out/link.json", "ops/out/existing.json"):
            self.assert_cli_error("--inspect-report", "ops/out/existing.json", "--index-key", KEY, "--out", out)
        self.assertEqual(C.read_json(self.source), self.saved)

    def test_normal_audit_writes_summary_without_truncating_full_report(self):
        snapshot = self.root / "ops/out/snapshot.json"
        snapshot.write_text(json.dumps({"indexes": {}, "side": {}, "errors": []}), encoding="utf-8")
        self.assertEqual(self.command("--snapshot", "ops/out/snapshot.json", "--out", "ops/out/result.json"), 2)
        full, small = C.read_json(self.root / "ops/out/result.json"), C.read_json(self.root / "ops/out/result-summary.json")
        self.assertEqual(full["summary"], small["summary"])
        self.assertEqual(full["errors"], small["errors"])
        self.assertIn("measurementPolicy", full)
        self.assertNotIn("measurementPolicy", small)
        self.assertTrue((self.root / "ops/out/result.md").is_file())

    def test_automatic_summary_cannot_follow_symlink_outside_or_replace_input(self):
        outside = self.root / "outside.json"
        outside.write_text("preserve", encoding="utf-8")
        (self.root / "ops/out/result-summary.json").symlink_to(outside)
        self.assert_cli_error("--snapshot", "ops/out/existing.json", "--out", "ops/out/result.json")
        self.assertEqual(outside.read_text(), "preserve")
        self.assert_cli_error("--snapshot", "ops/out/existing.json", "--out", "ops/out/existing.json")


if __name__ == "__main__":
    unittest.main()
