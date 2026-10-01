import pathlib
import sys
import tempfile
import unittest
import wave

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from basmala_local import cut


class OpenerChannelDecodeTest(unittest.TestCase):
    def test_cancelled_stereo_uses_original_channel_and_exact_requested_samples(self):
        with tempfile.TemporaryDirectory() as t:
            p=pathlib.Path(t);n=np.arange(32000)
            voice=(np.sin(2*np.pi*(440*n/16000+.000007*n*n))*5000).astype('<i2')
            src=p/'source.wav'
            with wave.open(str(src),'wb') as w:
                w.setnchannels(2);w.setsampwidth(2);w.setframerate(16000)
                w.writeframes(np.column_stack([voice,-voice]).astype('<i2').tobytes())
            out=cut(str(src),250,1000,str(p/'clip.wav'))
            with wave.open(out) as w:
                got=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2')
            np.testing.assert_array_equal(got,voice[4000:20000])

    def test_ordinary_mono_keeps_its_waveform_and_duration(self):
        with tempfile.TemporaryDirectory() as t:
            p=pathlib.Path(t);voice=(np.sin(np.arange(32000)*.1)*4000).astype('<i2');src=p/'source.wav'
            with wave.open(str(src),'wb') as w:
                w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(voice.tobytes())
            out=cut(str(src),500,1000,str(p/'clip.wav'))
            with wave.open(out) as w:got=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2')
            np.testing.assert_array_equal(got,voice[8000:24000])

if __name__=='__main__':unittest.main()
