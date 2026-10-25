# -*- coding: utf-8 -*-
"""اختباراتُ القياس الموازي في `ctc_dualfix` (‏2026-10-25 · تسريع): قسمةُ النوافذ على عمّال لا تغيّر بايتاً من
`meas` — لا قيمةً ولا ترتيبَ مفاتيح — لأنّ كلَّ نافذةٍ تُقاس بالدالّة نفسِها، والتجميعُ بترتيب الأصل.
والنموذجُ هنا بديلٌ حتميٌّ (‏لا torch)؛ المطلوبُ إثباتُ سلامة القسمة والتجميع والرجوع إلى المتسلسل."""
import json
import os
import pathlib
import pickle
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import ctc_dualfix as F
import window_census_witness as X

SURAH = 105          # الفيل — خمسُ آياتٍ، وبياناتُ النصّ من المستودع نفسِه
N = 5
FAIL_START = 4000    # نافذةٌ يُفشلها البديلُ عمداً (‏بدؤها م.ث) ليثبت أنّ التعذّر لا يدخل النتيجةَ في الحالين


def fake_ci_module():
    """بديلُ `ci_spoken_census`: نموذجان وهميّان حتميّان يُرجعان مقاطعَ تابعةً لطول المقطع والنصّ وحدهما."""
    C = types.SimpleNamespace(_M={})

    def emissions(pcm):
        return (len(pcm), float(sum(pcm[:50])))

    def segment(em, n_samples, texts):
        n, head = em
        if n // 16 + 0 in (FAIL_START,):
            raise RuntimeError("fake window failure")
        out, t = [], 0.0
        for i, tx in enumerate(texts):
            d = 0.4 + 0.01 * len(tx) + (n % 97) / 1000.0
            out.append((t + 0.0123, t + d, -0.5 - 0.1 * i - (head % 7) / 10.0))
            t += d
        return out

    C._emissions, C._segment = emissions, segment
    C._conf = lambda sc: round(max(0.0, min(1.0, 1.0 + 0.25 * float(sc))), 3)
    Q = types.SimpleNamespace(configure=lambda: {"id": "q", "revision": "r2", "weightsSha256": "w2", "license": "Apache-2.0",
                                                  "canonicalTextChanged": False},
                              reference_text=lambda t: t + "|q")
    mod = types.ModuleType("ci_spoken_census")
    mod.C, mod.Q = C, Q
    mod.configure_generic = lambda: {"id": "g", "revision": "r1", "weightsSha256": "w1", "license": "Apache-2.0"}
    return mod


def make_idx():
    return {"riwaya": "hafs", "entries": [{"ayahId": f"{SURAH}:{k}", "startMs": 1000 * k, "endMs": 1000 * k + 1000}
                                          for k in range(1, N + 1)]}


def make_pcm(total_ms=8000):
    return [((i * 31) % 17) / 17.0 for i in range(total_ms * 16)]


class ShardsTest(unittest.TestCase):
    def plans(self, n=11):
        return {f"9:{k}": ([], [k * 1000, k * 1000 + (k % 4 + 1) * 700], []) for k in range(1, n + 1)}

    def test_every_window_lands_in_exactly_one_shard_keeping_order(self):
        pl = self.plans()
        for w in (1, 2, 3, 5):
            shards = F.split_shards(pl, w)
            self.assertEqual(sorted(k for sh in shards for k in sh), sorted(pl))
            self.assertEqual(sum(len(sh) for sh in shards), len(pl))
            for sh in shards:
                self.assertEqual(list(sh), [k for k in pl if k in sh])      # ترتيبُ plans محفوظ داخل الحصّة

    def test_deterministic_and_balanced(self):
        pl = self.plans(12)
        a, b = F.split_shards(pl, 2), F.split_shards(pl, 2)
        self.assertEqual([list(x) for x in a], [list(x) for x in b])
        load = [sum(v[1][1] - v[1][0] for v in sh.values()) for sh in a]
        longest = max(v[1][1] - v[1][0] for v in pl.values())
        self.assertLessEqual(abs(load[0] - load[1]), longest)               # تفاوتٌ لا يتجاوز أطولَ نافذة

    def test_more_workers_than_windows_never_makes_an_empty_shard(self):
        pl = self.plans(3)
        shards = F.split_shards(pl, 8)
        self.assertEqual(len(shards), 3)
        self.assertTrue(all(shards))

    def test_effective_workers_respects_cores_and_threads(self):
        self.assertEqual(F.effective_workers(2, 2, 4), 2)
        self.assertEqual(F.effective_workers(2, 2, 2), 1)      # مُشغّلٌ بنواتين: لا اشتراكَ زائد
        self.assertEqual(F.effective_workers(8, 2, 4), 2)      # لا يتجاوز الأنوية
        self.assertEqual(F.effective_workers(0, 2, 4), 1)
        self.assertEqual(F.effective_workers(None, 2, 4), 1)


class MeasureEquivalenceTest(unittest.TestCase):
    def setUp(self):
        self._saved = sys.modules.get("ci_spoken_census")
        sys.modules["ci_spoken_census"] = fake_ci_module()
        self.pcm = make_pcm()
        self.idx = make_idx()

    def tearDown(self):
        if self._saved is None:
            sys.modules.pop("ci_spoken_census", None)
        else:
            sys.modules["ci_spoken_census"] = self._saved

    def runner(self, log):
        """مُشغّلُ الحصص في العملية نفسِها لكن بعبور pickle كما يعبر الحدَّ بين عمليّتين."""
        def run(shards, mm_path, n_samples):
            self.assertEqual(n_samples, len(self.pcm))
            return [pickle.loads(pickle.dumps(F._measure_windows(self.pcm, sh, log))) for sh in shards]
        return run

    def measured(self, workers, runner=None):
        logs = []
        with mock.patch.object(F.os, "cpu_count", return_value=4):
            out = F.measure_all(self.pcm, self.idx, SURAH, 8000, log=logs.append, workers=workers,
                                shard_runner=runner)
        return out, logs

    def test_parallel_result_is_byte_identical_to_serial(self):
        (m1, mod1, pl1), _ = self.measured(1)
        (m2, mod2, pl2), logs = self.measured(2, self.runner(lambda m: None))
        self.assertTrue(any("قياسٌ موازٍ" in line for line in logs))
        dump = lambda *a: json.dumps(a, ensure_ascii=False)                # يشمل ترتيبَ المفاتيح
        self.assertEqual(dump(m1, mod1, pl1), dump(m2, mod2, pl2))
        self.assertEqual(list(mod2), ["generic", "quran"])
        for aid, per in m2.items():
            if "generic" in per and "quran" in per:
                self.assertEqual(list(per), ["generic", "context", "quran"])     # كترتيب الأصل

    def test_a_failed_window_is_skipped_in_both_paths(self):
        (m1, _, _), _ = self.measured(1)
        failed = [aid for aid, per in m1.items() if "generic" not in per]
        self.assertTrue(failed, "البديلُ يُفشل نافذةً عمداً")
        (m2, _, _), _ = self.measured(2, self.runner(lambda m: None))
        self.assertEqual(json.dumps(m1), json.dumps(m2))

    def test_broken_worker_pool_falls_back_to_serial_not_to_partial_result(self):
        (m1, _, _), _ = self.measured(1)
        def broken(shards, mm_path, n_samples):
            raise RuntimeError("A process in the process pool was terminated abruptly")
        (m2, _, _), logs = self.measured(2, broken)
        self.assertTrue(any("يعود إلى المتسلسل" in line for line in logs))
        self.assertEqual(json.dumps(m1), json.dumps(m2))

    def test_workers_one_never_touches_the_pool(self):
        def boom(*a):
            raise AssertionError("pool must not be used")
        (m, _, _), _ = self.measured(1, boom)
        self.assertTrue(m)

    def test_value_errors_from_a_worker_are_not_swallowed(self):
        def bad(shards, mm_path, n_samples):
            raise ValueError("Unsupported canonical character")
        with self.assertRaises(ValueError):
            self.measured(2, bad)


class ShardWorkerTest(unittest.TestCase):
    def test_worker_refuses_a_file_of_a_different_length(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "x.16k.f32")
            np.zeros(1600, dtype="<f4").tofile(path)
            with self.assertRaises(RuntimeError):
                F._shard_worker(path, 1601, {})

    def test_real_process_pool_roundtrip_with_a_stub_worker(self):
        """آليّةُ spawn نفسُها (‏استيرادُ الوحدة في الابن · فتحُ الفكّ ذاكرةً مرسومة · نقلُ النتيجة) بعاملٍ بديل."""
        import subprocess
        import numpy as np
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "a.mp3.16k.f32")
            np.arange(3200, dtype="<f4").tofile(path)
            script = os.path.join(d, "smoke.py")
            pathlib.Path(script).write_text(
                "import sys, numpy as np\n"
                f"sys.path.insert(0, {str(pathlib.Path(__file__).parent)!r})\n"
                "import ctc_dualfix as F\n"
                "def stub(mm, n, sh):\n"
                "    x = np.memmap(mm, dtype='<f4', mode='r')\n"
                "    assert len(x) == n\n"
                "    return ({'generic': {k: ([(1, 2, 0.5)], 0) for k in sh}, 'quran': {}}, {'generic': {'id': 'g'}})\n"
                "if __name__ == '__main__':\n"
                "    F._shard_worker = stub\n"
                f"    r = F._run_shards_in_processes([{{'a': 1}}, {{'b': 2}}], {path!r}, 3200)\n"
                "    print(sorted(k for p in r for k in p[0]['generic']))\n",
                encoding="utf-8")
            p = subprocess.run([sys.executable, script], capture_output=True, text=True, timeout=120)
            self.assertEqual(p.returncode, 0, p.stderr[-800:])
            self.assertIn("['a', 'b']", p.stdout)


class WiringTest(unittest.TestCase):
    ROOT = pathlib.Path(__file__).parents[2]

    def wf(self):
        return (self.ROOT / ".github" / "workflows" / "ctc_splice.yml").read_text(encoding="utf-8")

    def test_workflow_enables_two_workers_without_changing_precision_or_threads(self):
        y = self.wf()
        self.assertIn('CTC_DUALFIX_WORKERS: "2"', y)
        self.assertIn("CTC_INT8=0 CTC_THREADS=2", y)
        self.assertEqual(X.RUNTIME, {"precision": "float32", "threads": 2})   # العقدُ الذي يحكم عليه الشاهدُ

    def test_dualfix_main_reads_workers_from_env_and_enforces_threads(self):
        src = (pathlib.Path(F.__file__)).read_text(encoding="utf-8")
        self.assertIn('os.environ.get("CTC_DUALFIX_WORKERS")', src)
        self.assertIn('os.environ.get("CTC_THREADS") != "2"', src)

    def test_budget_guard_wraps_dualfix_and_heard_loops(self):
        y = self.wf()
        self.assertIn("B_END=$(( ${JOB_T0:-$(date +%s)} + (350 - 25) * 60 ))", y)
        self.assertEqual(y.count('LEFT=$(( B_END - $(date +%s) ))'), 2)
        self.assertIn('timeout --signal=TERM --kill-after=60 "${LEFT}s" python tools/alignment_v3/ctc_dualfix.py', y)
        self.assertIn('timeout --signal=TERM --kill-after=60 "${LEFT}s" python tools/alignment_v3/ctc_heard_map.py', y)
        self.assertEqual(y.count('s*.json.part'), 2)

    def test_per_surah_outputs_are_written_atomically(self):
        for name in ("ctc_dualfix.py", "ctc_heard_map.py"):
            src = (pathlib.Path(F.__file__).parent / name).read_text(encoding="utf-8")
            self.assertIn('os.replace(out + ".part", out)', src, name)


if __name__ == "__main__":
    unittest.main()
