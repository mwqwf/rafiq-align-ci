"""🔎 صيد الأخطاء 2026-10-09: حرّاسٌ كانت تمرّر عند تعثّر القراءة أو شذوذ المدخل — تُختبر هنا أنّها تقف."""
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import promote as P  # noqa: E402


class Boom:
    def get_object(self, **_k):
        raise ConnectionError("timeout")


def _rep(hi, n=200):
    return {"key": "timings-staging/hafs/x.aaaaaaaa.jz", "riwaya": "hafs", "reciterId": "x",
            "verdict": "مقبول", "fatal": [], "sha256": "a" * 64, "ts": 1,
            "sample": {"severe": [0, n, [0.0, 0.0, hi]], "rows": [1]}}


class GuardsFailClosed(unittest.TestCase):
    def tearDown(self):
        P._CATALOG = None
        P.OPENERS_TRUSTED = set()

    def test_catalog_read_failure_stops_instead_of_empty(self):
        P._CATALOG = None
        with self.assertRaises(SystemExit):
            P.catalog(Boom(), "b")

    def test_truncation_read_failure_is_stale_not_missing(self):
        self.assertEqual(P.truncation(Boom(), "b", "hafs", "x", None), ([], "stale"))

    def test_frozen_key_without_sha_stays_frozen(self):
        self.assertEqual(P.parse_frozen("timings/hafs/x.jz\n"), {"timings/hafs/x.jz": ""})

    def test_hold_without_reason_stays_held(self):
        d = pathlib.Path(tempfile.mkdtemp())
        f = d / "hold.txt"
        f.write_text("timings/hafs/x.jz\n", encoding="utf-8")
        old = P.HOLD
        try:
            P.HOLD = f
            self.assertIn("timings/hafs/x.jz", P.held())
        finally:
            P.HOLD = old

    def test_nan_upper_bound_is_refused(self):
        P.WITHDRAWN_MAP = {}
        _t, why = P.gate(_rep(float("nan")), {}, "", {}, None, {}, None, {})
        self.assertIsNotNone(why)

    def test_float_sample_size_does_not_skip_minimum(self):
        P.WITHDRAWN_MAP = {}
        _t, why = P.gate(_rep(0.04, n=10.0), {}, "", {}, None, {}, None, {})
        self.assertIsNotNone(why)

    def test_short_commit_is_not_trusted(self):
        P.OPENERS_TRUSTED = {"c9f21837"}
        self.assertFalse(P.openers_tool_ok({"commit": "9"}))
        self.assertFalse(P.openers_tool_ok({"commit": "c9"}))


if __name__ == "__main__":
    unittest.main()
