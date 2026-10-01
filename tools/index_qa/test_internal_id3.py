import unittest
from mp3_metadata import strip_internal_id3


def frame(payload=b''):
    return b'\xff\xfb\x90\x00' + payload + bytes(413 - len(payload))


def tag(payload=b'album', version=3, footer=False):
    n = len(payload)
    h = b'ID3' + bytes([version, 0, 16 if footer else 0, (n >> 21) & 127, (n >> 14) & 127, (n >> 7) & 127, n & 127])
    return h + payload + (b'3DI' + h[3:] if footer else b'')


class InternalMetadata(unittest.TestCase):
    def test_removes_only_complete_metadata_between_complete_frames(self):
        a, b, c = frame(b'a'), frame(b'b'), frame(b'c')
        self.assertEqual(strip_internal_id3(a + b + tag() + c), a + b + c)

    def test_preserves_id3_bytes_inside_audio_payload(self):
        d = frame(b'ID3' + bytes([3, 0, 0, 0, 0, 0, 0])) * 3
        self.assertEqual(strip_internal_id3(d), d)

    def test_rejects_truncated_frame_and_unrecognized_junk_without_partial_cleanup(self):
        for tail in [frame()[:-1], b'broken' + frame(), b'junk']:
            d = frame() * 2 + tag() + tail
            self.assertEqual(strip_internal_id3(d), d)

    def test_rejects_invalid_tag_length_and_truncated_tag(self):
        for t in [b'ID3\x03\x00\x00\xff\x00\x00\x05', tag()[:-1]]:
            d = frame() * 2 + t + frame()
            self.assertEqual(strip_internal_id3(d), d)

    def test_accepts_valid_footer_and_rejects_forged_footer(self):
        prefix = frame() * 2
        self.assertEqual(strip_internal_id3(prefix + tag(version=4, footer=True) + frame()), prefix + frame())
        d = prefix + tag(version=4, footer=True)[:-1] + b'x' + frame()
        self.assertEqual(strip_internal_id3(d), d)

    def test_preserves_final_id3v1_and_supports_multiple_internal_tags(self):
        suffix = b'TAG' + bytes(125)
        d = frame() * 2 + tag() + frame() + tag(b'cover') + frame() + suffix
        self.assertEqual(strip_internal_id3(d), frame() * 4 + suffix)

    def test_does_not_treat_initial_or_terminal_tag_as_internal(self):
        for d in [tag() + frame() * 3, frame() * 2 + tag()]:
            self.assertEqual(strip_internal_id3(d), d)


if __name__ == '__main__':
    unittest.main()
