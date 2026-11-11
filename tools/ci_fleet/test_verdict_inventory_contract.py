"""جرد الأحكام والكاش: اختبارات محلية بلا اعتماد أو اتصال بالدلو."""
from collections import Counter
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

from tools.index_qa import promote
from tools.index_qa import verdict_cache as cache
from tools.index_qa import verdict_inventory as subject


class FakeClient:
    def __init__(self, objects=(), bodies=None, *, pages=None, list_error=False,
                 response_etags=None):
        self.pages = pages if pages is not None else [{"Contents": list(objects)}]
        self.bodies = bodies or {}
        self.list_error = list_error
        self.response_etags = {
            entry["Key"]: entry.get("ETag")
            for page in self.pages for entry in page.get("Contents", []) if "Key" in entry
        }
        if response_etags is not None:
            self.response_etags.update(response_etags)
        self.list_calls = []
        self.get_calls = []
        self.streams = []
        self.lock = threading.Lock()

    def get_paginator(self, name):
        assert name == "list_objects_v2"
        return self

    def paginate(self, **kwargs):
        self.list_calls.append(kwargs)
        yield from self.pages
        if self.list_error:
            raise OSError("فشل السرد")

    def get_object(self, *, Bucket, Key):
        with self.lock:
            self.get_calls.append(Key)
        data = self.bodies[Key]
        if isinstance(data, Exception):
            raise data
        if hasattr(data, "read"):
            stream = data
        else:
            stream = io.BytesIO(data if isinstance(data, bytes) else json.dumps(data).encode())
        self.streams.append(stream)
        response = {"Body": stream}
        if self.response_etags.get(Key) is not None:
            response["ETag"] = self.response_etags[Key]
        return response


def obj(key, etag='"v1"'):
    return {"Key": key, "ETag": etag}


def cache_path(directory, key, etag):
    return directory / (hashlib.sha256(f"{key}|{etag}".encode()).hexdigest() + ".json")


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def test_existing_key_etag_filename_and_json_remain_compatible(self):
        value = [{"key": "timings/a", "verdict": "مقبول"}, {"key": "timings/b"}]
        cache.store(self.directory, "state/a.json", "e", value)
        expected = cache_path(self.directory, "state/a.json", "e")
        self.assertEqual(json.loads(expected.read_text()), value)
        self.assertEqual(cache.cached(self.directory, "state/a.json", "e"), value)
        self.assertIsNone(cache.cached(self.directory, "state/a.json", "other"))
        self.assertIsNone(cache.cached(self.directory, "state/b.json", "e"))

    def test_missing_corrupt_and_unreadable_cache_are_misses(self):
        self.assertIsNone(cache.cached(self.directory, "k", "e"))
        cache_path(self.directory, "k", "e").write_text("{")
        self.assertIsNone(cache.cached(self.directory, "k", "e"))
        with patch.object(Path, "read_text", side_effect=OSError("قراءة")):
            self.assertIsNone(cache.cached(self.directory, "k", "e"))

    def test_write_failure_remains_best_effort(self):
        with patch.object(Path, "write_text", side_effect=OSError("كتابة")):
            cache.store(self.directory, "k", "e", {})


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def run_inventory(self, client):
        return subject.inventory(client, "bucket", self.directory)

    def test_classification_matches_original_priority_and_prefix(self):
        cases = [
            ({"verdict": "مقبول"}, None),
            ({"verdict": "مقبول بنيوياً بلا عينة"}, None),
            ({"verdict": "مقبول-أي شيء جسيم"}, None),
            ({"verdict": "بنيوي جسيم حدّي موقوف"}, "خلل بنيوي"),
            ({"verdict": "جسيم حدّي موقوف"}, "عطبٌ جسيم"),
            ({"verdict": "حدّي موقوف"}, "حدّي"),
            ({"verdict": "موقوف"}, "موقوف"),
            ({"verdict": "غير مقبول"}, "آخر"),
            ({"verdict": " مقبول"}, "آخر"),
            ({"verdict": 123}, "آخر"), ({"verdict": None}, "آخر"),
            ({}, "آخر"),
        ]
        for report, expected in cases:
            with self.subTest(report=report):
                self.assertEqual(subject.classify(report), expected)

    def test_exact_prefix_all_extensions_per_object_and_no_report_key_required(self):
        bodies = {
            "state-ci/a.json": {"key": "same", "verdict": "حدّي"},
            "state-ci-extra/b": {"key": "same", "verdict": "حدّي"},
            "state-ci/no-extension": {},
            "state-ci/a.txt": {"verdict": "موقوف"},
        }
        client = FakeClient([obj(key) for key in bodies], bodies)
        result = self.run_inventory(client)
        self.assertEqual(client.list_calls, [{"Bucket": "bucket", "Prefix": "state-ci"}])
        self.assertCountEqual(client.get_calls, bodies)
        self.assertEqual(result.per, {"حدّي": 2, "آخر": 1, "موقوف": 1})
        self.assertEqual((result.seen, result.read, result.failed), (4, 4, 0))
        self.assertFalse(result.partial)

    def test_cold_one_get_each_then_current_etag_warm_zero_gets(self):
        bodies = {f"state-ci/{n}": {"verdict": "مقبول" if n % 2 else "موقوف"}
                  for n in range(33)}
        objects = [obj(key) for key in bodies]
        cold = FakeClient(objects, bodies)
        first = self.run_inventory(cold)
        self.assertEqual(len(cold.get_calls), len(objects))
        self.assertEqual(first.hits, 0)
        warm = FakeClient(objects)
        second = self.run_inventory(warm)
        self.assertEqual(warm.get_calls, [])
        self.assertEqual(second.per, first.per)
        self.assertEqual((second.read, second.hits), (33, 33))
        self.assertEqual(len(warm.list_calls), 1)

    def test_changed_etag_does_not_reuse_old_report(self):
        cache.store(self.directory, "k", "old", {"verdict": "مقبول"})
        client = FakeClient([obj("k", '"new"')], {"k": {"verdict": "موقوف"}})
        result = self.run_inventory(client)
        self.assertEqual(result.per, {"موقوف": 1})
        self.assertEqual(client.get_calls, ["k"])
        self.assertEqual(result.hits, 0)

    def test_etag_changed_after_listing_counts_report_without_poisoning_cache(self):
        report = {"verdict": "موقوف"}
        client = FakeClient([obj("k", '"old"')], {"k": report},
                            response_etags={"k": '"new"'})
        with patch.object(subject, "store", wraps=cache.store) as store:
            result = self.run_inventory(client)
        self.assertEqual((result.seen, result.read, result.failed, result.hits), (1, 1, 0, 0))
        self.assertFalse(result.partial)
        self.assertEqual(result.per, {"موقوف": 1})
        self.assertEqual(client.get_calls, ["k"])
        store.assert_not_called()
        self.assertIsNone(cache.cached(self.directory, "k", "old"))
        self.assertIsNone(cache.cached(self.directory, "k", "new"))

    def test_missing_empty_or_invalid_get_etag_does_not_cache_but_counts_report(self):
        for etag in (None, "", '""', 17):
            with self.subTest(etag=etag):
                client = FakeClient([obj("k")], {"k": {"verdict": "حدّي"}},
                                    response_etags={"k": etag})
                with patch.object(subject, "store", wraps=cache.store) as store:
                    result = self.run_inventory(client)
                self.assertEqual((result.read, result.failed), (1, 0))
                self.assertFalse(result.partial)
                self.assertEqual(result.per, {"حدّي": 1})
                self.assertEqual(client.get_calls, ["k"])
                store.assert_not_called()
                self.assertIsNone(cache.cached(self.directory, "k", "v1"))

    def test_matching_list_and_get_etags_normalize_quotes_before_caching(self):
        for index, (listed, returned) in enumerate((
                ('"v1"', '"v1"'), ('"v1"', 'v1'),
                ('v1', '"v1"'), ('v1', 'v1'))):
            with self.subTest(listed=listed, returned=returned):
                key = f"key-{index}"
                report = {"verdict": "حدّي"}
                client = FakeClient([obj(key, listed)], {key: report},
                                    response_etags={key: returned})
                result = self.run_inventory(client)
                self.assertEqual((result.read, result.hits), (1, 0))
                self.assertEqual(client.get_calls, [key])
                self.assertEqual(cache.cached(self.directory, key, "v1"), report)
                warm = FakeClient([obj(key, listed)])
                self.assertEqual(self.run_inventory(warm).hits, 1)
                self.assertEqual(warm.get_calls, [])

    def test_missing_empty_or_invalid_etag_never_uses_or_creates_cache(self):
        cache.store(self.directory, "k", "", {"verdict": "مقبول"})
        for etag in (None, "", '""', 17):
            with self.subTest(etag=etag):
                client = FakeClient([obj("k", etag)], {"k": {"verdict": "موقوف"}})
                with patch.object(subject, "store") as store:
                    result = self.run_inventory(client)
                self.assertEqual(client.get_calls, ["k"])
                self.assertEqual(result.per, {"موقوف": 1})
                store.assert_not_called()
        client = FakeClient([{"Key": "k"}], {"k": {}})
        self.assertEqual(self.run_inventory(client).hits, 0)
        self.assertEqual(client.get_calls, ["k"])

    def test_corrupt_or_non_dictionary_cache_fetches_source(self):
        for content in ("{", "null", "[]", "1", '"text"'):
            with self.subTest(content=content):
                cache_path(self.directory, "k", "v1").write_text(content)
                client = FakeClient([obj("k")], {"k": {"verdict": "موقوف"}})
                result = self.run_inventory(client)
                self.assertEqual(result.per, {"موقوف": 1})
                self.assertEqual(client.get_calls, ["k"])
                self.assertEqual(result.hits, 0)

    def test_cache_io_failure_does_not_hide_source(self):
        client = FakeClient([obj("k")], {"k": {}})
        with patch.object(Path, "mkdir", side_effect=OSError("كتابة")), \
                patch.object(subject, "cached", side_effect=OSError("قراءة")), \
                patch.object(Path, "write_text", side_effect=OSError("كتابة")):
            result = self.run_inventory(client)
        self.assertEqual(result.read, 1)
        self.assertFalse(result.partial)

    def test_bad_json_non_dict_missing_and_get_errors_are_partial_without_retry(self):
        bodies = {"good": {"verdict": "حدّي"}, "json": b"{", "list": [],
                  "null": None, "text": "str", "number": 7,
                  "failure": OSError("قراءة")}
        client = FakeClient([obj(key) for key in [*bodies, "missing"]], bodies)
        result = self.run_inventory(client)
        self.assertEqual((result.seen, result.read, result.failed), (8, 1, 7))
        self.assertEqual(len(client.get_calls), 8)
        self.assertEqual(result.per, {"حدّي": 1})
        self.assertTrue(result.partial)
        self.assertTrue(all(stream.closed for stream in client.streams))

    def test_body_read_failure_closes_body_and_counts_failure(self):
        class BadBody(io.BytesIO):
            def read(self):
                raise OSError("انقطعت القراءة")
        body = BadBody()
        client = FakeClient([obj("k")], {"k": body})
        self.assertEqual(self.run_inventory(client).failed, 1)
        self.assertTrue(body.closed)

    def test_malformed_list_object_is_failed_not_silently_skipped(self):
        result = self.run_inventory(FakeClient([{}]))
        self.assertEqual((result.seen, result.failed), (1, 1))
        self.assertTrue(result.partial)

    def test_listing_failure_preserves_previous_page_counts(self):
        client = FakeClient(bodies={"k": {"verdict": "حدّي"}},
                            pages=[{}, {"Contents": [obj("k")]}], list_error=True)
        result = self.run_inventory(client)
        self.assertEqual((result.seen, result.read), (1, 1))
        self.assertEqual(result.per, {"حدّي": 1})
        self.assertTrue(result.list_failed)
        self.assertTrue(result.partial)

    def test_initial_listing_failure_is_not_successful_empty_inventory(self):
        client = FakeClient(pages=[], list_error=True)
        result = self.run_inventory(client)
        self.assertTrue(result.partial)
        self.assertEqual(result.seen, 0)
        self.assertEqual(client.get_calls, [])

    def test_paginator_creation_failure_is_partial(self):
        client = FakeClient()
        with patch.object(client, "get_paginator", side_effect=OSError("سرد")):
            self.assertTrue(self.run_inventory(client).list_failed)

    def test_empty_inventory_is_complete(self):
        result = self.run_inventory(FakeClient(pages=[{}]))
        self.assertFalse(result.partial)
        self.assertEqual(result.read, 0)

    def test_tied_counts_keep_listing_order(self):
        client = FakeClient([obj("b"), obj("a")],
                            {"b": {"verdict": "موقوف"}, "a": {"verdict": "حدّي"}})
        self.assertEqual(self.run_inventory(client).per.most_common(),
                         [("موقوف", 1), ("حدّي", 1)])

    def test_reads_are_parallel_and_never_exceed_sixteen(self):
        class ConcurrentClient(FakeClient):
            active = 0
            maximum = 0
            def get_object(self, **kwargs):
                with self.lock:
                    self.active += 1
                    self.maximum = max(self.maximum, self.active)
                    if self.active == 16:
                        ready.set()
                try:
                    if not ready.wait(5):
                        raise AssertionError("لم تصل القراءات المتوازية إلى 16")
                    return super().get_object(**kwargs)
                finally:
                    with self.lock:
                        self.active -= 1
        ready = threading.Event()
        client = ConcurrentClient([obj(str(i)) for i in range(48)],
                                  {str(i): {} for i in range(48)})
        result = self.run_inventory(client)
        self.assertEqual(result.read, 48)
        self.assertEqual(client.maximum, 16)
        self.assertEqual(len(client.get_calls), 48)

    def test_summary_marks_partial_counts_and_incomplete_listing(self):
        result = subject.Inventory(per=Counter({"حدّي": 2}), seen=3, read=2,
                                   failed=1, list_failed=True)
        output = io.StringIO()
        with redirect_stdout(output):
            subject.print_summary(result)
        self.assertIn("جرد جزئي", output.getvalue())
        self.assertIn("حدّي: 2", output.getvalue())
        self.assertIn("قُرئ 2 من 3", output.getvalue())
        self.assertIn("تعذّر 1", output.getvalue())
        self.assertIn("عدد الكائنات الكلي غير معلوم", output.getvalue())

    def test_main_status_and_original_client_configuration(self):
        credentials = {"endpoint": "https://example.invalid", "accessKeyId": "test",
                       "secretAccessKey": "test", "bucket": "bucket"}
        path = self.directory / "credentials.json"
        path.write_text(json.dumps(credentials))
        for partial in (False, True):
            with self.subTest(partial=partial):
                fake = types.SimpleNamespace(client=unittest.mock.Mock(return_value="client"))
                result = subject.Inventory(failed=int(partial))
                with patch.dict("sys.modules", {"boto3": fake}), \
                        patch.object(subject, "CREDS", path), \
                        patch.object(subject, "inventory", return_value=result) as inventory, \
                        redirect_stdout(io.StringIO()):
                    self.assertEqual(subject.main(), int(partial))
                inventory.assert_called_once_with("client", "bucket")
                fake.client.assert_called_once_with(
                    "s3", endpoint_url=credentials["endpoint"], aws_access_key_id="test",
                    aws_secret_access_key="test", region_name="auto")

    def test_main_missing_credentials_reports_partial_and_exits_one(self):
        with patch.dict("sys.modules", {"boto3": types.SimpleNamespace()}), \
                patch.object(subject, "CREDS", self.directory / "missing"), \
                redirect_stdout(io.StringIO()) as output:
            self.assertEqual(subject.main(), 1)
        self.assertIn("جرد جزئي", output.getvalue())


class PromoteCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        for patcher in (
                patch.object(promote, "__file__", str(self.directory / "promote.py")),
                patch.object(promote, "STATE_PREFIXES", ("state/",)),
                patch.object(promote, "READ_FAILED", 0),
                patch.object(promote.time, "sleep")):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.cache_dir = self.directory / "work" / "verdict_cache"
        self.cache_dir.mkdir(parents=True)

    def test_promote_still_filters_suffix_and_requires_report_key_and_flattens_lists(self):
        one, two = {"key": "a"}, {"key": "b"}
        client = FakeClient([obj("state/a.json"), obj("state/b.txt")],
                            {"state/a.json": [one, two, {}, None]})
        with redirect_stdout(io.StringIO()):
            result = promote.bucket_reports(client, "bucket")
        self.assertEqual(result, [("state/a.json", one), ("state/a.json", two)])
        self.assertEqual(client.get_calls, ["state/a.json"])
        self.assertEqual(promote.READ_FAILED, 0)
        warm = FakeClient([obj("state/a.json")])
        with redirect_stdout(io.StringIO()):
            self.assertEqual(promote.bucket_reports(warm, "bucket"), result)
        self.assertEqual(warm.get_calls, [])

    def test_promote_keeps_retry_count_and_read_failure_guard(self):
        client = FakeClient([obj("state/a.json")], {"state/a.json": OSError("قراءة")})
        with redirect_stdout(io.StringIO()):
            self.assertEqual(promote.bucket_reports(client, "bucket"), [])
        self.assertEqual(client.get_calls, ["state/a.json"] * 3)
        self.assertEqual(promote.READ_FAILED, 1)

    def test_inventory_can_reuse_matching_dictionary_cached_by_promote(self):
        report = {"key": "timings/a", "verdict": "حدّي"}
        client = FakeClient([obj("state-ci/a.json")], {"state-ci/a.json": report})
        with patch.object(promote, "STATE_PREFIXES", ("state-ci",)), redirect_stdout(io.StringIO()):
            promote.bucket_reports(client, "bucket")
        warm = FakeClient([obj("state-ci/a.json")])
        result = subject.inventory(warm, "bucket", self.cache_dir)
        self.assertEqual((result.hits, result.read), (1, 1))
        self.assertEqual(result.per, {"حدّي": 1})
        self.assertEqual(warm.get_calls, [])


if __name__ == "__main__":
    unittest.main()
