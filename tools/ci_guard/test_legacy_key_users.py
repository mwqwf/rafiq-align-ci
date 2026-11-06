#!/usr/bin/env python3
"""حارسُ مستهلكي المفتاح القديم (§13-د من CI_PUBLIC_RUNNER_MIGRATION.md) — يحلّ محلَّ test_env_scope.py.

يفشل إن:
  ١. ذكر سيرٌ في .github/workflows/ غيرُ الاثنين المسموحَين أيَّ اسمٍ فيه DEPLOY_KEY أو QuranRafiq.git أو mwqwf/QuranRafiq
     (المسموحان: package-catalog-cloud.yml و tasmi-student-train.yml).
     ⛔ أ7 (الإصلاح الرابع): لا يُستثنى ملفٌّ كاملٌ بعد اليوم؛ في job-log.yml يُستثنى **السطرُ المعروف وحده** (قائمةُ رفضٍ
     تُطابَق حرفاً بعد قصّ المسافات) — وأيُّ ذكرٍ آخرَ فيه يُمسك.
  ٢. وُجد سيرٌ اسمُه يبدأ بـprivate-ci (بقايا v1).
  ٣. وُجد مجلّد jobs/private_ci (أو أيُّ مجلّدٍ تحت jobs/ اسمُه يبدأ بـprivate).
بلا تبعيّات: unittest وحدها.
"""
import os
import re
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
# كلُّ نمطٍ يُبحث مستقلّاً (فلا يبتلع تطابقٌ متداخلٌ غيرَه)
NEEDLES = tuple(re.compile(x) for x in (r"\w*DEPLOY_KEY\w*", r"QuranRafiq\.git", r"mwqwf/QuranRafiq"))
ALLOWED_USERS = {"package-catalog-cloud.yml", "tasmi-student-train.yml"}
# أ7: سطرٌ بعينه لا ملفٌّ كامل — قائمةُ الرفض في job-log.yml (فُحصت يدويّاً). تغييرُه يتطلّب تعديلَ هذا الثابت عمداً.
KNOWN_LINES = {
    "job-log.yml": {
        r'MARK = re.compile(r"\w*DEPLOY_KEY\w*|QuranRafiq\.git|mwqwf/QuranRafiq")  # أيُّ مفتاحِ نشرٍ أيّاً كان اسمُه',
    },
}
# المساراتُ التي يحرسها السيرُ على push (pull_request بلا مرشّح: الفحصُ يظهر على كلّ طلب — Codex الرابعة أ7)
GUARDED_PATHS = ('".github/workflows/**"', '"tools/ci_guard/**"', '"jobs/private_ci/**"', '"jobs/**/private*"',
                 '".github/workflows/legacy-key-guard.yml"')


def violations(root):
    out = []
    wf = os.path.join(root, ".github", "workflows")
    if os.path.isdir(wf):
        for name in sorted(os.listdir(wf)):
            if name.startswith("private-ci"):
                out.append(f"سيرٌ من بقايا v1: {name}")
            if not os.path.isfile(os.path.join(wf, name)) or name in ALLOWED_USERS:
                continue
            known = KNOWN_LINES.get(name, set())
            with open(os.path.join(wf, name), encoding="utf-8", errors="replace") as f:
                for no, line in enumerate(f, 1):
                    if line.strip() in known:
                        continue
                    for m in sorted({x for n in NEEDLES for x in n.findall(line)}):
                        out.append(f"سيرٌ غيرُ مسموحٍ يذكر {m}: {name}:{no}")
    jobs = os.path.join(root, "jobs")
    if os.path.exists(os.path.join(jobs, "private_ci")):
        out.append("مجلّد jobs/private_ci باقٍ")
    elif os.path.isdir(jobs):
        out += [f"مجلّدٌ خاصٌّ تحت jobs/: {d}" for d in sorted(os.listdir(jobs)) if d.startswith("private")]
    return out


class LegacyKeyUsersTest(unittest.TestCase):
    def test_repo_is_clean(self):
        self.assertEqual(violations(ROOT), [])

    def _repo(self, d, files):
        wf = os.path.join(d, ".github", "workflows")
        os.makedirs(wf, exist_ok=True)
        for name, text in files:
            with open(os.path.join(wf, name), "w", encoding="utf-8") as f:
                f.write(text)

    def test_catches_planted_violations(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "jobs", "private_ci"))
            self._repo(d, (("a.yml", "k: ${{ secrets.QR_READ_DEPLOY_KEY_B64 }}"),
                           ("b.yml", "git clone git@github.com:mwqwf/QuranRafiq.git"),
                           ("c.yml", "repo: mwqwf/QuranRafiq"),
                           ("d.yml", "k: ${{ secrets.OTHER_DEPLOY_KEY }}"),
                           ("private-ci-x.yml", "name: x"),
                           ("package-catalog-cloud.yml", "QR_READ_DEPLOY_KEY_B64"),
                           ("ok.yml", "name: ok")))
            got = violations(d)
            self.assertEqual(len(got), 7, got)  # b.yml يطابق نمطَين
            for needle in ("a.yml", "b.yml", "c.yml", "d.yml", "private-ci-x.yml", "jobs/private_ci"):
                self.assertTrue(any(needle in g for g in got), needle)
            self.assertFalse(any("package-catalog-cloud" in g or "ok.yml" in g for g in got))

    def test_a7_known_line_alone_passes_in_job_log(self):
        """أ7: السطرُ المعروف (بإزاحةٍ أيّاً كانت) هو وحده ما يُعفى في job-log.yml."""
        import tempfile
        (line,) = KNOWN_LINES["job-log.yml"]
        with tempfile.TemporaryDirectory() as d:
            self._repo(d, (("job-log.yml", "steps:\n  - run: |\n          " + line + "\n"),))
            self.assertEqual(violations(d), [])

    def test_a7_planted_secret_in_job_log_is_caught(self):
        """أ7 سلبيّ: سرٌّ مزروعٌ في job-log.yml بجوار السطر المعروف يُمسك (لا استثناءَ للملفّ كلِّه)."""
        import tempfile
        (line,) = KNOWN_LINES["job-log.yml"]
        for planted in ("  K: ${{ secrets.QR_READ_DEPLOY_KEY_B64 }}",
                        "  run: git clone git@github.com:mwqwf/QuranRafiq.git",
                        "  K: ${{ secrets.NEW_DEPLOY_KEY_X }}",
                        "  " + line + "  # ${{ secrets.QR_READ_DEPLOY_KEY_B64 }}"):
            with tempfile.TemporaryDirectory() as d:
                self._repo(d, (("job-log.yml", "          " + line + "\n" + planted + "\n"),))
                got = violations(d)
                self.assertTrue(got and all("job-log.yml:2" in g for g in got), (planted, got))

    def test_a7_restoring_private_jobs_is_caught(self):
        """أ7 سلبيّ: عودةُ jobs/private_ci أو مجلّدٍ خاصٍّ آخرَ تحت jobs/ تُمسك."""
        import tempfile
        for sub in ("private_ci", "private_v1"):
            with tempfile.TemporaryDirectory() as d:
                os.makedirs(os.path.join(d, "jobs", sub))
                self.assertEqual(len(violations(d)), 1, sub)

    def test_a7_workflow_triggers_cover_the_guarded_paths(self):
        """أ7: push يغطّي كلَّ مسارٍ محروس؛ وأ7-ب (Codex الرابعة): pull_request بلا مرشّح مسارات فيظهر الفحصُ على كلّ طلب،
        وسياقُ الفحص باسم السير (اسمُ الوظيفة = legacy-key-guard)، ويدويّاً."""
        p = os.path.join(ROOT, ".github", "workflows", "legacy-key-guard.yml")
        with open(p, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("workflow_dispatch:", text)
        self.assertRegex(text, r"\nname: legacy-key-guard\n")        # اسم السير
        self.assertRegex(text, r"\n    name: legacy-key-guard\n")    # اسم الوظيفة = السياق المطلوب في حماية main
        self.assertNotIn("paths-ignore", text)
        _, sep, triggers = text.partition("\non:\n")
        self.assertTrue(sep, "كتلة on: مفقودة")
        triggers = "\n" + triggers  # أوّلُ زنادٍ يلي «on:» مباشرةً بلا سطرٍ قبله، فيُسبق بسطرٍ ليُطابَق كغيره
        self.assertIn("\n  pull_request:", triggers)
        pr = triggers.split("\n  pull_request:", 1)[1].split("\n  push:", 1)[0]
        push = triggers.split("\n  push:", 1)[1].split("\n  workflow_dispatch:", 1)[0]
        self.assertNotIn("paths", pr, "pull_request بلا مرشّح مسارات — وإلا غاب الفحصُ عن طلبٍ لا يمسّها فلا يُستوفى الشرط")
        self.assertIn("branches: [main]", push)
        for path in GUARDED_PATHS:
            self.assertIn(path, push, path)


if __name__ == "__main__":
    unittest.main()
