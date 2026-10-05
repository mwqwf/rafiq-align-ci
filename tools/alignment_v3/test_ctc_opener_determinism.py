#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""حتميّةُ الشاهد الثاني للمطالع (‏fixV 2026-10-05): الحرّاز 73:1 أعطى «مؤكَّد» مرّةً و«غيرُ مؤكَّد»
مرّتين على الملفّ نفسِه لأنّ `ctc_seg._model` يكمّم int8 افتراضاً. هذه الاختباراتُ تفشل بلا الإصلاح."""
import importlib
import os
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


class Determinism(unittest.TestCase):
    def test_import_forces_float32_single_thread_even_if_env_says_int8(self):
        # بيئةٌ «عدائيّة»: من يطلب int8 وخيوطاً كثيرة لا يُرخي الشاهد.
        env = dict(os.environ, CTC_INT8="1", CTC_THREADS="8", MKL_CBWR="AUTO")
        code = ("import os,sys; sys.path.insert(0, %r); import ctc_opener_probe; "
                "print(os.environ['CTC_INT8'], os.environ['CTC_THREADS'], os.environ['MKL_CBWR'])" % str(HERE))
        out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True)
        self.assertEqual(out.stdout.split(), ["0", "1", "AVX2,STRICT"])

    def test_quantized_model_rejected(self):
        sys.path.insert(0, str(HERE))
        P = importlib.import_module("ctc_opener_probe")

        class Lin: pass
        Q = type("DynLinear", (), {"__module__": "torch.ao.nn.quantized.dynamic.modules.linear"})

        class M:
            def __init__(self, mods): self.mods = mods
            def named_modules(self): return self.mods

        P.assert_float32(M([("", object()), ("lm_head", Lin())]))      # float32 يمرّ
        with self.assertRaises(RuntimeError):
            P.assert_float32(M([("", object()), ("lm_head", Q())]))     # المكمَّمُ يُردّ

    def test_rule_records_precision(self):
        src = (HERE / "ctc_opener_probe.py").read_text(encoding="utf-8")
        self.assertIn('doc["lateCtcPrecision"]', src)
        self.assertIn("_ensure_model()", src.split("def probe(")[1].split("\n")[1])


    def test_clip_covers_measured_true_shift(self):
        # الحارثي 89 الصادق: الآيةُ بعد المدخل بـ3908م.ث ⇒ آخرُها بعد نهاية المدخل بالمقدار نفسه تقريباً.
        # مقطعٌ لا يغطّيه يبتر الآيةَ فتنهار الثقةُ إلى 0.0 ويُفلت العطب.
        sys.path.insert(0, str(HERE))
        P = importlib.import_module("ctc_opener_probe")
        self.assertGreaterEqual(P.clip_end_ms(10000) - 10000, 3908 + 1500)


if __name__ == "__main__":
    unittest.main()
