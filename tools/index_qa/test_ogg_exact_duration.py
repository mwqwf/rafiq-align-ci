"""Real Vorbis sample counts and strict rejection of damaged original pages."""
import pathlib
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import oggdur
import run as R


@unittest.skipUnless(shutil.which('ffmpeg'), 'ffmpeg unavailable')
class ExactVorbisDurationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = pathlib.Path(cls.tmp.name)
        cls.original = cls.root / 'real.ogg'
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                        'sine=frequency=700:sample_rate=44100:duration=2',
                        '-c:a', 'libvorbis', str(cls.original)], check=True)
        cls.raw = cls.original.read_bytes()

    @classmethod
    def tearDownClass(cls):
        R._DECODED.clear()
        cls.tmp.cleanup()

    def write(self, raw):
        path = self.root / (self.id().split('.')[-1] + '.mp3')
        path.write_bytes(raw)
        return path

    def mutate_page(self, page_number, mutation):
        body = bytearray(self.raw)
        pos = 0
        for _ in range(page_number):
            count = body[pos + 26]
            pos += 27 + count + sum(body[pos + 27:pos + 27 + count])
        count = body[pos + 26]
        end = pos + 27 + count + sum(body[pos + 27:pos + 27 + count])
        page = bytearray(body[pos:end])
        mutation(page)
        page[22:26] = bytes(4)
        page[22:26] = struct.pack('<I', oggdur.checksum(page))
        body[pos:end] = page
        return bytes(body)

    def test_exact_eos_sample_count_matches_full_decoder_and_ignores_extension(self):
        path = self.write(self.raw)
        self.assertAlmostEqual(oggdur.duration_ms(path), 2000, places=6)
        self.assertAlmostEqual(R._file_duration_ms(path), 2000, places=6)
        whole = R._full_decode_pcm(path)
        self.assertEqual(len(whole), 32000)
        actual, rate = R._exact_window_pcm(path, 1200, 1600)
        self.assertEqual(rate, 16000)
        np.testing.assert_array_equal(actual, whole[19200:25600])

    def test_corrupted_payload_is_rejected_even_with_existing_eos(self):
        bad = bytearray(self.raw)
        bad[-4] ^= 1
        with self.assertRaisesRegex(ValueError, 'checksum'):
            oggdur.duration_ms(self.write(bad))

    def test_truncation_and_missing_eos_are_rejected(self):
        for raw in (self.raw[:-1], self.raw[:10]):
            with self.assertRaises(ValueError):
                oggdur.duration_ms(self.write(raw))
        raw = self.mutate_page(0, lambda p: p.__setitem__(slice(18, 22), struct.pack('<I', 1)))
        with self.assertRaisesRegex(ValueError, 'missing page'):
            oggdur.duration_ms(self.write(raw))

    def test_another_serial_or_broken_continuation_is_rejected_with_valid_crc(self):
        for offset, value in ((14, 123456),):
            raw = self.mutate_page(1, lambda p: p.__setitem__(slice(offset, offset + 4), struct.pack('<I', value)))
            with self.assertRaisesRegex(ValueError, 'streams'):
                oggdur.duration_ms(self.write(raw))
        raw = self.mutate_page(1, lambda p: p.__setitem__(5, p[5] | 1))
        with self.assertRaisesRegex(ValueError, 'continuation'):
            oggdur.duration_ms(self.write(raw))

    def test_chained_stream_or_trailing_bytes_are_rejected(self):
        for raw in (self.raw + self.raw, self.raw + b'x'):
            with self.assertRaisesRegex(ValueError, 'EOS'):
                oggdur.duration_ms(self.write(raw))

    def test_ordinary_mp3_counter_path_is_preserved(self):
        path = self.write(b'ID3' + bytes(97))
        with mock.patch('mp3dur.dur', return_value=(1.25, 0)) as frame_counter:
            self.assertEqual(R._file_duration_ms(path), 1250)
            frame_counter.assert_called_once_with(str(path))


if __name__ == '__main__':
    unittest.main()
