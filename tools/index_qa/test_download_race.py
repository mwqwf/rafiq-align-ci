#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""عقدُ المخبأ: لا يُفكّ ملفٌّ لم يكتمل تنزيلُه — بلا شبكةٍ ولا صوتٍ قرآنيّ.

الشاهدُ المقيس (‏2026-09-28، فخفاخ/قالون · يونس): `_prefetch` والحلقةُ الرئيسة نزّلا
الرابطَ نفسَه إلى المسار نفسِه، فقُبل نصفُ ملفٍّ «مخبّأً» وفُكّ 376.6ث من 2346.3ث،
فسقطت 319 نافذةً «غيرَ حاسمة». وهذه الاختباراتُ تُثبت أنّ ذلك لا يتكرّر.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import run as R  # noqa: E402

URL = "https://example.invalid/folder/010Younes.mp3"
BODY = bytes(range(256)) * 400          # ‏102400 بايت
_SLEEP = time.sleep                      # الحقيقيّ: `R.time.sleep` يُطفأ في الاختبار وهو الوحدةُ نفسُها


class _SlowResp:
    """استجابةٌ تبثّ على دفعاتٍ بطيئة، وتنكسر بعد حدٍّ إن طُلب."""

    def __init__(self, body, chunk=8192, delay=0.01, break_after=None):
        self.body, self.chunk, self.delay, self.break_after = body, chunk, delay, break_after
        self.pos = 0
        self.headers = {"Content-Length": str(len(body))}
        self.status = 200

    def read(self, n=-1):
        if self.break_after is not None and self.pos >= self.break_after:
            raise ConnectionResetError("انقطع النقل في منتصفه")
        _SLEEP(self.delay)
        n = self.chunk if n is None or n < 0 else min(n, self.chunk)
        out = self.body[self.pos:self.pos + n]
        self.pos += len(out)
        return out

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class DownloadRaceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = Path(self.tmp.name)
        self.p_cache = mock.patch.object(R, "LOCAL_CACHE", self.cache)
        self.p_cache.start()
        R._MIRROR_DECIDED[URL] = None                    # لا دلوَ ولا مرآة
        self.p_sleep = mock.patch.object(R.time, "sleep", lambda s: None)
        self.p_sleep.start()

    def tearDown(self):
        self.p_sleep.stop()
        self.p_cache.stop()
        R._MIRROR_DECIDED.pop(URL, None)
        self.tmp.cleanup()

    def _final(self):
        return next(iter(self.cache.glob("*.mp3")), None)

    def test_concurrent_caller_never_sees_a_half_file(self):
        calls = []

        def fake_urlopen(rq, timeout=None):
            calls.append(1)
            return _SlowResp(BODY)

        got_at_return = []
        results = []
        with mock.patch.object(urllib.request, "urlopen", side_effect=fake_urlopen):
            t1 = threading.Thread(target=lambda: results.append(R._local_audio(URL)))
            t1.start()
            # ‏ننتظر حتى يكون النقلُ في منتصفه (‏≥10ك.ب كُتبت في أيّ مسار)
            for _ in range(2000):
                if any(f.stat().st_size >= 10_000 for f in self.cache.iterdir()):
                    break
                _SLEEP(0.001)
            f = self._final()
            self.assertTrue(f is None or f.stat().st_size == len(BODY),
                            "المسارُ النهائيّ ظهر قبل اكتمال التنزيل")
            # ‏المستدعي الثاني (‏الحلقةُ الرئيسة) يجب أن ينتظر لا أن يقرأ النصف:
            #    ما يُعاد إليه يُقرأ **لحظةَ عودته** لا بعد انتهاء الخيط الأوّل.
            r2 = R._local_audio(URL)
            got_at_return.append(len(Path(r2).read_bytes()))
            results.append(r2)
            t1.join()
        self.assertEqual(got_at_return, [len(BODY)], "أُعيد نصفُ ملفٍّ على أنّه مخبّأ")
        self.assertEqual(len(results), 2)
        for r in results:
            self.assertEqual(Path(r).read_bytes(), BODY)
        self.assertEqual(len(calls), 1, "نُزّل الرابطُ مرّتين معاً")
        self.assertEqual(list(self.cache.glob("*.part")), [])

    def test_mid_stream_failure_leaves_nothing_cacheable(self):
        # ‏كان النصفُ يبقى في المسار النهائيّ بعد الاستثناء، فيُقبل «مخبّأً» في النداء التالي
        with mock.patch.object(urllib.request, "urlopen",
                               side_effect=lambda rq, timeout=None: _SlowResp(
                                   BODY, delay=0, break_after=40000)):
            with self.assertRaisesRegex(RuntimeError, "تعذّر تنزيل"):
                R._local_audio(URL)
        self.assertIsNone(self._final())
        self.assertEqual(list(self.cache.glob("*.part")), [])

    def test_short_body_against_declared_length_is_rejected(self):
        class _Short(_SlowResp):
            def __init__(self):
                super().__init__(BODY[:50000], delay=0)
                self.headers = {"Content-Length": str(len(BODY))}
        with mock.patch.object(urllib.request, "urlopen",
                               side_effect=lambda rq, timeout=None: _Short()):
            with self.assertRaisesRegex(RuntimeError, "مبتور"):
                R._local_audio(URL)
        self.assertIsNone(self._final())


class DecodeWhileWritingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.mp3 = Path(self.tmp.name) / "growing.mp3"
        self.mp3.write_bytes(b"\0" * 4096)

    def tearDown(self):
        R._DECODED.pop(str(self.mp3), None)
        self.tmp.cleanup()

    def test_file_that_grows_under_the_decoder_is_rejected(self):
        # ‏الفكُّ وعدُّ الإطارات يتّفقان على نصف الملفّ — فالاتّفاقُ وحده لا يكفي
        def fake_run(cmd, stdout=None, **kw):
            stdout.write(np.ones(16000, dtype="<f4").tobytes())
            with open(self.mp3, "ab") as f:
                f.write(b"\0" * 4096)                    # كاتبٌ آخرُ ما زال ينزّل
            os.utime(self.mp3, ns=(time.time_ns(), time.time_ns() + 10**9))
            return subprocess.CompletedProcess(cmd, 0, stdout=None, stderr=b"")
        with mock.patch.object(R.subprocess, "run", side_effect=fake_run), \
                mock.patch.object(R, "_file_duration_ms", return_value=1000.0):
            with self.assertRaisesRegex(RuntimeError, "تغيّر أثناء الفكّ"):
                R._exact_window_pcm(self.mp3, 0, 500)
        self.assertFalse(Path(str(self.mp3) + ".16k.f32").exists())
        self.assertFalse(Path(str(self.mp3) + ".16k.f32.part").exists())
        self.assertNotIn(str(self.mp3), R._DECODED)


if __name__ == "__main__":
    unittest.main()
