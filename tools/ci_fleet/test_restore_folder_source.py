#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يختبر حلَّ رابط السورة من جدول `files` في حلقة الاسترجاع — بلا شبكةٍ ولا دلو.

    python -m unittest tools.ci_fleet.test_restore_folder_source

⛔ **لماذا كُتب (2026-09-25):** كان `source_ratio` يقيس `{base}{s:03d}.mp3` حتى
لقارئ مجلّدٍ أسماؤه في جدول `files` (‏`warsh/gharbi_warsh`) ⇒ 404 ⇒ «نسبة=None»
فتُرك 18 آيةً بحكمٍ كاذبٍ بموت المصدر. ويُثبت هنا أيضاً أنّ مَن لا جدولَ له
يبقى سلوكُه حرفاً كما كان.
"""
from __future__ import annotations

import unittest
from unittest import mock

from tools.ci_fleet import restore_loop as loop

FOLDER = ("https://archive.org/download/128----kb-mustufa--gharby---by--warsh-mp3"
          "--full--mushaf--quran--114--sora---fr")
NAMES = [f"ar_{i:03d}_Mustapha Gharbi_Warsh.mp3" for i in range(1, 115)]
CAT = {"riwayat": [
    {"id": "warsh", "reciters": [
        {"id": "gharbi_warsh", "base": FOLDER, "files": NAMES},
        {"id": "short_warsh", "base": "https://example.org/short/", "files": NAMES[:113]},
        {"id": "plain_warsh", "base": "https://example.org/plain/"},
    ]},
]}
D = {s: 100_000 + 10_000 * s for s in range(1, 11)}
TARGET = 7


def sizer(seen: list):
    """دالّةُ حجمٍ معلومةُ الجواب: 1000 بايت/ث، وترفض ما لا يطابق نمطاً معروفاً."""
    def size(url: str) -> int:
        seen.append(url)
        tail = url.rsplit("/", 1)[-1]
        if tail.startswith("ar_"):
            s = int(tail[3:6])
        elif tail[:3].isdigit() and tail.endswith(".mp3"):
            s = int(tail[:3])
        else:
            raise ValueError(f"404: {url}")
        return int(D[s])      # D بالميلي ثانية × 1000 بايت/ث ÷ 1000
    return size


class FileTablesTest(unittest.TestCase):
    def test_tables_only_for_catalog_files_and_114_exactly(self):
        t = loop.file_tables(CAT)
        self.assertEqual(t[("warsh", "gharbi_warsh")][36], NAMES[35])
        self.assertIsNone(t[("warsh", "short_warsh")])
        self.assertNotIn(("warsh", "plain_warsh"), t)

    def test_realign_template(self):
        names = loop.file_tables(CAT)[("warsh", "gharbi_warsh")]
        self.assertEqual(loop.realign_template(FOLDER + "/", names), FOLDER)
        self.assertNotIn("{s", loop.realign_template(FOLDER, names))
        self.assertEqual(loop.realign_template("https://example.org/plain/", None),
                         "https://example.org/plain/{s:03d}.mp3")


class SourceRatioTest(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(loop, "surah_ends", lambda _i: D)
        p.start()
        self.addCleanup(p.stop)

    def test_folder_reciter_resolves_names_from_table(self):
        seen: list = []
        names = loop.file_tables(CAT)[("warsh", "gharbi_warsh")]
        r = loop.source_ratio(object(), FOLDER, TARGET, [dict(D)] * 4, names,
                              size=sizer(seen))
        self.assertAlmostEqual(r, 1.0)
        self.assertTrue(all(u.startswith(FOLDER + "/ar_") for u in seen), seen)
        self.assertIn(FOLDER + "/ar_007_Mustapha%20Gharbi_Warsh.mp3", seen)
        self.assertFalse(any("/007.mp3" in u for u in seen))

    def test_numeric_template_on_folder_would_404(self):
        # الشاهدُ على العطب القديم: بلا جدولٍ يُبنى القالبُ الرقميُّ فيفشل السبر.
        seen: list = []

        def only_names(url):
            if "/ar_" not in url:
                raise ValueError("404")
            return 1
        self.assertIsNone(loop.source_ratio(object(), FOLDER + "/", TARGET,
                                            [dict(D)] * 4, None, size=only_names))

    def test_plain_reciter_unchanged(self):
        seen: list = []
        r = loop.source_ratio(object(), "https://example.org/plain/", TARGET,
                              [dict(D)] * 4, size=sizer(seen))
        self.assertAlmostEqual(r, 1.0)
        self.assertIn("https://example.org/plain/007.mp3", seen)
        self.assertTrue(all(u.startswith("https://example.org/plain/") and
                            u.endswith(".mp3") and u[-7:-4].isdigit() for u in seen))

    def test_default_size_is_head_len(self):
        seen: list = []
        with mock.patch.object(loop, "head_len", sizer(seen)):
            r = loop.source_ratio(object(), "https://example.org/plain/", TARGET,
                                  [dict(D)] * 4)
        self.assertAlmostEqual(r, 1.0)
        self.assertTrue(seen)

    def test_missing_name_is_not_guessed(self):
        names = {s: f"ar_{s:03d}_x.mp3" for s in range(1, 115) if s != TARGET}
        seen: list = []
        self.assertIsNone(loop.source_ratio(object(), FOLDER, TARGET, [dict(D)] * 4,
                                            names, size=sizer(seen)))
        self.assertFalse(any("007" in u for u in seen))


class ScanDispatchTest(unittest.TestCase):
    """ما يُمرَّر إلى `realign_surah.yml`: المجلّدُ ومعه `reciter_id` لقارئ الجدول،
    والقالبُ الرقميُّ حرفاً لغيره."""

    def _scan(self, riw, rid, base, tables):
        row = {"riwaya": riw, "reciter": rid, "surah": 36, "have": 80,
               "expected": 83, "gap": 3, "key": f"timings/{riw}/{rid}.jz",
               "liveKey": f"timings/{riw}/{rid}.jz"}
        calls, ratio_names = [], []
        idx = {"entries": [], "refineVersion": 2}

        def fake_ratio(_idx, _base, _s, _refs, names=None):
            ratio_names.append(names)
            return 1.0
        with mock.patch.object(loop, "catalog_bases", return_value={(riw, rid): base}), \
             mock.patch.object(loop, "catalog_file_tables", return_value=tables), \
             mock.patch.object(loop, "fetch_index", return_value=(idx, None)), \
             mock.patch.object(loop, "surah_ends", return_value={36: 10_000}), \
             mock.patch.object(loop, "inflight_reciters", return_value=set()), \
             mock.patch.object(loop, "candidates", return_value=[row]), \
             mock.patch.object(loop, "blocked_realign", return_value=False), \
             mock.patch.object(loop, "source_ratio", side_effect=fake_ratio), \
             mock.patch.object(loop, "measured_skip", return_value=4990), \
             mock.patch.object(loop, "gh", side_effect=lambda *a: calls.append(a) or "u"), \
             mock.patch.dict(loop.os.environ, {}, clear=False):
            loop.os.environ.pop("GITHUB_REF_NAME", None)
            loop.cmd_scan(unittest.mock.Mock(limit=1))
        return calls, ratio_names

    def test_folder_reciter_gets_folder_and_reciter_id(self):
        tables = loop.file_tables(CAT)
        calls, names = self._scan("warsh", "gharbi_warsh", FOLDER + "/", tables)
        self.assertEqual(names, [tables[("warsh", "gharbi_warsh")]])
        flat = calls[-1]
        self.assertIn(f"url_template={FOLDER}", flat)
        self.assertIn("reciter_id=gharbi_warsh", flat)

    def test_plain_reciter_keeps_numeric_template(self):
        calls, names = self._scan("warsh", "plain_warsh", "https://example.org/plain/",
                                  loop.file_tables(CAT))
        self.assertEqual(names, [None])
        self.assertIn("url_template=https://example.org/plain/{s:03d}.mp3", calls[-1])

    def test_bad_table_is_not_measured_nor_dispatched(self):
        calls, names = self._scan("warsh", "short_warsh", "https://example.org/short/",
                                  loop.file_tables(CAT))
        self.assertEqual((calls, names), ([], []))


if __name__ == "__main__":
    unittest.main()
