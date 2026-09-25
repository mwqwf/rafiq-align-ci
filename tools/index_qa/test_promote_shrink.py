"""حارسُ «لا ترقيةَ تُنقص المنشور» (2026-09-25، soufi_sousi 6234⇒6216)."""
import gzip
import io
import json
import unittest

from tools.index_qa.promote import shrink_refusal


class _Missing(Exception):
    response = {"Error": {"Code": "NoSuchKey"}}


class _Cl:
    def __init__(self, n=None, exc=None, raw=None):
        self.n, self.exc, self.raw = n, exc, raw

    def get_object(self, **_kw):
        if self.exc:
            raise self.exc
        body = self.raw if self.raw is not None else gzip.compress(
            json.dumps({"entries": [0] * self.n}).encode())
        return {"Body": io.BytesIO(body)}


T = "timings/sousi/soufi_sousi.jz"


class ShrinkTest(unittest.TestCase):
    def test_smaller_candidate_refused(self):
        self.assertIn("6216 < 6234", shrink_refusal(_Cl(6234), "b", T, 6216))

    def test_equal_or_larger_passes(self):
        self.assertIsNone(shrink_refusal(_Cl(6234), "b", T, 6234))
        self.assertIsNone(shrink_refusal(_Cl(6234), "b", T, 6235))

    def test_first_publish_passes(self):
        self.assertIsNone(shrink_refusal(_Cl(exc=_Missing()), "b", T, 10))

    def test_unreadable_live_refuses(self):
        self.assertIsNotNone(shrink_refusal(_Cl(exc=OSError("net")), "b", T, 6236))
        self.assertIsNotNone(shrink_refusal(_Cl(raw=b"junk"), "b", T, 6236))

    def test_allow_shrink_needs_same_target_and_reason(self):
        self.assertIsNotNone(shrink_refusal(_Cl(6234), "b", T, 6216, "timings/hafs/x.jz", "سبب"))
        self.assertIsNotNone(shrink_refusal(_Cl(6234), "b", T, 6216, T, "  "))
        self.assertIsNone(shrink_refusal(_Cl(6234), "b", T, 6216, T, "إسقاطُ سورةٍ تالفة"))


if __name__ == "__main__":
    unittest.main()
