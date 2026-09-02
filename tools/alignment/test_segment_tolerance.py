# -*- coding: utf-8 -*-
"""مقطعٌ يسقط لا يُسقط السورة — اختبارٌ يحقن الفشل ويثبت الاكتمال والوسم.

⛔ سبب وجوده مقيس (‏github-f4، 2026-09-02): مقطعٌ واحد يفشل في whisper فيرمي،
فتسقط السورة كلها ⇒ 112/114 ⇒ حارس الرفع يرفض ⇒ **يُعزل القارئ ويضيع عمله
كله**. وقع في `trabulsi` (‏15 و28) و`mansor` (‏9) وغيرهما على Cloud Run.

والمبدأ الذي يختبره: **الغياب الموسوم أنفع من قارئٍ ضائع، والصمت وحده ممنوع.**
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import transcribe as T  # noqa: E402


class SegmentToleranceTest(unittest.TestCase):
    def setUp(self):
        self._orig = T.transcribe_range
        self._orig_segs = T.speech_segments

    def tearDown(self):
        T.transcribe_range = self._orig
        T.speech_segments = self._orig_segs

    def _fake_segments(self, n):
        T.speech_segments = lambda total_ms, sil: [
            (i * 1000, (i + 1) * 1000) for i in range(n)
        ]

    def test_failed_segment_is_marked_and_surah_completes(self):
        """المقطع الثالث يسقط: تكتمل السورة، ويُوسَم الساقط، ولا يُفقد غيره."""
        self._fake_segments(5)

        def fake(wav, s, dur, tag):
            if tag == "seg2":
                raise T.SegmentFailed("CalledProcessError rc=127 · stderr: libwhisper.so.1 not found")
            return ["كلمة", tag]

        T.transcribe_range = fake
        out = T.transcribe("x.wav", 5000, [], log=lambda *a: None)

        self.assertEqual(len(out), 5, "السورة يجب أن تكتمل بكل مقاطعها")
        bad = [o for o in out if o.get("missing")]
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["words"], [], "الساقط بلا كلمات لا بكلماتٍ مخترعة")
        # ⛔ والتشخيص يُحفظ معه: «مفقود» بلا سببٍ يُعيد العطب مجهولاً
        self.assertIn("rc=127", bad[0]["why"])
        self.assertIn("libwhisper", bad[0]["why"])
        good = [o for o in out if not o.get("missing")]
        self.assertEqual(len(good), 4, "بقية المقاطع تمرّ سليمة")

    def test_unknown_error_still_raises(self):
        """⛔ التسامح مع `SegmentFailed` وحده: خطأٌ آخر يبقى صارخاً.

        وإلا صار الحارسُ بابَ ابتلاعٍ لعطبٍ لا نعرفه — وهو أسوأ من العطب.
        """
        self._fake_segments(3)

        def fake(wav, s, dur, tag):
            if tag == "seg1":
                raise MemoryError("لا ذاكرة")
            return ["كلمة"]

        T.transcribe_range = fake
        with self.assertRaises(MemoryError):
            T.transcribe("x.wav", 3000, [], log=lambda *a: None)


if __name__ == "__main__":
    unittest.main()
