#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""سقفُ التنزيل الكلّيّ في `run._local_audio` (مقيسٌ 2026-09-29).

مهلةُ `urlopen(timeout=90)` تسري على كلّ قراءةٍ لا على التنزيل كلّه، فبثٌّ بطيءٌ
لا ينقطع أبداً — وعلّقت به ملوحُ فخفاخ ساعتين حتى أُلغيت. هذا الاختبار يثبت:
  ① التنزيلُ السريعُ يُقبل كاملاً كما كان؛
  ② البطيءُ يتجاوز السقفَ فيُردّ بخطأ ولا يُقبل مبتوراً؛
  ③ ولا يبقى في المخبأ ملفٌّ جزئيّ.
"""
import http.server
import os
import sys
import tempfile
import threading
import time
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

BODY = b"x" * 200_000


class _H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Length", str(len(BODY)))
        self.end_headers()
        try:
            if self.path.startswith("/slow"):
                for i in range(0, len(BODY), 1000):
                    self.wfile.write(BODY[i:i + 1000])
                    self.wfile.flush()
                    time.sleep(0.05)
            else:
                self.wfile.write(BODY)
        except (BrokenPipeError, ConnectionResetError):
            pass


class DownloadDeadlineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _H)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        os.environ["QA_DL_DEADLINE_S"] = "2"
        import run
        cls.rq = run
        run.LOCAL_CACHE = Path(tempfile.mkdtemp())
        run._mirror_url = lambda u: None
        # لا انتظارَ بين المحاولات — دون مسّ `time.sleep` الذي يستعمله الخادم.
        run.time = types.SimpleNamespace(sleep=lambda s: None,
                                         monotonic=time.monotonic, time=time.time)

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        os.environ.pop("QA_DL_DEADLINE_S", None)

    def test_fast_download_accepted_whole(self):
        p = self.rq._local_audio(f"http://127.0.0.1:{self.port}/fast/001.mp3")
        self.assertEqual(os.path.getsize(p), len(BODY))

    def test_slow_stream_rejected_not_truncated(self):
        with self.assertRaises(RuntimeError) as cm:
            self.rq._local_audio(f"http://127.0.0.1:{self.port}/slow/002.mp3")
        self.assertIn("تجاوز التنزيلُ", str(cm.exception))
        self.assertEqual(list(self.rq.LOCAL_CACHE.glob("*.part")), [])
        self.assertEqual([p for p in self.rq.LOCAL_CACHE.glob("*.mp3")
                          if p.stat().st_size != len(BODY)], [])


if __name__ == "__main__":
    unittest.main()
