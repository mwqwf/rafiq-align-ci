"""مرشّحٌ أكبرُ مُحكَمٌ لا يُظلّل مرشّحاً أصغرَ سليماً للقارئ نفسِه (2026-09-25).

بلا شبكةٍ ولا دلو: `s3` و`fetch_index` و`_salt_count` و`subprocess.run` محاكاة."""
import datetime as dt
import types
import unittest
from unittest import mock

from tools.ci_fleet import restore_loop as loop

T = lambda h: dt.datetime(2026, 9, 25, h)                       # noqa: E731
LIVE = "timings/qalun/akri_qalun.jz"
BIG = "timings-staging/qalun/akri_qalun.8b9fea7c.jz"     # أكبرُ زيادةً، مبتورُ السور
GOOD = "timings-staging/qalun/akri_qalun.655f19d5.jz"    # أحدثُ وأصغرُ زيادةً، سليم
OTHER_LIVE = "timings/hafs/x.jz"
OTHER = "timings-staging/hafs/x.1111.jz"


class _Pag:
    def __init__(self, objs):
        self.objs = objs

    def paginate(self, Bucket, Prefix):                        # noqa: N803
        return [{"Contents": [o for o in self.objs if o["Key"].startswith(Prefix)]}]


class _S3:
    def __init__(self, objs):
        self.objs = objs

    def get_paginator(self, _n):
        return _Pag(self.objs)


def _bucket(objs, sizes):
    return (mock.patch.object(loop, "s3", return_value=(_S3(objs), "b")),
            mock.patch.object(loop, "fetch_index",
                              side_effect=lambda k: ({"entries": [0] * sizes[k]}, None)))


OBJS = [{"Key": LIVE, "LastModified": T(1)},
        {"Key": BIG, "LastModified": T(2)},
        {"Key": GOOD, "LastModified": T(3)},
        {"Key": OTHER_LIVE, "LastModified": T(1)},
        {"Key": OTHER, "LastModified": T(2)}]
SIZES = {LIVE: 6000, BIG: 6100, GOOD: 6033, OTHER_LIVE: 6200, OTHER: 6210}


class StagedImprovementsTests(unittest.TestCase):
    def test_returns_all_improved_candidates_grouped_by_reciter(self):
        a, b = _bucket(OBJS, SIZES)
        with a, b:
            got = loop._staged_improvements()
        self.assertEqual([(r["key"], r["gain"]) for r in got],
                         [(BIG, 100), (GOOD, 33), (OTHER, 10)])
        self.assertTrue(all(r["live"] in (LIVE, OTHER_LIVE) for r in got))

    def test_not_improved_or_older_than_live_are_dropped(self):
        objs = OBJS + [{"Key": "timings-staging/qalun/akri_qalun.old.jz", "LastModified": T(0)},
                       {"Key": "timings-staging/qalun/akri_qalun.same.jz", "LastModified": T(4)}]
        sizes = dict(SIZES, **{"timings-staging/qalun/akri_qalun.same.jz": 6000})
        a, b = _bucket(objs, sizes)
        with a, b:
            keys = [r["key"] for r in loop._staged_improvements()]
        self.assertNotIn("timings-staging/qalun/akri_qalun.old.jz", keys)
        self.assertNotIn("timings-staging/qalun/akri_qalun.same.jz", keys)


def _imp():
    return [{"key": BIG, "live": LIVE, "gain": 100, "riwaya": "qalun", "reciter": "akri_qalun"},
            {"key": GOOD, "live": LIVE, "gain": 33, "riwaya": "qalun", "reciter": "akri_qalun"},
            {"key": OTHER, "live": OTHER_LIVE, "gain": 10, "riwaya": "hafs", "reciter": "x"}]


class GateShadowTests(unittest.TestCase):
    def _gate(self, salts, struct=lambda k: None):
        calls = []
        with mock.patch.object(loop, "inflight_reciters", return_value=set()), \
             mock.patch.object(loop, "_staged_improvements", return_value=_imp()), \
             mock.patch.object(loop, "_salt_count", side_effect=lambda k: salts.get(k, 0)), \
             mock.patch.object(loop, "_struct_fatal", side_effect=struct), \
             mock.patch.object(loop, "_census_due", return_value=False), \
             mock.patch.object(loop, "gh", side_effect=lambda *x: calls.append(x) or ""):
            loop.cmd_gate(types.SimpleNamespace(limit=6))
        return [c for c in calls if "openers.yml" in c]

    def test_salted_bigger_does_not_shadow_unsalted_smaller(self):
        op = self._gate({BIG: 4, GOOD: 0, OTHER: 4})
        self.assertEqual(len(op), 1)
        self.assertIn(f"only={GOOD}", op[0])

    def test_one_gate_per_reciter_biggest_unsalted(self):
        # الحالةُ العادية: لا مُحكَمَ فوقه ⇒ يُبوَّب الأكبرُ وحده كما كان
        op = self._gate({})
        self.assertEqual(len(op), 1)
        self.assertIn(f"only={BIG},{OTHER}", op[0])
        self.assertNotIn(GOOD, op[0])

    def test_struct_rejected_bigger_falls_to_next(self):
        op = self._gate({}, struct=lambda k: "سورةٌ غائبة" if k == BIG else None)
        self.assertIn(f"only={GOOD},{OTHER}", op[0])

    def test_all_salted_gates_nothing(self):
        self.assertEqual(self._gate({BIG: 4, GOOD: 4, OTHER: 4}), [])


class PromoteFallbackTests(unittest.TestCase):
    def _promote(self, dry, real, salts):
        tried = []

        def run(cmd, **_kw):
            if "--unfreeze" in cmd or "refreeze.py" in " ".join(map(str, cmd)):
                return types.SimpleNamespace(stdout="", returncode=0)
            k = cmd[cmd.index("--only") + 1]
            tried.append((k, "--yes" in cmd))
            return types.SimpleNamespace(stdout=(real if "--yes" in cmd else dry)(k),
                                         returncode=0)
        with mock.patch.object(loop, "_staged_improvements", return_value=_imp()), \
             mock.patch.object(loop, "_salt_count", side_effect=lambda k: salts.get(k, 0)), \
             mock.patch.object(loop.subprocess, "run", side_effect=run), \
             mock.patch.object(loop, "gh", return_value=""):
            loop.cmd_promote(types.SimpleNamespace())
        return tried

    def test_rejected_bigger_then_smaller_is_promoted(self):
        tried = self._promote(
            lambda k: "⛔ سورٌ مبتورةٌ في المصدر" if k == BIG else "✅ جاهز",
            lambda k: "→ ✅", {BIG: 4, GOOD: 4, OTHER: 4})
        self.assertEqual(tried, [(BIG, False), (GOOD, False), (GOOD, True),
                                 (OTHER, False), (OTHER, True)])

    def test_at_most_one_promotion_per_reciter(self):
        tried = self._promote(lambda k: "✅ جاهز", lambda k: "→ ✅",
                              {BIG: 4, GOOD: 4, OTHER: 4})
        self.assertEqual([k for k, yes in tried if yes], [BIG, OTHER])

    def test_unsalted_smaller_is_not_tried(self):
        tried = self._promote(lambda k: "⛔ مبتورة" if k == BIG else "✅ جاهز",
                              lambda k: "→ ✅", {BIG: 4, GOOD: 3, OTHER: 4})
        self.assertNotIn(GOOD, [k for k, _ in tried])

    def test_stale_diagnosis_does_not_fall_through(self):
        tried = self._promote(
            lambda k: ("⏳ تشخيص الكتالوج يصف فهرساً آخر" if k == BIG else "✅ جاهز"),
            lambda k: "→ ✅", {BIG: 4, GOOD: 4, OTHER: 4})
        self.assertNotIn(GOOD, [k for k, _ in tried])


if __name__ == "__main__":
    unittest.main()
