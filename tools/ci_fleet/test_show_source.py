#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يختبر `show_source` — طباعةَ مصدر القارئ من الكتالوج، بكتالوجٍ وهميٍّ في الذاكرة.

    python -m unittest tools.ci_fleet.test_show_source

⛔ **لماذا كُتب (2026-09-25):** كانت الأداةُ تطبع `{base}{s:03d}.mp3` حتى لقارئِ
مجلّدٍ أسماؤه في جدول `files` (‏`warsh/gharbi_warsh`) ⇒ 404 وحكمٌ كاذبٌ بموت
المصدر. ⚖️ بلا شبكةٍ ولا دلو.
"""
from __future__ import annotations

import unittest

from tools.ci_fleet import show_source as ss

FOLDER = ("https://archive.org/download/128----kb-mustufa--gharby---by--warsh-mp3"
          "--full--mushaf--quran--114--sora---fr")
CAT = {"riwayat": [
    {"id": "warsh", "reciters": [
        {"id": "gharbi_warsh", "base": FOLDER,
         "files": [f"ar_{i:03d}_Mustapha_Gharbi_Warsh.mp3" for i in range(1, 115)]},
        {"id": "plain_warsh", "base": "https://example.org/plain/"},
    ]},
]}
BASES = {("warsh", "gharbi_warsh"): FOLDER,
         ("warsh", "plain_warsh"): "https://example.org/plain/"}


class ShowSourceTest(unittest.TestCase):
    def test_file_tables_detected_only_for_files(self):
        self.assertEqual(ss.catalog_file_tables(CAT), {("warsh", "gharbi_warsh")})

    def test_folder_reciter_prints_folder_without_template(self):
        lines, rc = ss.describe("warsh/gharbi_warsh", BASES,
                                ss.catalog_file_tables(CAT))
        self.assertEqual(rc, 0)
        self.assertEqual(lines[0], f"✅ warsh/gharbi_warsh\t{FOLDER}")
        text = "\n".join(lines)
        self.assertNotIn("{s:03d}", text)
        self.assertIn("files", text)
        self.assertIn("realign_surah", text)
        self.assertIn("reciter_id=gharbi_warsh", text)
        self.assertIn("ctc_splice", text)
        self.assertIn("whisper_splice", text)

    def test_template_reciter_unchanged(self):
        lines, rc = ss.describe("warsh/plain_warsh", BASES,
                                ss.catalog_file_tables(CAT))
        self.assertEqual((lines, rc),
                         (["✅ warsh/plain_warsh\thttps://example.org/plain/{s:03d}.mp3"], 0))

    def test_unknown_reciter_refused(self):
        lines, rc = ss.describe("warsh/nobody", BASES, set())
        self.assertEqual(rc, 1)
        self.assertIn("لا مصدرَ", lines[0])


if __name__ == "__main__":
    unittest.main()
