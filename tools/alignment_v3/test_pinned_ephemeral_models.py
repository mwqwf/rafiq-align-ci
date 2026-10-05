"""حدود التنزيل المؤقت وتثبيت البصمة بلا أي اتصال أو أوزان فعلية."""
import hashlib
import io
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import Mock, patch
import urllib.error

from tools.alignment_v3 import pinned_ephemeral_models as E


class Response(io.BytesIO):
    def __init__(self, data, url, length=None):
        super().__init__(data)
        self.url = url
        self.headers = {"Content-Length": str(len(data) if length is None else length)}

    def geturl(self):
        return self.url

    def getcode(self):
        return 200


class EphemeralTest(unittest.TestCase):
    def test_partial_http_response_rejected_before_use(self):
        with tempfile.TemporaryDirectory() as directory:
            url = "https://huggingface.co/model/resolve/pinned/file.json"
            for code, headers in ((206, {}), (200, {"Content-Range": "bytes 0-1/8"})):
                response = Response(b"{}", url)
                response.headers.update(headers)
                response.getcode = lambda: code
                opener = types.SimpleNamespace(open=lambda *a, **k: response)
                with self.assertRaisesRegex(ValueError, "HTTP200"):
                    E.download_file(opener, url, Path(directory)/"file.json", limit=100, started=0)
                self.assertEqual(list(Path(directory).iterdir()), [])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.parent = Path(self.tmp.name)
        self.weight = b"synthetic pinned weights"
        self.digest = hashlib.sha256(self.weight).hexdigest()
        self.sha_patch = patch.object(E, "WEIGHTS_SHA256", self.digest)
        self.sha_patch.start(); self.addCleanup(self.sha_patch.stop)
        self.requests = []

    def opener(self, request, timeout):
        self.requests.append(request)
        self.assertEqual(timeout, 60)
        data = self.weight if request.full_url.endswith(E.WEIGHT_FILE) else b"{}"
        return Response(data, request.full_url)

    def run_context(self, **kwargs):
        return E.quran_ephemeral_download(parent=self.parent,
                   opener=types.SimpleNamespace(open=self.opener), **kwargs)

    def test_explicit_download_pins_urls_sha_and_cleans_after_context(self):
        with self.run_context(allow_download=True) as ev:
            snapshot = Path(ev["snapshot"])
            self.assertTrue((snapshot / E.WEIGHT_FILE).is_file())
            self.assertTrue(all(f"/resolve/{E.REVISION}/" in r.full_url for r in self.requests))
            self.assertTrue(all(r.get_header("Authorization") is None for r in self.requests))
            self.assertEqual(ev["weightsSha256"], self.digest)
            self.assertEqual(ev["totalBytes"], len(self.weight) + 2 * (len(E.FILES) - 1))
            self.assertFalse(ev["cacheWrite"])
        self.assertFalse(snapshot.exists())
        self.assertEqual(list(self.parent.iterdir()), [])

    def test_no_opt_in_means_no_files_or_network(self):
        with self.assertRaisesRegex(ValueError, "صراحة"):
            with self.run_context():
                self.fail("unexpected download")
        self.assertEqual(self.requests, [])
        self.assertEqual(list(self.parent.iterdir()), [])

    def test_wrong_weight_sha_cleans_all_and_does_not_yield(self):
        with patch.object(E, "WEIGHTS_SHA256", "f" * 64), self.assertRaisesRegex(ValueError, "بصمة"):
            with self.run_context(allow_download=True):
                self.fail("unverified weight escaped")
        self.assertEqual(list(self.parent.iterdir()), [])

    def test_cache_directory_and_insufficient_disk_rejected_before_network(self):
        with patch.dict("os.environ", {"HF_HOME": str(self.parent)}), self.assertRaisesRegex(ValueError, "cache"):
            with self.run_context(allow_download=True): pass
        with patch.object(E.shutil, "disk_usage", return_value=types.SimpleNamespace(free=0)), self.assertRaisesRegex(ValueError, "المساحة"):
            with self.run_context(allow_download=True): pass
        self.assertEqual(self.requests, [])

    def test_redirect_cannot_downgrade_or_escape_public_model_hosts(self):
        for url in ("http://huggingface.co/x", "https://huggingface.co.evil.example/x",
                    "https://user:password@huggingface.co/x", "https://127.0.0.1/x"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                E.checked_public_url(url)
        self.assertTrue(E.checked_public_url("https://cas-bridge.xethub.hf.co/x?signed=public"))

    def test_stream_limit_truncation_deadline_and_cleanup(self):
        url = "https://huggingface.co/model/resolve/pinned/file.json"
        cases = [(b"abcdef", 6, 3, [0, 0]), (b"abc", 6, 9, [0, 0]), (b"abc", 3, 9, [601])]
        for data, length, limit, clock in cases:
            with self.subTest(data=data, length=length, limit=limit, clock=clock):
                target = self.parent / "test.json"
                opener = types.SimpleNamespace(open=lambda *a, **k: Response(data, url, length))
                with self.assertRaises((ValueError, TimeoutError)):
                    E.download_file(opener, url, target, limit=limit, started=0,
                                    clock=Mock(side_effect=clock + [601] * 10))
                self.assertFalse(target.exists())
                self.assertEqual(list(self.parent.iterdir()), [])

    def test_optional_404_is_recorded_but_required_404_fails(self):
        orig = self.opener
        def optional(req, timeout):
            if req.full_url.endswith("tokenizer.json"):
                raise urllib.error.HTTPError(req.full_url, 404, "missing", {}, None)
            return orig(req, timeout)
        with E.quran_ephemeral_download(allow_download=True, parent=self.parent,
                                        opener=types.SimpleNamespace(open=optional)) as ev:
            self.assertIn({"filename": "tokenizer.json", "optionalAbsent": True}, ev["files"])
        def required(req, timeout):
            raise urllib.error.HTTPError(req.full_url, 404, "missing", {}, None)
        with self.assertRaises(urllib.error.HTTPError):
            with E.quran_ephemeral_download(allow_download=True, parent=self.parent,
                                            opener=types.SimpleNamespace(open=required)): pass
        self.assertEqual(list(self.parent.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
