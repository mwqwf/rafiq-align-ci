import struct
import unittest
from unittest import mock
from tools.index_qa import final_verse_free_batch as B


class TailWindowTests(unittest.TestCase):
    def test_native_stereo_tail_and_eof_clamp_preserve_all_frames(self):
        with mock.patch.object(B.S,'RATE',1):
            c=B.NativeWindow(2,90,105)
            raw=b''.join(struct.pack('<hh',i,-i) for i in range(101))
            for offset in range(0,len(raw),7):c.feed(raw[offset:offset+7])
            proof=c.finish()
            self.assertEqual(proof['windowEndSampleExclusive'],101)
            self.assertTrue(proof['requestedEndClampedToDecodedEof'])
            self.assertEqual(struct.unpack('<11h',c.channels()['native-1']),tuple(range(90,101)))
            self.assertEqual(struct.unpack('<11h',c.channels()['native-2']),tuple(-i for i in range(90,101)))
            self.assertEqual(len(c.window),44)

    def test_mono_window_is_not_duplicated_and_middle_does_not_grow_buffer(self):
        with mock.patch.object(B.S,'RATE',1):
            c=B.NativeWindow(1,90,100)
            c.feed(struct.pack('<110h',*range(110)))
            self.assertEqual(c.finish()['frames'],110)
            self.assertEqual(list(c.channels()),['native-1'])
            self.assertEqual(struct.unpack('<10h',c.channels()['native-1']),tuple(range(90,100)))
            self.assertEqual(len(c.window),20)

    def test_missing_tail_and_partial_frame_are_refused(self):
        with mock.patch.object(B.S,'RATE',1):
            for n in (0,178,179,183):
                c=B.NativeWindow(1,90,100);c.feed(b'\0'*n)
                with self.assertRaises(B.S.metadata.ProbeError):c.finish()
            with self.assertRaises(B.S.metadata.ProbeError):B.NativeWindow(1,0,71)
            with self.assertRaises(B.S.metadata.ProbeError):B.NativeWindow(3,90,100)

    def test_fractional_eof_uses_integer_sample_count_without_floor_loss(self):
        class Backend:
            def infer(self,raw):return {'text':'synthetic audio only'}
        source={'surah':4,'sha256':'a'*64,'windowSeconds':[3814,3871.817125]}
        count=round((source['windowSeconds'][1]-source['windowSeconds'][0])*B.S.RATE)
        result=B.S.measure_window(Backend(),b'\0'*(count*2),source,'native-1','test')
        self.assertEqual(result['windowSamplesCovered'],count)
        source['windowSeconds'][1]+=.00001
        with self.assertRaises(B.S.metadata.ProbeError):
            B.S.measure_window(Backend(),b'\0'*(count*2),source,'native-1','test')

    def test_all_groups_bind_to_exact_existing_candidates(self):
        groups=[B.load_plan(i) for i in range(3)]
        self.assertEqual([len(g) for g in groups],[6,6,4])
        self.assertEqual(len({r['id'] for g in groups for r in g}),16)


if __name__=='__main__':unittest.main()
