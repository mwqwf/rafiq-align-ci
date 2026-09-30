"""حارسا الفكّ في `run.py` (‏2026-09-30): نزعُ وسم ID3v2 · وحشوُ ما بعد نهاية الملفّ.

    python -m unittest tools/index_qa/test_decode_guards.py

يُختبر بطرفيه: ما يجب قبولُه يُقبل، **وما كان يُردّ لعلّةٍ حقيقيّةٍ يبقى مردوداً**.
"""
from __future__ import annotations

import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run                                                       # noqa: E402

AUDIO = b"\xff\xfb\x90\x64" + b"\x00" * 400          # رأسُ إطار MPEG ثمّ حشو


def _id3(payload, footer=False):
    n = len(payload)
    size = bytes([(n >> 21) & 0x7f, (n >> 14) & 0x7f, (n >> 7) & 0x7f, n & 0x7f])
    return b"ID3\x03\x00" + (b"\x10" if footer else b"\x00") + size + payload + (b"3DI" + b"\x00" * 7 if footer else b"")


class StripId3(unittest.TestCase):
    def test_strips_tag_with_corrupt_cover(self):
        apic = b"APIC" + struct.pack(">I", 30) + b"\x00\x00" + b"\x00image/png\x00\x03\x00" + b"\x89PNG" + b"\x7f" * 10
        self.assertEqual(run._strip_id3v2(_id3(apic) + AUDIO), AUDIO)

    def test_footer_flag_skips_footer(self):
        self.assertEqual(run._strip_id3v2(_id3(b"x" * 20, footer=True) + AUDIO), AUDIO)

    def test_no_tag_unchanged(self):
        self.assertEqual(run._strip_id3v2(AUDIO), AUDIO)

    def test_bad_syncsafe_size_not_stripped(self):
        bad = b"ID3\x03\x00\x00\x80\x00\x00\x00" + AUDIO   # حجمٌ غيرُ آمنِ المزامنة ⇒ لا يُلمس
        self.assertEqual(run._strip_id3v2(bad), bad)

    def test_audio_input_writes_stripped_copy(self):
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "a.mp3")
            Path(p).write_bytes(_id3(b"y" * 50) + AUDIO)
            q = run._audio_input(p)
            self.assertNotEqual(q, p)
            self.assertEqual(Path(q).read_bytes(), AUDIO)
            self.assertEqual(Path(p).read_bytes()[:3], b"ID3")      # الأصلُ لا يُمسّ
            p2 = os.path.join(t, "b.mp3")
            Path(p2).write_bytes(AUDIO)
            self.assertEqual(run._audio_input(p2), p2)


class EofPad(unittest.TestCase):
    TOL = 80.0

    def ok(self, start, dur, got_end, fd, ayah_end, file_end):
        return run._eof_pad_ok(start, dur, got_end, fd, self.TOL, ayah_end, file_end)

    def test_last_entry_inside_file_padded(self):              # الشرطُ القديمُ نفسُه
        self.assertTrue(self.ok(49050, 8000, 53869, 53869, 53800, 53800))

    def test_last_entry_past_frame_count_refused(self):        # a_alhazmi 93:11: +47م.ث — لا سماح
        self.assertFalse(self.ok(49050, 5000, 53869, 53869, 53916, 53916))

    def test_non_last_refused_when_last_entry_overruns_by_little(self):
        self.assertFalse(self.ok(33000, 8000, 38165, 38165, 34000, 38200))

    def test_non_last_ayah_of_intact_file_padded(self):        # kyat 93:10
        self.assertTrue(self.ok(33000, 8000, 38165, 38165, 34000, 38100))

    def test_truncated_file_last_entry_beyond_refused(self):   # الفهرسُ يدّعي صوتاً بعد النهاية
        self.assertFalse(self.ok(33000, 8000, 38165, 38165, 34000, 41000))

    def test_ayah_itself_beyond_file_refused(self):
        self.assertFalse(self.ok(49050, 8000, 53869, 53869, 55000, 55000))

    def test_shortfall_in_middle_refused(self):                # المفكوكُ لم يبلغ نهايةَ الملفّ
        self.assertFalse(self.ok(10000, 8000, 14000, 53869, 12000, 53800))

    def test_window_inside_file_refused(self):                 # لا يتجاوز الطلبُ نهايةَ الملفّ
        self.assertFalse(self.ok(10000, 8000, 17000, 53869, 12000, 53800))

    def test_missing_ends_refused(self):
        self.assertFalse(self.ok(49050, 8000, 53869, 53869, None, 53800))
        self.assertFalse(self.ok(49050, 8000, 53869, 53869, 53800, None))


if __name__ == "__main__":
    unittest.main()
