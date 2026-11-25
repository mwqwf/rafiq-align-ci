"""عقدُ ذاكرة أحكام الصوت بين الدورات — بلا اتصالٍ بالدلو.

💰 سببُه مقيس (2026-11-25): ‏97% من GetObject على rafiq-media كانت تنزيلَ state/ كاملاً
في كلّ دورة لأنّ العدّاء يبدأ بذاكرةٍ فارغة. العقدُ: كلُّ سير عملٍ يشغّل promote.py مجدولاً
يستعيد الذاكرةَ قبله ويحفظها بعده، والمسارُ هو مسارُ promote.bucket_reports نفسُه.
"""
from pathlib import Path
import re
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = "tools/index_qa/work/verdict_cache"
# سيرُ العمل ← (الوظيفة، نصٌّ يدلّ على خطوة الترقية)
WORKFLOWS = {
    "ctc_driver.yml": ("drive", "ctc_driver.py"),
    "keepalive.yml": ("gate_and_promote", "promote.py --yes"),
    "restore.yml": ("restore", "restore_loop.py promote"),
}


def load(rel):
    return yaml.load((ROOT / rel).read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


class VerdictCacheContract(unittest.TestCase):
    def test_path_matches_promote(self):
        src = (ROOT / "tools/index_qa/promote.py").read_text(encoding="utf-8")
        self.assertIn('Path(__file__).resolve().parent / "work" / "verdict_cache"', src)
        # الذاكرةُ مفتاحُها «المفتاح|ETag» ⇒ ملفٌّ تغيّر يُنزَّل من جديد.
        self.assertIn('f"{key}|{etag}"', src)

    def test_actions_use_same_path_and_prefix(self):
        r = load(".github/actions/verdict-cache-restore/action.yml")
        s = load(".github/actions/verdict-cache-save/action.yml")
        rc = next(x for x in r["runs"]["steps"] if x.get("uses", "").startswith("actions/cache/restore"))
        sc = next(x for x in s["runs"]["steps"] if x.get("uses", "").startswith("actions/cache/save"))
        self.assertEqual(rc["with"]["path"], CACHE_DIR)
        self.assertEqual(sc["with"]["path"], CACHE_DIR)
        self.assertEqual(rc["with"]["restore-keys"].strip(), "verdict-cache-")
        self.assertTrue(sc["with"]["key"].startswith("verdict-cache-"))
        # حفظٌ عند الزيادة وحدها، وتقليمٌ يُبقي نسختين ولا يُفشل الوظيفة.
        self.assertEqual(sc["if"], "steps.count.outputs.save == 'true'")
        prune = s["runs"]["steps"][-1]["run"]
        self.assertIn("'.[2:][].id'", prune)
        self.assertIn("|| true", prune)

    def test_scheduled_promoters_restore_before_and_save_after(self):
        for wf, (job, marker) in WORKFLOWS.items():
            with self.subTest(wf=wf):
                steps = load(f".github/workflows/{wf}")["jobs"][job]["steps"]
                uses = [s.get("uses", "") for s in steps]
                runs = [s.get("run", "") for s in steps]
                ri = uses.index("./.github/actions/verdict-cache-restore")
                si = uses.index("./.github/actions/verdict-cache-save")
                pi = next(i for i, r in enumerate(runs) if marker in r)
                self.assertLess(ri, pi)
                self.assertGreater(si, pi)
                self.assertEqual(steps[si]["if"], "always()")
                self.assertTrue(re.fullmatch(r"\$\{\{ github\.token \}\}", steps[si]["with"]["token"]))
                # الاستعادةُ بعد checkout (فالإجراءُ المحليّ موجود).
                self.assertLess(uses.index("actions/checkout@v4"), ri)


if __name__ == "__main__":
    unittest.main()
