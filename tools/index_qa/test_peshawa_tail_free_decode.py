import struct
import unittest
from unittest import mock
from tools.index_qa import peshawa_tail_free_decode as P


class NativePcmTest(unittest.TestCase):
    def test_stereo_order_and_overlapping_windows_are_preserved(self):
        with mock.patch.object(P.S, 'RATE', 1):
            raw = b''.join(struct.pack('<hh', i, -i) for i in range(285))
            c = P.NativeCollector(2)
            for offset in range(0, len(raw), 13):
                c.feed(raw[offset:offset + 13])
            self.assertEqual(c.finish()['frames'], 285)
            a, b = c.window(188, 248), c.window(244, 284)
            self.assertEqual(struct.unpack('<60h', a['native-1']), tuple(range(188, 248)))
            self.assertEqual(struct.unpack('<60h', a['native-2']), tuple(-i for i in range(188, 248)))
            self.assertEqual(a['native-1'][-8:], b['native-1'][:8])
            self.assertEqual(bytes(c.data), raw)

    def test_mono_is_not_duplicated_or_mixed(self):
        with mock.patch.object(P.S, 'RATE', 1):
            c = P.NativeCollector(1)
            c.feed(struct.pack('<285h', *range(285)))
            self.assertEqual(list(c.window(244, 284)), ['native-1'])
            self.assertEqual(struct.unpack('<40h', c.window(244, 284)['native-1']), tuple(range(244, 284)))

    def test_short_partial_and_excessive_pcm_fail_closed(self):
        with mock.patch.object(P.S, 'RATE', 1):
            for raw in (b'', b'\x00' * 566, b'\x00' * 569):
                c = P.NativeCollector(1)
                c.feed(raw)
                with self.assertRaises(P.S.metadata.ProbeError):
                    c.finish()
            with self.assertRaises(P.S.metadata.ProbeError):
                P.NativeCollector(1).feed(b'\x00' * 602)
        with self.assertRaises(P.S.metadata.ProbeError):
            P.NativeCollector(3)

    def test_unplanned_windows_rejected(self):
        with mock.patch.object(P.S, 'RATE', 1):
            c = P.NativeCollector(1)
            c.feed(b'\x00' * 570)
            with self.assertRaises(P.S.metadata.ProbeError):
                c.window(180, 248)


if __name__ == '__main__':
    unittest.main()
