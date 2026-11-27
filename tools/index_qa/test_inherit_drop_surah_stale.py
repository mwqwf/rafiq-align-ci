#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""توريثُ إسقاط السور لا يحمّل إعلاناً بالياً لسورة استُرجعت ولها مداخل (‏akri e9930f75 س10).

الحارسُ `declared_absent` يبقى يردّ الأصل المتناقض؛ التوريث يشتقّ الإعلان من نسخة
نُزع منها ما استُرجع (`without_stale_drop`) ثم يمرّر الحارس على النسخة المنظّفة.
"""
import io
from contextlib import redirect_stdout
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import declarations                                                   # noqa: E402
import stage_transform as st                                          # noqa: E402


def stale_parent(*, with_10=True):
    """أصلٌ كالعكري بعد استرجاع س10: op يسمّي 10 و26 و37، وس10 لها مداخل."""
    entries = [{"ayahId": f"10:{i}", "startMs": i, "endMs": i + 1} for i in range(1, 5)]
    entries += [{"ayahId": f"56:{i}", "startMs": 1000 + i, "endMs": 1001 + i} for i in range(1, 4)]
    drops = "10,26,37" if with_10 else "26,37"
    decls = {
        "26": {"op": "drop_surah", "reasonCode": "SOURCE_TRUNCATED", "reasonUser": "س"},
        "37": {"op": "drop_surah", "reasonCode": "OTHER", "reasonUser": "س"},
    }
    if with_10:
        decls["10"] = {"op": "drop_surah", "reasonCode": "OTHER", "reasonUser": "س"}
    return {
        "riwaya": "qalun",
        "reciterId": "akri_qalun",
        "entries": entries,
        "transform": {
            "op": f"drop_surah:{drops}|declare_gap:4,24",
            "dropSurah": [37],
            "reasonCode": "SOURCE_TRUNCATED",
            "reasonUser": "س",
            "declarations": decls,
        },
    }


def product(parent):
    return {"entries": list(parent["entries"]), "transform": {"op": "ctc_splice:56"}}


class StaleDropNotCarried(unittest.TestCase):
    def test_guard_still_refuses_inconsistent_parent(self):
        """الحارس نفسه لا يُرخى: الأصل المتناقض يُردّ إن قُرئ مباشرة."""
        with self.assertRaises(SystemExit) as e:
            declarations.declared_absent(stale_parent())
        self.assertIn("لها مداخل في الأصل", str(e.exception))
        self.assertIn("10", str(e.exception))

    def test_inherit_strips_restored_and_carries_remaining(self):
        pidx = stale_parent()
        out = product(pidx)
        buf = io.StringIO()
        with redirect_stdout(buf):
            st.inherit_drop_surah(pidx, out)
        tr = out["transform"]
        self.assertEqual(tr["dropSurah"], [26, 37])
        self.assertNotIn("10", tr.get("declarations") or {})
        self.assertEqual(set((tr.get("declarations") or {})), {"26", "37"})
        self.assertIn("10", buf.getvalue())
        # الأصل لم يُمسّ
        self.assertIn("10", pidx["transform"]["op"])
        self.assertIn("10", pidx["transform"]["declarations"])

    def test_consistent_parent_unchanged_path(self):
        pidx = stale_parent(with_10=False)
        out = product(pidx)
        st.inherit_drop_surah(pidx, out)
        self.assertEqual(out["transform"]["dropSurah"], [26, 37])
        self.assertEqual(set(out["transform"]["declarations"]), {"26", "37"})

    def test_all_named_drops_restored_carries_nothing(self):
        pidx = stale_parent()
        pidx["transform"]["op"] = "drop_surah:10|declare_gap:4,24"
        pidx["transform"]["dropSurah"] = [10]
        pidx["transform"]["declarations"] = {
            "10": {"op": "drop_surah", "reasonCode": "OTHER", "reasonUser": "س"},
        }
        out = product(pidx)
        st.inherit_drop_surah(pidx, out)
        self.assertNotIn("dropSurah", out["transform"])
        self.assertNotIn("10", out["transform"].get("declarations") or {})


if __name__ == "__main__":
    unittest.main()
