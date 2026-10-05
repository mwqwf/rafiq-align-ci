"""ترميمُ الإطارات التالفة القصيرة (‏`mp3_resync` · fixV 2026-10-05 · mhsny/002).

    python -m unittest tools/index_qa/test_mp3_resync.py

يُختبر بطرفيه على ملفٍّ مصنوع (‏ضجيجٌ وردي يُرمَّز MP3 ثمّ تُتلف إطاراتُه):
- **الزمنُ بعد العطب لا ينزاح** (‏ارتباطٌ بالعيّنة مع الأصل السليم ≤ 1م.ث) — وبدون الترميم كانت
  النافذةُ تُرفض كلُّها، والفكُّ المتسامحُ وحده يُزيحها ~50م.ث.
- **وما زال الحارسُ يرفض** العطبَ الطويل (‏≥ ثانية: صوتٌ مفقود) وخطأَ الفكّ الذي لا فجوةَ تفسّره.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "alignment"))

import mp3_resync as M                                           # noqa: E402
import run                                                       # noqa: E402

RATE = 16000


def _lame_ok():
    if not shutil.which("ffmpeg"):
        return False
    p = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True)
    return "libmp3lame" in p.stdout


def _lag(a, b, at, n=16000, span=2000):
    seg = a[at:at + n]
    best = None
    for L in range(-span, span + 1):
        s = b[at + L:at + L + n]
        if len(s) < n:
            continue
        c = float(np.dot(seg, s))
        if best is None or c > best[0]:
            best = (c, L)
    return best[1]


@unittest.skipUnless(_lame_ok(), "ffmpeg بـlibmp3lame غير متاح")
class Resync(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.clean = os.path.join(cls.tmp, "clean.mp3")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                        "anoisesrc=d=60:c=pink:seed=7:a=0.3", "-ar", "44100", "-ac", "1",
                        "-b:a", "128k", "-c:a", "libmp3lame", cls.clean], check=True)
        d = open(cls.clean, "rb").read()
        frames, _ = M.scan(d)
        mid = frames[len(frames) // 2][0]
        # ثلاثُ مناطق تالفة متقاربة (‏كملفّ المحيسني: 691 بايتاً في ثلاث فجوات) — أوّلُها يمحو رأسَ إطار
        b = bytearray(d)
        for off, n in ((mid, 300), (mid + 700, 200), (mid + 1500, 191)):
            b[off:off + n] = bytes(n)
        cls.dmg = os.path.join(cls.tmp, "dmg.mp3")
        open(cls.dmg, "wb").write(bytes(b))
        # عطبٌ طويل: ~1.6ث مصفّرة (‏صوتٌ مفقودٌ حقّاً)
        b2 = bytearray(d)
        b2[mid:mid + 26000] = bytes(26000)
        cls.long = os.path.join(cls.tmp, "long.mp3")
        open(cls.long, "wb").write(bytes(b2))
        cls.ref = M.ffmpeg_decode_bytes(d)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _fresh(self):
        run._DECODED.clear()
        run._RESYNCED.clear()

    def test_plain_decode_reports_error(self):
        """المقدّمة: الملفُّ المصنوع يُسقط ffmpeg عليه خطأَ فكٍّ فعلاً (‏وإلا لم يُختبر شيء)."""
        self._fresh()
        with self.assertRaises(RuntimeError):
            run._full_decode_pcm(self.dmg)

    def test_window_after_damage_not_shifted(self):
        self._fresh()
        x, r = run._ffmpeg_window_pcm(self.dmg, 45000, 47000)
        self.assertEqual((len(x), r), (32000, RATE))
        ref = self.ref[45 * RATE:47 * RATE]
        full = np.concatenate([np.zeros(45 * RATE, "float32"), x, np.zeros(RATE, "float32")])
        lag = _lag(np.concatenate([np.zeros(45 * RATE, "float32"), ref, np.zeros(RATE, "float32")]),
                   full, 45 * RATE, n=24000, span=1600)
        self.assertLessEqual(abs(lag), RATE // 1000, f"انزاح الزمنُ بعد العطب {lag} عيّنة")

    def test_whole_resync_aligned_before_and_after(self):
        self._fresh()
        x = run._resync_full_decode_pcm(self.dmg)
        self.assertEqual(_lag(self.ref, x, 10 * RATE), 0)
        self.assertLessEqual(abs(_lag(self.ref, x, 45 * RATE)), RATE // 1000)
        rep = run.RESYNC_REPORTS[str(self.dmg)]
        self.assertEqual(len(rep["clusters"]), 1)
        self.assertLess(rep["clusters"][0]["lostMs"], 200)

    def test_tolerant_decode_alone_would_shift(self):
        """الشاهدُ على لزوم الحشو: الفكُّ المتسامحُ وحده يُزيح ما بعد العطب."""
        raw = M.ffmpeg_decode_bytes(open(self.dmg, "rb").read())
        self.assertGreater(abs(_lag(self.ref, raw, 45 * RATE)), RATE // 100)

    def test_long_loss_still_refused(self):
        self._fresh()
        with self.assertRaises(RuntimeError) as cm:
            run._ffmpeg_window_pcm(self.long, 45000, 47000)
        self.assertIn("لا يُرمَّم", str(cm.exception))

    def test_error_without_frame_gap_refused(self):
        with self.assertRaises(M.Unrecoverable):
            M.resync_decode(self.clean, M.ffmpeg_decode_bytes)

    def test_oversized_gap_refused(self):
        """فجوةٌ كبيرةٌ لا يُقدَّر زمنُها من حجمها ⇒ تُردّ (‏حدُّ GAP_SLOT_MAX_MS)."""
        d = bytearray(open(self.clean, "rb").read())
        frames, _ = M.scan(bytes(d))
        mid = frames[len(frames) // 2][0]
        d[mid:mid + 12000] = bytes(12000)
        p = os.path.join(self.tmp, "big.mp3")
        with open(p, "wb") as f:
            f.write(bytes(d))
        with self.assertRaises(M.Unrecoverable) as cm:
            M.resync_decode(p, M.ffmpeg_decode_bytes)
        self.assertIn("لا يُقدَّر زمنٌ بهذا الحجم", str(cm.exception))

    def test_gap_slot_estimate(self):
        frames, gaps = M.scan(open(self.dmg, "rb").read())
        self.assertGreater(M.gap_slot_ms(frames, gaps[0]), 0)
        self.assertLessEqual(M.gap_slot_ms(frames, gaps[0]), M.GAP_SLOT_MAX_MS)

    def test_constants_fixed(self):
        self.assertEqual(M.MAX_LOSS_MS, 1000)
        self.assertEqual(M.MAX_CLUSTERS, 8)
        self.assertEqual(M.GAP_SLOT_MAX_MS, 300)
        src = Path(M.__file__).read_text(encoding="utf-8")
        self.assertNotIn("os.environ", src)


if __name__ == "__main__":
    unittest.main()
