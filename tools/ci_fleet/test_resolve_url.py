#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ترميز اسم الملف في resolve_url — بلا شبكة ولا دلو.

    python -m unittest tools.ci_fleet.test_resolve_url
"""
from __future__ import annotations

import unittest
from urllib.parse import quote

from tools.ci_fleet.resolve_url import href_filename, resolve_surah_url

# شاهد التشغيلة الفاشلة 45069139294: الاسم في الجدول كان مرمّزاً سلفاً.
SHAYKHNA_29_ENCODED = "029%20%D8%A7%D9%84%D8%B9%D9%86%D9%83%D8%A8%D9%88%D8%AA.mp3"
SHAYKHNA_29_RAW = "029 العنكبوت.mp3"
FOLDER = "https://archive.org/download/4666666666666666666666666694696496433_gmail_002"
BROKEN = FOLDER + "/" + quote(SHAYKHNA_29_ENCODED)  # الترميز المزدوج الذي أسقط التنزيل


class HrefFilenameTest(unittest.TestCase):
    def test_raw_arabic_name_is_quoted_once(self):
        got = href_filename(SHAYKHNA_29_RAW)
        self.assertEqual(got, quote(SHAYKHNA_29_RAW, safe=""))
        self.assertIn("%20", got)
        self.assertNotIn("%25", got)

    def test_already_encoded_name_is_not_double_quoted(self):
        got = href_filename(SHAYKHNA_29_ENCODED)
        self.assertEqual(got, SHAYKHNA_29_ENCODED)
        self.assertNotIn("%25", got)
        self.assertNotEqual(got, quote(SHAYKHNA_29_ENCODED))
        self.assertIn("%2520", quote(SHAYKHNA_29_ENCODED))  # شاهد العطب القديم

    def test_space_only_ascii_name(self):
        self.assertEqual(href_filename("ar_007_Mustapha Gharbi_Warsh.mp3"),
                         "ar_007_Mustapha%20Gharbi_Warsh.mp3")
        self.assertEqual(href_filename("ar_007_Mustapha%20Gharbi_Warsh.mp3"),
                         "ar_007_Mustapha%20Gharbi_Warsh.mp3")


class ResolveSurahUrlTest(unittest.TestCase):
    def test_numeric_template_unchanged(self):
        tpl = "https://server11.mp3quran.net/hatem/{s:03d}.mp3"
        self.assertEqual(resolve_surah_url(tpl, 57),
                         "https://server11.mp3quran.net/hatem/057.mp3")

    def test_folder_plus_preencoded_catalog_name(self):
        url = resolve_surah_url(FOLDER, 29, {29: SHAYKHNA_29_ENCODED})
        self.assertEqual(url, FOLDER + "/" + SHAYKHNA_29_ENCODED)
        self.assertNotEqual(url, BROKEN)

    def test_folder_plus_raw_catalog_name(self):
        url = resolve_surah_url(FOLDER, 29, {29: SHAYKHNA_29_RAW})
        self.assertEqual(url, FOLDER + "/" + href_filename(SHAYKHNA_29_RAW))

    def test_missing_name_is_a_loud_stop(self):
        with self.assertRaises(SystemExit) as ctx:
            resolve_surah_url(FOLDER, 29, {1: "001.mp3"})
        self.assertIn("لا اسمَ لسورة 29", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
