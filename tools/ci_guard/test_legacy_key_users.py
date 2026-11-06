#!/usr/bin/env python3
"""حارسُ مستهلكي المفتاح القديم (§13-د من CI_PUBLIC_RUNNER_MIGRATION.md) — يحلّ محلَّ test_env_scope.py.

يفشل إن:
  ١. ذكر سيرٌ في .github/workflows/ غيرُ الاثنين المسموحَين النصَّ QR_READ_DEPLOY_KEY_B64 أو QuranRafiq.git أو mwqwf/QuranRafiq
     (المسموحان: package-catalog-cloud.yml و tasmi-student-train.yml؛ ويُستثنى job-log.yml بالاسم لأنّ ذكره تعليقٌ/قائمةُ رفض).
  ٢. وُجد سيرٌ اسمُه يبدأ بـprivate-ci (بقايا v1).
  ٣. وُجد مجلّد jobs/private_ci.
بلا تبعيّات: unittest وحدها.
"""
import os
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
NEEDLES = ("QR_READ_DEPLOY_KEY_B64", "QuranRafiq.git", "mwqwf/QuranRafiq")
ALLOWED_USERS = {"package-catalog-cloud.yml", "tasmi-student-train.yml"}
EXEMPT_MENTION_ONLY = {"job-log.yml"}  # ذكرٌ في تعليقٍ؛ فُحص يدويّاً ولا يُوسَّع هذا الاستثناء


def violations(root):
    out = []
    wf = os.path.join(root, ".github", "workflows")
    if os.path.isdir(wf):
        for name in sorted(os.listdir(wf)):
            if name.startswith("private-ci"):
                out.append(f"سيرٌ من بقايا v1: {name}")
            if not os.path.isfile(os.path.join(wf, name)) or name in ALLOWED_USERS | EXEMPT_MENTION_ONLY:
                continue
            with open(os.path.join(wf, name), encoding="utf-8", errors="replace") as f:
                text = f.read()
            for n in NEEDLES:
                if n in text:
                    out.append(f"سيرٌ غيرُ مسموحٍ يذكر {n}: {name}")
    if os.path.exists(os.path.join(root, "jobs", "private_ci")):
        out.append("مجلّد jobs/private_ci باقٍ")
    return out


class LegacyKeyUsersTest(unittest.TestCase):
    def test_repo_is_clean(self):
        self.assertEqual(violations(ROOT), [])

    def test_catches_planted_violations(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            wf = os.path.join(d, ".github", "workflows")
            os.makedirs(wf)
            os.makedirs(os.path.join(d, "jobs", "private_ci"))
            for name, text in (("a.yml", "k: ${{ secrets.QR_READ_DEPLOY_KEY_B64 }}"),
                               ("b.yml", "git clone git@github.com:mwqwf/QuranRafiq.git"),
                               ("c.yml", "repo: mwqwf/QuranRafiq"),
                               ("private-ci-x.yml", "name: x"),
                               ("package-catalog-cloud.yml", "QR_READ_DEPLOY_KEY_B64"),
                               ("ok.yml", "name: ok")):
                with open(os.path.join(wf, name), "w", encoding="utf-8") as f:
                    f.write(text)
            got = violations(d)
            self.assertEqual(len(got), 6, got)  # b.yml يطابق نمطَين
            self.assertTrue(any("a.yml" in g for g in got) and any("b.yml" in g for g in got)
                            and any("c.yml" in g for g in got) and any("private-ci-x.yml" in g for g in got)
                            and any("jobs/private_ci" in g for g in got))
            self.assertFalse(any("package-catalog-cloud" in g or "ok.yml" in g for g in got))


if __name__ == "__main__":
    unittest.main()
