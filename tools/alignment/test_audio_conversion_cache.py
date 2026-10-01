"""يكشف استعمال WAV قديم بعد استبدال صوت المصدر تحت الاسم نفسه."""
import os
import struct
import sys
import tempfile
import unittest
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import to_wav16k


class AudioConversionCacheTest(unittest.TestCase):
    def test_changed_source_refreshes_conversion_but_unchanged_source_reuses_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.wav"
            def write(seconds):
                with wave.open(str(source), "wb") as w:
                    w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
                    w.writeframes(struct.pack('<h', 1000) * (16000 * seconds))
            write(1)
            converted = Path(to_wav16k(str(source)))
            stamp = converted.stat().st_mtime_ns
            self.assertEqual(to_wav16k(str(source)), str(converted))
            self.assertEqual(converted.stat().st_mtime_ns, stamp)
            write(2)
            # نجعل ترتيب الزمن قطعياً دون انتظار أو اعتماد على دقة نظام الملفات.
            old = source.stat().st_mtime_ns - 1_000_000_000
            os.utime(converted, ns=(old, old))
            to_wav16k(str(source))
            with wave.open(str(converted)) as w:
                self.assertEqual(w.getnframes(), 32000)
