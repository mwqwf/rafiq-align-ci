#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""سلسلةُ الدفعات فوق مرشّح مسرحٍ ورث إسقاطاً (2026-11-10): حارسُ البنية في التحزيم يُحكم بالأصل **المنشور**."""
import gzip
import hashlib
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import promote  # noqa: E402
from stage_transform import (AYAH_COUNTS, needs_drop_parent, published_origin,  # noqa: E402
                             published_owner_approved, parent_coded_approved)

RIW, RID, HIDE = "qalun", "rak_test", 36
REASON = "توقيتٌ قيد الإصلاح"


def entries(skip):
    return [{"ayahId": f"{s}:{a}", "startMs": 0, "endMs": 1}
            for s in range(1, 115) if s not in skip for a in range(1, AYAH_COUNTS[s - 1] + 1)]


def index(skip, transform):
    es = entries(skip)
    return {"riwaya": RIW, "reciterId": RID, "refineVersion": 2, "ayahCount": 6236,
            "missing": {"count": 6236 - len(es)}, "entries": es, "transform": transform}


LIVE = index({HIDE}, {"op": f"drop_surah:{HIDE}", "reasonCode": "OTHER", "reasonUser": REASON,
                      "dropSurah": [HIDE]})
LIVE_BODY = gzip.compress(json.dumps(LIVE).encode("utf-8"))
LIVE_SHA = hashlib.sha256(LIVE_BODY).hexdigest()
ROW_KEY = f"timings-staging/{RIW}/{RID}.{LIVE_SHA[:8]}.jz"


def chained(from_sha=LIVE_SHA, from_key=f"timings/{RIW}/{RID}.jz"):
    """منتَجُ الدفعة الثانية: يرث إعلانَ الحيّ ومصدرُه في الترويسة هو الحيّ."""
    return index({HIDE}, {"op": "ctc_splice:heard:7-12", "reasonCode": "OTHER", "reasonUser": REASON,
                          "dropSurah": [HIDE], "fromSha256": from_sha, "fromKey": from_key})


def fetch(key):
    if key == f"timings/{RIW}/{RID}.jz":
        return LIVE_BODY
    raise KeyError(key)


def gate(idx, approvals):
    dp, dps = published_origin(idx, fetch)
    own = published_owner_approved(dp, dps, approvals) if needs_drop_parent(idx) else frozenset()
    inh = parent_coded_approved(dp, idx, f"timings/{RIW}/{RID}.jz", dps, approvals)
    return promote.index_gate(idx, parent=dp, parent_sha=dps, owner_approved=own,
                              coded_approved=inh, inherited_rows=[])


class PublishedOrigin(unittest.TestCase):
    def test_chain_passes_with_live_row(self):
        self.assertIsNone(gate(chained(), {ROW_KEY: frozenset({HIDE})}))

    def test_old_call_without_parent_refused(self):
        why = promote.index_gate(chained(), inherited_rows=[])
        self.assertIn("بلا أصل منشور", why)

    def test_no_live_row_refused(self):
        self.assertIsNotNone(gate(chained(), {}))

    def test_other_key_row_ignored(self):
        self.assertIsNotNone(gate(chained(), {f"timings-staging/{RIW}/{RID}.deadbeef.jz": frozenset({HIDE})}))

    def test_wrong_origin_sha_refused(self):
        self.assertIn("بلا أصل منشور", gate(chained(from_sha="0" * 64), {ROW_KEY: frozenset({HIDE})}))

    def test_wrong_origin_key_refused(self):
        bad = chained(from_key=f"timings-staging/{RIW}/{RID}.f4a70aad.jz")
        self.assertIn("بلا أصل منشور", gate(bad, {ROW_KEY: frozenset({HIDE})}))

    def test_new_hide_refused(self):
        idx = index({HIDE, 55}, dict(chained()["transform"], dropSurah=[HIDE, 55]))
        self.assertIsNotNone(gate(idx, {ROW_KEY: frozenset({HIDE, 55})}))

    def test_lost_entry_refused(self):
        idx = chained()
        idx["entries"] = [e for e in idx["entries"] if e["ayahId"] != "2:5"]
        idx["missing"]["count"] += 1
        self.assertIsNotNone(gate(idx, {ROW_KEY: frozenset({HIDE})}))

    def test_unpublished_reader(self):
        self.assertEqual(published_origin({"riwaya": RIW, "reciterId": "none"}, fetch), (None, None))

    def test_owner_row_only_declared_in_live(self):
        self.assertEqual(published_owner_approved(LIVE, LIVE_SHA, {ROW_KEY: frozenset({HIDE, 55})}),
                         frozenset({HIDE}))

    def test_mixed_live_truncated_and_hidden(self):
        """حيٌّ يجمع بتراً معلناً (4) وحجباً مؤقّتاً (36) بصفٍّ يسمّيهما (‏حالة akri_qalun)."""
        live = index({4, HIDE}, {"op": f"drop_surah:4,{HIDE}", "reasonCode": "OTHER", "reasonUser": REASON,
                                 "declarations": {"4": {"op": "drop_surah", "reasonCode": "SOURCE_TRUNCATED",
                                                        "reasonUser": "ناقص"},
                                                  str(HIDE): {"op": "drop_surah", "reasonCode": "OTHER",
                                                              "reasonUser": REASON}}})
        body = gzip.compress(json.dumps(live).encode("utf-8"))
        sha = hashlib.sha256(body).hexdigest()
        cand = index({4, HIDE}, dict(live["transform"], op="ctc_splice:heard:7-12", dropSurah=[4, HIDE],
                                     fromSha256=sha, fromKey=f"timings/{RIW}/{RID}.jz"))
        cand["missing"]["byReason"] = {"source_truncated": AYAH_COUNTS[3]}
        row = {f"timings-staging/{RIW}/{RID}.{sha[:8]}.jz": frozenset({4, HIDE})}
        own = published_owner_approved(live, sha, row)
        self.assertEqual(own, frozenset({4, HIDE}))
        inh = parent_coded_approved(live, cand, f"timings/{RIW}/{RID}.jz", sha, row)
        self.assertIsNone(promote.index_gate(cand, parent=live, parent_sha=sha, owner_approved=own,
                                             coded_approved=inh, inherited_rows=[]))
        self.assertIsNotNone(promote.index_gate(cand, parent=live, parent_sha=sha,
                                                owner_approved=frozenset({HIDE}), coded_approved=inh,
                                                inherited_rows=[]))

if __name__ == "__main__":
    unittest.main()
