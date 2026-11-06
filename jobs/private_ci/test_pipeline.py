#!/usr/bin/env python3
"""🧪 اختباراتُ الخطّة (plan.py) والرافع (upload_r2.py) والحالة (status_back.py) وحارس النطاق بأمثلةٍ مزروعة."""
import datetime
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import plan  # noqa: E402
import status_back  # noqa: E402
import upload_r2  # noqa: E402
import test_env_scope as scope  # noqa: E402

SHA = "a" * 40
KINDS = plan.load_kinds()


class PlanTest(unittest.TestCase):
    def ok(self, **kw):
        args = dict(event="repository_dispatch", payload_json=json.dumps({"sha": SHA, "kind": "app-test"}),
                    dry_run="", plant="false", head_sha="b" * 40, kinds=KINDS)
        args.update(kw)
        return plan.decide(**args)

    def test_valid_dispatch(self):
        out = self.ok()
        self.assertEqual((out["kind"], out["sha"], out["source"], out["context"]), ("app-test", SHA, "private", "ci/app-test"))

    def test_multi_leg(self):
        out = self.ok(payload_json=json.dumps({"sha": SHA, "kind": "device-matrix"}))
        self.assertEqual(out["multi"], "true")
        self.assertEqual(len(json.loads(out["legs"])), 6)

    def test_rejects_extra_keys_bad_sha_bad_kind(self):
        bad = [
            {"sha": SHA, "kind": "app-test", "ref": "main"},          # ⛔ (هـ) مفتاحٌ ثالث
            {"sha": SHA},
            {"sha": SHA.upper(), "kind": "app-test"},
            {"sha": SHA[:39], "kind": "app-test"},
            {"sha": SHA + "; rm -rf /", "kind": "app-test"},
            {"sha": SHA, "kind": "recite-switch-emu"},                 # ⛔ لا يُنقل (‏يقرأ أسراراً)
            {"sha": SHA, "kind": "dry-run"},                           # التجربةُ يدويّةٌ فقط
            {"sha": SHA, "kind": "$(id)"},
            ["not", "a", "dict"],
        ]
        for p in bad:
            with self.subTest(p=p):
                with self.assertRaises(ValueError):
                    self.ok(payload_json=json.dumps(p))
        with self.assertRaises(ValueError):
            self.ok(payload_json="{not json")

    def test_rejection_message_does_not_echo_input(self):
        try:
            self.ok(payload_json=json.dumps({"sha": "deadbeef-SECRET", "kind": "x"}))
        except ValueError as e:
            self.assertNotIn("SECRET", str(e))

    def test_workflow_dispatch_only_dry_run(self):
        with self.assertRaises(ValueError):
            self.ok(event="workflow_dispatch", dry_run="false")
        out = self.ok(event="workflow_dispatch", dry_run="true", plant="true")
        self.assertEqual((out["kind"], out["source"], out["plant"]), ("dry-run", "public", "true"))
        self.assertEqual(out["sha"], "b" * 40)

    def test_plant_ignored_on_dispatch(self):
        self.assertEqual(self.ok(plant="true")["plant"], "false")

    def test_other_events_refused(self):
        for ev in ("pull_request", "pull_request_target", "push", "issue_comment", "workflow_run"):
            with self.subTest(ev=ev), self.assertRaises(ValueError):
                self.ok(event=ev)

    def test_all_kinds_known_and_timeouts_bounded(self):
        moved = {"app-test", "engine-test", "engine-models", "tasmi-model-emulator-smoke", "ui-shots-emu",
                 "hudhud-feature-test", "ads-emulator-smoke", "device-matrix", "dry-run"}
        self.assertEqual(set(KINDS), moved)
        for k, spec in KINDS.items():
            for leg in spec["legs"]:
                self.assertLessEqual(leg["timeout"], 120, k)


class SigV4Test(unittest.TestCase):
    def test_aws_documented_presign_vector(self):
        """مثالُ AWS الموثَّق للرابط الموقَّع (S3 · examplebucket/test.txt · 2013-05-24 · 86400 ث)."""
        url = upload_r2.presign_get(
            "examplebucket.s3.amazonaws.com", "/test.txt", "AKIAIOSFODNN7EXAMPLE",
            "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            datetime.datetime(2013, 5, 24, 0, 0, 0, tzinfo=datetime.timezone.utc), 86400,
            region="us-east-1")
        self.assertTrue(url.endswith("X-Amz-Signature=aeeed9bbccd4d02ee5c0109b86d86835f995330da4c265957d157751f604d404"), url)

    def test_signed_put_shape(self):
        now = datetime.datetime(2026, 11, 6, tzinfo=datetime.timezone.utc)
        url, h = upload_r2.signed_request("PUT", "acc.r2.cloudflarestorage.com", "/mushafak-private/ci/x y.txt",
                                          "K", "S", now, b"hi", "text/plain")
        self.assertEqual(url, "https://acc.r2.cloudflarestorage.com/mushafak-private/ci/x%20y.txt")
        self.assertTrue(h["authorization"].startswith("AWS4-HMAC-SHA256 Credential=K/20261106/auto/s3/aws4_request"))
        self.assertIn("SignedHeaders=content-type;host;x-amz-content-sha256;x-amz-date", h["authorization"])


class UploadPolicyTest(unittest.TestCase):
    def test_private_mode_bucket_allowlist(self):
        upload_r2.check_bucket("private", "mushafak-private")
        for b in ("rafiq-media", "anything-else", ""):
            with self.subTest(b=b), self.assertRaises(ValueError):
                upload_r2.check_bucket("private", b)

    def test_dryrun_never_writes_private_bucket(self):
        with self.assertRaises(ValueError):
            upload_r2.check_bucket("dryrun", "mushafak-private")

    def test_creds_must_be_r2(self):
        os.environ["T_CREDS"] = json.dumps({"endpoint": "https://evil.example.com", "accessKeyId": "a",
                                            "secretAccessKey": "b", "bucket": "mushafak-private"})
        try:
            with self.assertRaises(ValueError):
                upload_r2.load_creds("T_CREDS")
        finally:
            del os.environ["T_CREDS"]

    def test_public_bucket_detected_and_objects_deleted(self):
        """إن ردّ النطاقُ العامّ 200 على ما رُفع في الوضع الخاص ⇒ حذفٌ وخروجٌ برمز 4 ولا رابطٌ موقَّع."""
        calls = []

        class R:
            def __init__(self, status): self.status = status
            def __enter__(self): return self
            def __exit__(self, *a): return False

        def fake_open(req, timeout=0):
            calls.append((req.get_method(), req.full_url.split("?")[0]))
            return R(200)

        orig = (upload_r2.put_object, upload_r2.delete_object, upload_r2.public_probe)
        upload_r2.put_object = lambda c, k, b, ct: fake_open(type("Q", (), {"get_method": lambda s: "PUT", "full_url": k})())
        upload_r2.delete_object = lambda c, k: calls.append(("DELETE", k))
        upload_r2.public_probe = lambda k: 200
        os.environ["T_CREDS"] = json.dumps({"endpoint": "https://" + "0" * 32 + ".r2.cloudflarestorage.com",
                                            "accessKeyId": "a", "secretAccessKey": "b", "bucket": "mushafak-private"})
        try:
            with tempfile.TemporaryDirectory() as d:
                out, st = os.path.join(d, "out"), os.path.join(d, "st")
                os.makedirs(out); os.makedirs(st)
                open(os.path.join(out, "log.txt"), "w").write("x\n")
                rc = upload_r2.main(["--mode", "private", "--creds-env", "T_CREDS", "--out", out, "--state", st,
                                     "--sha", SHA, "--run-id", "1", "--leg", "main"])
                self.assertEqual(rc, upload_r2.EXIT_PUBLIC_BUCKET)
                self.assertTrue(any(c[0] == "DELETE" for c in calls))
                self.assertFalse(os.path.exists(os.path.join(st, "link.txt")))
        finally:
            upload_r2.put_object, upload_r2.delete_object, upload_r2.public_probe = orig
            del os.environ["T_CREDS"]


class StatusTest(unittest.TestCase):
    RUN = "https://github.com/mwqwf/rafiq-align-ci/actions/runs/42"

    def test_no_success_without_tests(self):
        self.assertEqual(status_back.state_from("success", {"tests": 0}), "failure")
        self.assertEqual(status_back.state_from("success", {"tests": 3}), "success")
        self.assertEqual(status_back.state_from("cancelled", None), "error")

    def test_context_and_link_allowlists(self):
        p = status_back.build_payload("success", "ci/app-test", self.RUN, {"tests": 5, "failures": 0, "errors": 0})
        self.assertEqual(p["target_url"], self.RUN)
        self.assertLessEqual(len(p["description"]), 140)
        signed = "https://" + "0" * 32 + ".r2.cloudflarestorage.com/mushafak-private/ci/private-ci/x/log.txt.gz?X-Amz-Signature=1"
        self.assertEqual(status_back.build_payload("failure", "public-ci/device-matrix/a24-small-x86", self.RUN,
                                                   None, signed)["target_url"], signed)
        for ctx in ("continuous-integration/x", "ci/app-test; drop", "public-ci/" + "x" * 80, ""):
            with self.subTest(ctx=ctx), self.assertRaises(ValueError):
                status_back.build_payload("success", ctx, self.RUN, None)
        # رابطٌ غريب لا يمرّ — يُستبدل برابط التشغيلة إن كان موقَّعاً غيرَ معروف، ويُرفض إن كان هو الهدف
        self.assertEqual(status_back.build_payload("success", "ci/app-test", self.RUN, None,
                                                   "https://evil.example.com/?X-Amz-Signature=1")["target_url"], self.RUN)
        with self.assertRaises(ValueError):
            status_back.build_payload("success", "ci/app-test", "https://evil.example.com/", None)

    def test_dry_run_sends_nothing(self):
        sent = []
        orig = status_back.send
        status_back.send = lambda *a, **k: sent.append(a) or 201
        try:
            rc = status_back.main(["--dry-run", "--sha", SHA, "--context", "public-ci/dry-run", "--result", "success",
                                   "--run-url", self.RUN])
        finally:
            status_back.send = orig
        self.assertEqual(rc, 0)
        self.assertEqual(sent, [])


@unittest.skipIf(scope.yaml is None, "PyYAML غيرُ مثبّت")
class ScopeNegativeTest(unittest.TestCase):
    """حارسُ النطاق يُمسك المخالفاتِ المزروعة — لا يكفي أن يمرّ على الشجرة النظيفة."""

    def base(self):
        files = scope.workflows()
        if not files:
            self.skipTest("لا مجلّدَ سيور")
        return dict(files)

    def test_other_workflow_using_env_or_secret(self):
        files = self.base()
        files["evil.yml"] = "on: push\njobs:\n  x:\n    runs-on: ubuntu-latest\n    environment: Private-CI\n    steps: []\n"
        files["evil2.yml"] = ("on: push\njobs:\n  x:\n    runs-on: ubuntu-latest\n    environment:\n      name: private-ci\n"
                              "    steps: []\n")
        files["evil3.yml"] = "on: push\njobs:\n  x:\n    runs-on: ubuntu-latest\n    environment: ${{ github.event.inputs.e }}\n    steps: []\n"
        files["evil4.yml"] = "on: push\njobs:\n  x:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo ${{ secrets.PCI_STATUS_TOKEN }}\n"
        files["evil5.yml"] = "on: push\njobs:\n  x:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo ${{ secrets.QR_READ_DEPLOY_KEY_B64 }}\n"
        v = scope.find_violations(files)
        for name in ("evil.yml", "evil2.yml", "evil3.yml", "evil4.yml", "evil5.yml"):
            self.assertTrue(any(x.startswith(name) for x in v), f"{name} لم يُمسك")

    def test_weakened_private_ci_is_caught(self):
        files = self.base()
        good = files["private-ci.yml"]
        mutations = {
            "pull_request": good.replace("  workflow_dispatch:\n", "  pull_request:\n  workflow_dispatch:\n", 1),
            "cache": good.replace("      - name: الاستنساخ الجزئي\n",
                                  "      - uses: actions/cache@0400d5f644dc74513175e3cd8d07132dd4860809\n        with: {path: x, key: y}\n      - name: الاستنساخ الجزئي\n", 1),
            "unpinned": good.replace("actions/setup-java@cf277c60eb25467037889841efdb72551f06f6c3", "actions/setup-java@v4", 1),
            "perms": good.replace("permissions:\n  contents: read\n", "permissions:\n  contents: write\n", 1),
            "setx": good.replace("run: bash jobs/private_ci/run.sh build", "run: |\n          set -x\n          bash jobs/private_ci/run.sh build", 1),
            "secret-in-build": good.replace("      - name: البناء والاختبار (المخرجات إلى ملف)\n",
                                            "      - name: البناء والاختبار (المخرجات إلى ملف)\n        env:\n          K: ${{ secrets.PCI_DEPLOY_KEY_B64 }}\n", 1),
            "persist": good.replace("persist-credentials: false", "persist-credentials: true", 1),
            "cat-log": good.replace("run: bash jobs/private_ci/run.sh build", "run: cat $RUNNER_TEMP/private_ci/out/log.txt", 1),
        }
        for label, text in mutations.items():
            with self.subTest(m=label):
                self.assertNotEqual(text, good, f"الطفرة {label} لم تُطبَّق")
                f2 = dict(files); f2["private-ci.yml"] = text
                self.assertTrue(scope.find_violations(f2), f"الطفرة {label} مرّت")

    def test_extra_sh_in_jobs_dir(self):
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, "run.sh"), "w").write("echo\n")
            open(os.path.join(d, "x.sh"), "w").write("echo\n")
            v = scope.jobs_dir_violations(d)
            self.assertTrue(any("x.sh" in s for s in v))
            self.assertTrue(any("شرطُ الاستدعاء" in s for s in v))


if __name__ == "__main__":
    unittest.main()
