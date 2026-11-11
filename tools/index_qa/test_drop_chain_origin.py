#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""سلسلةُ المنشأ لإعلان الغياب الموروث (أمر القائد 2026-11-11): تُمشى إلى الحيّ الحاليّ ببصمة المحتوى الكاملة لكلّ حلقة.

اختباراتُ طفراتٍ لكلّ حقل: fromKey · البصمة · الأصل (الحيّ) · قائمة الإسقاط · حلقةٌ وسطى مبدَّلةُ البايتات · حيٌّ متبدّل،
والعمقُ والدائريةُ والحلقةُ المفقودةُ، وبقاءُ السلسلة ذاتِ المستوى الواحد كما كانت.
    python -m unittest tools/index_qa/test_drop_chain_origin.py
"""
import gzip
import hashlib
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import promote  # noqa: E402
from stage_transform import AYAH_COUNTS  # noqa: E402

RIW, RID, HIDE = "qalun", "chain_test", 36
REASON = "توقيتٌ قيد الإصلاح"
LIVE_KEY = f"timings/{RIW}/{RID}.jz"


def entries(skip):
    return [{"ayahId": f"{s}:{a}", "startMs": 0, "endMs": 1}
            for s in range(1, 115) if s not in skip for a in range(1, AYAH_COUNTS[s - 1] + 1)]


def index(transform, skip=(HIDE,)):
    es = entries(set(skip))
    return {"riwaya": RIW, "reciterId": RID, "refineVersion": 2, "ayahCount": 6236,
            "missing": {"count": 6236 - len(es)}, "entries": es, "transform": transform}


def blob(idx):
    b = gzip.compress(json.dumps(idx, sort_keys=True).encode("utf-8"))
    return b, hashlib.sha256(b).hexdigest()


def hdr(op, frm_key, frm_sha, drops=(HIDE,), **kw):
    t = {"op": op, "reasonCode": "OTHER", "reasonUser": REASON, "dropSurah": list(drops),
         "fromKey": frm_key, "fromSha256": frm_sha}
    t.update(kw)
    return t


def skey(sha):
    return f"timings-staging/{RIW}/{RID}.{sha[:8]}.jz"


class World:
    """الحيّ ← L1 ← L2 ← المنتَج؛ والجالبُ يقرأ من قاموسٍ في الذاكرة."""

    def __init__(self):
        self.live = index({"op": f"drop_surah:{HIDE}", "reasonCode": "OTHER", "reasonUser": REASON,
                           "dropSurah": [HIDE]})
        self.live_body, self.live_sha = blob(self.live)
        self.l1 = index(hdr("ctc_splice:heard:1-2", LIVE_KEY, self.live_sha))
        self.l1_body, self.l1_sha = blob(self.l1)
        self.l2 = index(hdr("ctc_splice:heard:3-4", skey(self.l1_sha), self.l1_sha))
        self.l2_body, self.l2_sha = blob(self.l2)
        self.product = index(hdr("ctc_splice:heard:5-6", skey(self.l2_sha), self.l2_sha))
        self.store = {LIVE_KEY: self.live_body, skey(self.l1_sha): self.l1_body, skey(self.l2_sha): self.l2_body}

    def fetch(self, key):
        return self.store[key]

    def gate(self, idx=None, live_sha=None, live=None):
        return promote.index_gate(idx or self.product, parent=live or self.live,
                                  parent_sha=live_sha or self.live_sha, inherited_rows=[],
                                  owner_approved=frozenset({HIDE}), coded_approved=frozenset({HIDE}),
                                  chain_fetch=self.fetch)


class Accepts(unittest.TestCase):
    def test_three_links_accepted(self):
        w = World()
        self.assertIsNone(w.gate())

    def test_walk_returns_live(self):
        w = World()
        live, sha, why = promote.drop_chain_origin(w.product, w.fetch)
        self.assertIsNone(why)
        self.assertEqual(sha, w.live_sha)
        self.assertEqual(live["transform"]["op"], f"drop_surah:{HIDE}")

    def test_live_op_with_declare_gap_suffix(self):
        """akri_qalun: الحيّ op=`drop_surah:…|declare_gap:24` بلا حقل dropSurah — الـ24 حجبٌ لا إسقاط."""
        w = World()
        self.assertEqual(promote._declared_surahs({"op": "drop_surah:4,10,37|declare_gap:24"}), {"4", "10", "37"})
        live = index({"op": f"drop_surah:{HIDE}|declare_gap:24", "reasonCode": "OTHER", "reasonUser": REASON})
        lb, lsha = blob(live)
        link = index(hdr("ctc_splice:heard:1-2", LIVE_KEY, lsha))
        b, sha = blob(link)
        prod = index(hdr("ctc_splice:heard:3-4", skey(sha), sha))
        got = promote.drop_chain_origin(prod, {LIVE_KEY: lb, skey(sha): b}.__getitem__)
        self.assertEqual((got[1], got[2]), (lsha, None))

    def test_single_level_unchanged_without_fetch(self):
        w = World()
        one = index(hdr("ctc_splice:heard:7-8", LIVE_KEY, w.live_sha))
        self.assertIsNone(promote.index_gate(one, parent=w.live, parent_sha=w.live_sha, inherited_rows=[],
                                             owner_approved=frozenset({HIDE}), coded_approved=frozenset({HIDE})))

    def test_staged_origin_without_fetch_still_refused(self):
        w = World()
        why = promote.index_gate(w.product, parent=w.live, parent_sha=w.live_sha, inherited_rows=[])
        self.assertIn("بلا أصل منشور", why)
        self.assertNotIn("—", why)                      # رُدّ قبل المشي لا بعده: لا جالبَ ⇒ لا سلسلة


class Mutations(unittest.TestCase):
    def test_product_from_key_other_reciter(self):
        w = World()
        w.product["transform"]["fromKey"] = f"timings-staging/{RIW}/other.{w.l2_sha[:8]}.jz"
        self.assertIn("بلا أصل منشور", w.gate())

    def test_product_from_key_not_fetchable(self):
        w = World()
        w.product["transform"]["fromKey"] = skey("0" * 64)
        self.assertIn("حلقةٌ مفقودةٌ", w.gate())

    def test_product_from_sha_wrong(self):
        w = World()
        w.product["transform"]["fromSha256"] = "0" * 64
        self.assertIn("بصمةُ محتوى", w.gate())

    def test_middle_link_bytes_swapped(self):
        w = World()
        evil = index(hdr("ctc_splice:heard:3-4", skey(w.l1_sha), w.l1_sha), skip=(HIDE, 55))
        w.store[skey(w.l2_sha)] = blob(evil)[0]
        self.assertIn("بصمةُ محتوى", w.gate())

    def test_name_alone_is_not_trusted(self):
        w = World()
        w.store[skey(w.l1_sha)] = w.live_body          # الاسمُ اسمُ L1 والبايتاتُ بايتاتُ الحيّ
        self.assertIn("بصمةُ محتوى", w.gate())

    def test_chain_ends_at_older_live(self):
        w = World()
        newer = index({"op": f"drop_surah:{HIDE}", "reasonCode": "OTHER", "reasonUser": REASON,
                       "dropSurah": [HIDE], "note": "حيٌّ أحدث"})
        nb, nsha = blob(newer)
        w.store[LIVE_KEY] = w.live_body                  # السلسلةُ تنتهي عند الحيّ القديم
        why = w.gate(live=newer, live_sha=nsha)
        self.assertIn("لا تنتهي بالحيّ الحاليّ", why)

    def test_live_swapped_after_chain_built(self):
        w = World()
        newer = index({"op": f"drop_surah:{HIDE}", "reasonCode": "OTHER", "reasonUser": REASON,
                       "dropSurah": [HIDE], "note": "تبدّل"})
        nb, nsha = blob(newer)
        w.store[LIVE_KEY] = nb                           # الدلوُ تبدّل: بصمةُ الحلقة الأخيرة لا تطابق
        self.assertIn("بصمةُ محتوى", w.gate(live=newer, live_sha=nsha))

    def test_drop_list_added_in_product(self):
        w = World()
        w.product["transform"]["dropSurah"] = [HIDE, 55]
        w.product = dict(w.product, entries=entries({HIDE, 55}))
        self.assertIsNotNone(w.gate())

    def test_drop_list_disappears_in_middle(self):
        w = World()
        w.l1["transform"]["dropSurah"] = []
        w.store[skey(w.l1_sha)] = blob(w.l1)[0]
        l1sha = blob(w.l1)[1]
        w.l2["transform"].update(fromKey=skey(l1sha), fromSha256=l1sha)
        w.store[skey(w.l2_sha)] = blob(w.l2)[0]
        w.store[skey(l1sha)] = blob(w.l1)[0]
        w.product["transform"].update(fromSha256=blob(w.l2)[1], fromKey=skey(blob(w.l2)[1]))
        w.store[skey(blob(w.l2)[1])] = blob(w.l2)[0]
        # L1 يفقد dropSurah ويبقى op=ctc_splice ⇒ مجموعتُه الفارغةُ تخالف المنتَج
        self.assertIn("تبدّلت", w.gate())

    def test_middle_link_adds_new_drop(self):
        w = World()
        w.l1["transform"]["dropSurah"] = [HIDE, 77]
        b, sha = blob(w.l1)
        w.store[skey(sha)] = b
        w.l2["transform"].update(fromKey=skey(sha), fromSha256=sha)
        b2, sha2 = blob(w.l2)
        w.store[skey(sha2)] = b2
        w.product["transform"].update(fromKey=skey(sha2), fromSha256=sha2)
        self.assertIn("تبدّلت", w.gate())

    def test_reason_changed_in_middle(self):
        w = World()
        w.l1["transform"]["reasonUser"] = "سببٌ آخر"
        b, sha = blob(w.l1)
        w.store[skey(sha)] = b
        w.l2["transform"].update(fromKey=skey(sha), fromSha256=sha)
        b2, sha2 = blob(w.l2)
        w.store[skey(sha2)] = b2
        w.product["transform"].update(fromKey=skey(sha2), fromSha256=sha2)
        self.assertIn("reasonCode/reasonUser", w.gate())

    def test_gap_declaration_vanishes(self):
        w = World()
        gap = {"79": {"absent": [15], "evidenceKind": "x"}}
        w.product["transform"]["truncatedGaps"] = gap
        w.l1["transform"]["truncatedGaps"] = gap
        b, sha = blob(w.l1)
        w.store[skey(sha)] = b
        w.l2["transform"].update(fromKey=skey(sha), fromSha256=sha)     # L2 بلا إعلان الحجب
        b2, sha2 = blob(w.l2)
        w.store[skey(sha2)] = b2
        w.product["transform"].update(fromKey=skey(sha2), fromSha256=sha2)
        why = promote.drop_chain_origin(w.product, w.fetch)[2]
        self.assertIn("حجبٍ وسطيّ", why)

    def test_cycle_refused(self):
        w = World()
        w.l1["transform"].update(fromKey=skey(w.l2_sha), fromSha256=w.l2_sha)
        b, sha = blob(w.l1)
        w.store[skey(sha)] = b
        w.l2["transform"].update(fromKey=skey(sha), fromSha256=sha)
        b2, sha2 = blob(w.l2)
        w.store[skey(sha2)] = b2
        w.store[skey(w.l2_sha)] = b2
        w.product["transform"].update(fromKey=skey(sha2), fromSha256=sha2)
        why = promote.drop_chain_origin(w.product, w.fetch)[2]
        self.assertTrue(why and ("دائرية" in why or "بصمةُ" in why or "أطولُ" in why))

    def test_self_cycle_refused(self):
        w = World()
        loop = index(hdr("ctc_splice:heard:1-2", "x", "0" * 64))
        # حلقةٌ تشير إلى نفسها: بصمتُها لا تُحسب داخلها فنختبر الدائريةَ بمفتاحٍ مكرّر
        b, sha = blob(loop)
        loop["transform"].update(fromKey=skey(sha), fromSha256=sha)
        w.store[skey(sha)] = b
        w.product["transform"].update(fromKey=skey(sha), fromSha256=sha)
        self.assertIsNotNone(promote.drop_chain_origin(w.product, w.fetch)[2])

    def test_depth_limit(self):
        w = World()
        prev_key, prev_sha = LIVE_KEY, w.live_sha
        for i in range(promote.CHAIN_MAX_DEPTH):
            link = index(hdr(f"ctc_splice:heard:{i}", prev_key, prev_sha))
            b, sha = blob(link)
            w.store[skey(sha)] = b
            prev_key, prev_sha = skey(sha), sha
        w.product["transform"].update(fromKey=prev_key, fromSha256=prev_sha)
        why = promote.drop_chain_origin(w.product, w.fetch)[2]
        self.assertIn("أطولُ", why)

    def test_depth_exactly_max_ok(self):
        w = World()
        prev_key, prev_sha = LIVE_KEY, w.live_sha
        for i in range(promote.CHAIN_MAX_DEPTH - 1):
            link = index(hdr(f"ctc_splice:heard:{i}", prev_key, prev_sha))
            b, sha = blob(link)
            w.store[skey(sha)] = b
            prev_key, prev_sha = skey(sha), sha
        w.product["transform"].update(fromKey=prev_key, fromSha256=prev_sha)
        self.assertIsNone(promote.drop_chain_origin(w.product, w.fetch)[2])

    def test_other_riwaya_link(self):
        w = World()
        w.l1["riwaya"] = "hafs"
        b, sha = blob(w.l1)
        w.store[skey(sha)] = b
        w.l2["transform"].update(fromKey=skey(sha), fromSha256=sha)
        b2, sha2 = blob(w.l2)
        w.store[skey(sha2)] = b2
        w.product["transform"].update(fromKey=skey(sha2), fromSha256=sha2)
        self.assertIn("قارئٍ أو روايةٍ أخرى", w.gate())

    def test_foreign_prefix_refused(self):
        w = World()
        w.product["transform"]["fromKey"] = f"state/{RIW}/{RID}.jz"
        self.assertIn("ليس حيَّ", w.gate())

    def test_lost_published_entry_still_refused(self):
        w = World()
        w.product = dict(w.product, entries=w.product["entries"][1:])
        w.product["missing"] = {"count": 6236 - len(w.product["entries"])}
        self.assertIsNotNone(w.gate())

    def test_fetch_none_refused(self):
        w = World()
        self.assertIn("لا جالبَ", promote.drop_chain_origin(w.product, None)[2])


if __name__ == "__main__":
    unittest.main()
