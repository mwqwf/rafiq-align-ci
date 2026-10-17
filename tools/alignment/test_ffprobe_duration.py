# -*- coding: utf-8 -*-
"""اختبار مدّة الملفّ من الحزم (e5 · 2026-10-17): لا تقلّ عن الترويسة وتقارب الصوت الحقيقيّ."""
import os, subprocess, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402


class PacketDurationTest(unittest.TestCase):
    def test_mp3_duration_close_to_real_and_not_below_header(self):
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, "t.mp3")
            subprocess.run([common.FFMPEG, "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=12",
                            "-c:a", "libmp3lame", "-b:a", "64k", f], check=True)
            ms = common.ffprobe_duration_ms(f)
            hdr = int(float(subprocess.run([common.FFPROBE, "-v", "error", "-show_entries", "format=duration",
                                            "-of", "default=nw=1:nk=1", f], capture_output=True, text=True).stdout) * 1000)
            self.assertGreaterEqual(ms, hdr)
            self.assertLess(abs(ms - 12000), 120)

    def test_missing_file_packet_helper_returns_none(self):
        self.assertIsNone(common._packet_duration_ms("/nonexistent.mp3"))


if __name__ == "__main__":
    unittest.main()
