import pathlib
import subprocess
import sys
import tempfile
import unittest
import wave

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from channel_mix import cancellation_evidence, mono_filter, mono_pcm
from common import to_wav16k


class ChannelMixTest(unittest.TestCase):
    def setUp(self):
        t = np.arange(32000) / 16000
        self.voice = (.12 * np.sin(2*np.pi*440*t)).astype('float32')

    def test_opposing_stereo_preserves_original_channel_exactly(self):
        stereo = np.column_stack([self.voice, -self.voice])
        self.assertEqual(cancellation_evidence(stereo)['selectedChannel'], 0)
        np.testing.assert_array_equal(mono_pcm(stereo), self.voice)

    def test_regular_stereo_and_mono_keep_original_downmix(self):
        stereo = np.column_stack([self.voice, self.voice*.5])
        self.assertIsNone(cancellation_evidence(stereo))
        np.testing.assert_array_equal(mono_pcm(stereo), stereo.mean(axis=1))
        np.testing.assert_array_equal(mono_pcm(self.voice), self.voice)

    def test_quiet_noise_and_dissimilar_channels_do_not_select_channel(self):
        noise = np.random.default_rng(25).normal(0,.1,len(self.voice)).astype('float32')
        for x in [np.column_stack([self.voice,noise]),np.column_stack([self.voice, -self.voice*.4]), np.column_stack([self.voice*1e-4,-self.voice*1e-4])]:
            self.assertIsNone(cancellation_evidence(x))

    def test_invalid_samples_never_establish_cancellation(self):
        x=np.column_stack([self.voice,-self.voice]); x[0,0]=np.nan
        self.assertIsNone(cancellation_evidence(x))

    def test_real_codec_keeps_duration_and_recovers_signal_with_no_sample_shift(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=pathlib.Path(tmp)/'stereo.wav'
            with wave.open(str(p),'wb') as w:
                w.setnchannels(2);w.setsampwidth(2);w.setframerate(16000)
                w.writeframes((np.column_stack([self.voice,-self.voice])*32767).astype('<i2').tobytes())
            self.assertEqual(mono_filter(str(p)),['-af','pan=mono|c0=c0'])
            # Simulate the old cached WAV which cancelled the real speech.
            cached=pathlib.Path(str(p)+'.16k.wav')
            subprocess.run(['ffmpeg','-v','error','-i',str(p),'-ac','1','-y',str(cached)],check=True)
            out=to_wav16k(str(p))
            with wave.open(out) as w:
                recovered=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2')
            np.testing.assert_array_equal(recovered,(self.voice*32767).astype('<i2'))
            self.assertEqual(len(recovered),32000)
            stamp=cached.stat().st_mtime_ns
            to_wav16k(str(p));self.assertEqual(cached.stat().st_mtime_ns,stamp)

    def test_changed_source_invalidates_channel_probe(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=pathlib.Path(tmp)/'stereo.wav'
            def write(sign):
                with wave.open(str(p),'wb') as w:
                    w.setnchannels(2);w.setsampwidth(2);w.setframerate(16000)
                    w.writeframes((np.column_stack([self.voice,self.voice*sign])*32767).astype('<i2').tobytes())
            write(-1);self.assertTrue(mono_filter(str(p)))
            write(1);self.assertEqual(mono_filter(str(p)),[])

if __name__=='__main__':
    unittest.main()
