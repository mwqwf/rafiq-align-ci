"""اختبارات عقد النشر الرسمي والعرض الجاف دون شبكة أو نموذج صوتي."""
import argparse
import copy
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from tools.index_qa import post_stage_quality as Q
import promote as P

KEY = "timings-staging/hafs/peshawa.aaaaaaaa.jz"
SHA = "a" * 64
PARENT = "b" * 64
IDX = {"riwaya": "hafs", "reciterId": "peshawa", "entries": []}
PROOF = {"run_id": "123", "commit": "c" * 40}


def audio_report(check="rs1"):
    return {"key": KEY, "sha256": SHA, **IDX, "source": "ci", "kind": "audio",
            "sample": {"seedSalt": check, "errors": 0, "rows": []},
            "ts": 200, "verdict": "مقبول", "postStageProvenance": PROOF}


def openers_report():
    return {"key": KEY, "sha256": SHA, **IDX, "kind": "openers", "scope": "full",
            "threads": 4, "commit": P.OPENERS_FIX_COMMIT, "late": [], "errors": [],
            "at": 200, "rows": [{"surah": 63, "verdict": "clean"}],
            "postStageProvenance": PROOF}


class Client:
    def __init__(self):
        self.objects = {}
        self.writes = []
        self.prefixes = []
        self.mtime = 100
        self.corrupt = False

    def get_object(self, *, Bucket, Key):
        body = self.objects[Key]
        return {"Body": io.BytesIO(body + b" " if self.corrupt else body)}

    def put_object(self, **kw):
        self.writes.append(kw)
        self.objects[kw["Key"]] = kw["Body"]
        return {"ETag": "fake"}

    def head_object(self, **kw):
        return {"LastModified": datetime.fromtimestamp(self.mtime, timezone.utc)}

    def get_paginator(self, operation):
        assert operation == "list_objects_v2"
        return self

    def paginate(self, *, Bucket, Prefix):
        self.prefixes.append(Prefix)
        return [{"Contents": [{"Key": k} for k in self.objects if k.startswith(Prefix)]}]


class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.client = Client()
        self.loader = mock.Mock(return_value=(self.client, "bucket", IDX, {}))
        self.pub = Q.Publisher(self.client, "bucket", KEY, SHA, PARENT, "rs1", IDX, PROOF, self.loader)

    def publish(self, report=None, **kw):
        args = {"Bucket": "bucket", "Key": Q.state_key(KEY, "rs1"),
                "Body": json.dumps(report or audio_report()).encode()}
        return self.pub.put_object(**(args | kw))

    def test_exact_official_name_preserves_measurement_and_rebinds_before_write(self):
        report = audio_report()
        self.publish(report)
        self.loader.assert_called_once_with(KEY, SHA, PARENT)
        saved = json.loads(self.client.writes[0]["Body"])
        self.assertEqual(saved, report)
        self.assertEqual(saved["ts"], 200)

    def test_bucket_or_path_cannot_be_used_to_write_production(self):
        for kw in ({"Bucket": "other"}, {"Key": "timings/hafs/peshawa.jz"},
                   {"Key": Q.state_key(KEY, "rs2")}):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                self.publish(**kw)
        self.assertEqual(self.client.writes, [])
        self.loader.assert_not_called()

    def test_identity_full_sha_source_kind_and_salt_must_match(self):
        for patch in ({"key": KEY + "x"}, {"sha256": SHA[:-1] + "b"},
                      {"reciterId": "other"}, {"riwaya": "warsh"},
                      {"source": "local"}, {"kind": "struct"},
                      {"sample": {"seedSalt": "rs2"}}):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                self.publish(audio_report() | patch)
        self.assertFalse(self.client.writes)

    def test_stage_reupload_after_report_never_retimes_or_writes_report(self):
        self.client.mtime = 201
        with self.assertRaisesRegex(ValueError, "وقت الشاهد"):
            self.publish()
        self.assertFalse(self.client.writes)

    def test_future_report_time_is_rejected(self):
        with mock.patch.object(Q.time, "time", return_value=100), self.assertRaises(ValueError):
            self.publish()
        self.assertFalse(self.client.writes)

    def test_changed_candidate_or_parent_prevents_write(self):
        self.loader.side_effect = ValueError("changed parent")
        with self.assertRaisesRegex(ValueError, "changed parent"):
            self.publish()
        self.assertFalse(self.client.writes)

    def test_readback_must_match_written_bytes(self):
        self.client.corrupt = True
        with self.assertRaisesRegex(ValueError, "بايتاته"):
            self.publish()

    def test_rejected_quality_is_written_truthfully(self):
        rep = audio_report() | {"verdict": "مرفوض", "sample": {"seedSalt": "rs1", "errors": 0, "severe": 8}}
        self.publish(rep)
        self.assertEqual(json.loads(self.client.writes[0]["Body"])["verdict"], "مرفوض")

    def test_failed_audio_read_cannot_create_official_quality_report(self):
        rep = audio_report()
        rep['sample']['errors'] = 600
        with self.assertRaisesRegex(ValueError, "القياس الناقص"):
            self.publish(rep)
        self.assertEqual(self.client.writes, [])

    def test_audio_mirror_presigning_allows_get_but_never_write(self):
        self.client.generate_presigned_url = mock.Mock(return_value='https://example.invalid/read')
        params = {'Bucket': 'bucket', 'Key': 'audio/hafs/peshawa/063.mp3'}
        self.assertEqual(self.pub.generate_presigned_url('get_object', Params=params, ExpiresIn=3600),
                         'https://example.invalid/read')
        for method, http in [('put_object', None), ('delete_object', 'DELETE'), ('get_object', 'PUT')]:
            with self.assertRaises(ValueError):
                self.pub.generate_presigned_url(method, Params=params, HttpMethod=http)
        with self.assertRaises(ValueError):
            self.pub.generate_presigned_url('get_object', Params={**params, 'Bucket': 'other'})
        self.assertEqual(self.client.generate_presigned_url.call_count, 1)

    def test_real_audio_mirror_can_obtain_read_url_through_wrapper(self):
        import run as R
        client = mock.Mock()
        client.head_object.return_value = {'ContentLength': 123}
        client.generate_presigned_url.return_value = 'https://example.invalid/read'
        response = mock.MagicMock()
        response.__enter__.return_value.headers = {'Content-Length': '123'}
        with mock.patch.dict(R.MIRROR, {'riwaya': 'hafs', 'reciter': 'peshawa'}), \
                mock.patch.object(R, 's3', return_value=(Q.ReadOnlyClient(client), 'bucket')), \
                mock.patch('urllib.request.urlopen', return_value=response):
            self.assertEqual(R._mirror_url('https://example.invalid/063.mp3'),
                             ('https://example.invalid/read', 'audio/hafs/peshawa/063.mp3', 123))
        client.generate_presigned_url.assert_called_once_with('get_object',
            Params={'Bucket': 'bucket', 'Key': 'audio/hafs/peshawa/063.mp3'},
            ExpiresIn=3600, HttpMethod=None)


class OpenersTests(unittest.TestCase):
    def test_partial_untrusted_wrong_threads_or_error_is_not_a_complete_witness(self):
        for patch in ({"scope": "partial"}, {"commit": "untrusted"}, {"threads": 2},
                      {"errors": [63]}, {"rows": []}):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                Q.validate_report(openers_report() | patch, KEY, SHA, IDX, "openers")

    def test_incomplete_second_witness_cannot_acquit_late_row(self):
        rep = openers_report() | {"late": [63], "rows": [{"surah": 63, "verdict": "late"}],
                                  "lateCtcPrecision": "float32-1thread-avx2 · tail 6000",
                                  "lateCtcRule": "existing", "lateCtc": {"63": {"error": "no audio"}}}
        with self.assertRaises(ValueError):
            Q.validate_report(rep, KEY, SHA, IDX, "openers")
        rep["lateCtc"] = {"63": {"confirmed": False, "conf": 0.8, "diffMs": -100}}
        Q.validate_report(rep, KEY, SHA, IDX, "openers")
        rep["lateCtcPrecision"] = "int8"
        with self.assertRaises(ValueError):
            Q.validate_report(rep, KEY, SHA, IDX, "openers")

    def test_soft_findings_are_left_to_existing_native_gate(self):
        Q.validate_report(openers_report() | {"tail": [5], "suspect": [6], "unknown": [7]},
                          KEY, SHA, IDX, "openers")


class ReviewTests(unittest.TestCase):
    def setUp(self):
        import heard_gate as H
        self.client = Client()
        for check in ["openers", "rs1", "rs2", "rs3", "rs4"]:
            rep = openers_report() if check == "openers" else audio_report(check)
            self.client.objects[Q.state_key(KEY, check)] = json.dumps(rep).encode()
        self.client.objects[H.state_key(KEY)] = json.dumps(
            {"sha256": SHA, "ts": 200, "measurementComplete": True, "provenance": PROOF}).encode()
        self.a = argparse.Namespace(key=KEY, sha=SHA, parent_sha=PARENT, check="review")

    def test_preview_uses_native_guards_readonly_without_unfreezing_and_restores_globals(self):
        target = Q.parent_key(KEY)
        old_s3, old_argv, old_reports = P.s3, sys.argv, P.REPORTS_CACHE
        def actual_preview():
            self.assertEqual(sys.argv, ["promote.py", "--only", KEY])
            client, bucket = P.s3()
            self.assertIsInstance(client, Q.ReadOnlyClient)
            with self.assertRaises(ValueError):
                client.put_object(Bucket=bucket, Key=target, Body=b"bad")
            frozen, _, _ = P.load_frozen(client, bucket)
            self.assertEqual(frozen, {"timings/hafs/other.jz": "d" * 64})
            self.assertEqual(len(P.REPORTS_CACHE), 5)
            print(f"✅ جاهز: {KEY} → {target}")
        frozen = {target: PARENT, "timings/hafs/other.jz": "d" * 64}
        with mock.patch.object(P, "load_frozen", return_value=(frozen, "actual", "etag")), \
                mock.patch.object(P, "main", side_effect=actual_preview), \
                mock.patch.object(Q, "load_bound_candidate") as rebound:
            self.assertEqual(Q.review(self.a, self.client, "bucket", IDX, PROOF), 0)
            rebound.assert_called_once_with(KEY, SHA, PARENT)
        self.assertIs(P.s3, old_s3)
        self.assertIs(sys.argv, old_argv)
        self.assertIs(P.REPORTS_CACHE, old_reports)
        self.assertEqual(frozen[target], PARENT)
        self.assertFalse(self.client.writes)

    def test_older_run_witness_is_not_substituted_for_missing_current_measurement(self):
        key = Q.state_key(KEY, "rs4")
        rep = json.loads(self.client.objects[key])
        rep["postStageProvenance"]["run_id"] = "122"
        self.client.objects[key] = json.dumps(rep).encode()
        with mock.patch.object(P, "main") as native, self.assertRaisesRegex(ValueError, "دورة الفحص"):
            Q.review(self.a, self.client, "bucket", IDX, PROOF)
        native.assert_not_called()

    def test_nonready_native_preview_fails_and_cannot_write(self):
        with mock.patch.object(P, "main", side_effect=lambda: print("رفض أصلي")), self.assertRaises(ValueError):
            Q.review(self.a, self.client, "bucket", IDX, PROOF)
        self.assertFalse(self.client.writes)

    def test_read_reports_keeps_rejections_and_obeys_native_prefixes(self):
        self.client.objects["extra/" + KEY.replace("/", "_") + ".json"] = json.dumps(
            audio_report() | {"verdict": "مرفوض"}).encode()
        with mock.patch.object(P, "STATE_PREFIXES", ("extra/",)):
            records = Q.read_reports(self.client, "bucket", KEY)
        self.assertEqual(records[0][1]["verdict"], "مرفوض")
        self.assertEqual(len(records), 1)

    def test_report_read_error_cannot_silently_remove_a_veto(self):
        self.client.objects[Q.state_key(KEY, "rs1")] = b"not json"
        with self.assertRaises(json.JSONDecodeError):
            Q.read_reports(self.client, "bucket", KEY)

    def test_same_byte_stage_reupload_invalidates_every_old_witness(self):
        self.client.mtime = 201
        with mock.patch.object(P, "main") as native, self.assertRaisesRegex(ValueError, "وقت الشاهد"):
            Q.review(self.a, self.client, "bucket", IDX, PROOF)
        native.assert_not_called()

    def test_readonly_denies_mutating_methods_and_paginators(self):
        readonly = Q.ReadOnlyClient(self.client)
        for method in ("put_object", "copy_object", "delete_object", "upload_file", "create_multipart_upload"):
            with self.subTest(method=method), self.assertRaises(ValueError):
                getattr(readonly, method)
        with self.assertRaises(ValueError):
            readonly.get_paginator("delete_objects")


class ExistingAudioToolTests(unittest.TestCase):
    def test_native_cli_gets_real_salt_and_sha_and_preserves_rejection(self):
        import ci_run as C
        import run as R
        client = Client()
        rep = audio_report("rs3") | {"verdict": "مرفوض", "engine": "actual", "elapsedSec": 0}
        a = argparse.Namespace(key=KEY, sha=SHA, parent_sha=PARENT, check="rs3")
        def native_audit(key, args):
            self.assertEqual(key, KEY)
            self.assertEqual(args.expect_sha, SHA)
            self.assertEqual((args.clusters, args.per_cluster, args.threads), (20, 10, 1))
            self.assertEqual(os.environ["QA_SEED_SALT"], "rs3")
            self.assertEqual(os.environ["QA_SOURCE"], "ci")
            return copy.deepcopy(rep)
        with tempfile.TemporaryDirectory() as work:
            model = Path(work) / "model.bin"
            model.write_bytes(b"x" * 1_000_000)
            (Path(work) / "text_hafs.jz").write_bytes(b"fixture")
            with mock.patch.dict(os.environ, {"QA_MODEL": str(model)}, clear=False), \
                    mock.patch.object(R, "ASSETS", Path(work)), mock.patch.object(R, "audit", side_effect=native_audit), \
                    mock.patch.object(R, "show"), mock.patch.object(Q, "load_bound_candidate", return_value=(client, "bucket", IDX, {})):
                self.assertEqual(Q.audio_check(a, client, "bucket", IDX, PROOF), 1)
        self.assertEqual(client.writes[0]["Key"], Q.state_key(KEY, "rs3"))
        self.assertEqual(json.loads(client.writes[0]["Body"])["verdict"], "مرفوض")

    def test_model_digest_is_required_even_for_plausible_size(self):
        with tempfile.TemporaryDirectory() as work:
            model = Path(work) / "model.bin"
            model.write_bytes(b"x" * 1_000_000)
            with self.assertRaisesRegex(ValueError, "بصمة"):
                Q.verify_model(model)


if __name__ == "__main__":
    unittest.main()
