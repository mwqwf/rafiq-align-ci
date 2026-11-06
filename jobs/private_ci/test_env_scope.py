#!/usr/bin/env python3
"""🧱 حارسُ نطاق private-ci (الضمانة أ وأخواتُها) — يفشل إن:

  ١. ذكر أيُّ سيرٍ غيرُ private-ci.yml البيئةَ private-ci (‏نصّاً أو قاموساً أو بأيّ حالةِ أحرف)، أو جعل اسمَ بيئةٍ تعبيراً
     (${{ … }}) قد يُفضي إليها، أو ذكر أحدَ أسرارها الجديدة، أو استدعى private-ci.yml سيراً قابلاً لإعادة الاستعمال؛
  ٢. اتّسع زنادُ private-ci.yml عن repository_dispatch(private-ci) وworkflow_dispatch(dry_run)، أو فقد ضمانةً:
     صلاحياتٌ أوسع من contents: read · إجراءٌ غيرُ مثبَّتٍ بـSHA · actions/cache · upload/download-artifact · setup-gradle ·
     set -x · طباعةُ السجلّ · مهمّةٌ بلا timeout-minutes · خطوةٌ تحمل السرَّ ولا تستدعي سكربتاً معروفاً · checkout يحفظ الاعتماد؛
  ٣. خرج private-ci-sweeper.yml عن workflow_run وactions: write وGITHUB_TOKEN وحده؛
  ٤. وُضع في jobs/private_ci/ سكربتُ ‎.sh غيرُ run.sh، أو فقد run.sh شرطَ الاستدعاء (‏agent-job.yml يُنفّذ jobs/**/*.sh)؛
  ٥. انتشر المفتاحُ القديم QR_READ_DEPLOY_KEY_B64 إلى سيرٍ ليس في قائمة الإرث المعلَنة (‏تُصفَّر عند ب3).
"""
import os
import re
import sys
import unittest

try:
    import yaml
except ImportError:  # pragma: no cover — السيرُ يثبّتها؛ وغيابُها محلّيّاً لا يُبرّئ
    yaml = None

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.environ.get("PCI_REPO_ROOT", os.path.join(HERE, "..", "..")))
WF_DIR = os.path.join(ROOT, ".github", "workflows")
MAIN = "private-ci.yml"
SWEEPER = "private-ci-sweeper.yml"
ENV_NAME = "private-ci"
NEW_SECRETS = ("PCI_DEPLOY_KEY_B64", "PRIVATE_CI_R2_JSON", "PCI_STATUS_TOKEN")
LEGACY_KEY = "QR_READ_DEPLOY_KEY_B64"
# ⛔ إرثٌ معلَن (2026-11-06): ثلاثةُ سيورٍ تقرأ المفتاحَ القديم على مستوى المستودع — تعارضٌ قائمٌ مع (أ).
#    خطّةُ إغلاقه في docs/ops/CI_PUBLIC_RUNNER_MIGRATION.md (‏في الخاص) §خطوات المالك؛ وعند ب3 تُفرَّغ هذه القائمة.
LEGACY_KEY_USERS = {"agent-job.yml", "package-catalog-cloud.yml", "tasmi-student-train.yml"}
SHA_PIN = re.compile(r"^[\w.-]+/[\w.-]+(?:/[\w./-]+)?@[0-9a-f]{40}$")
ALLOWED_SECRET_STEPS = {
    "PCI_DEPLOY_KEY_B64": "run.sh clone",
    "PRIVATE_CI_R2_JSON": "upload_r2.py",
    "R2_CREDENTIALS_JSON": "upload_r2.py",
    "PCI_STATUS_TOKEN": "status_back.py",
}
FORBIDDEN_USES = ("actions/cache", "actions/upload-artifact", "actions/download-artifact",
                  "gradle/actions/setup-gradle", "gradle/gradle-build-action")


def workflows():
    if not os.path.isdir(WF_DIR):
        return {}
    out = {}
    for name in sorted(os.listdir(WF_DIR)):
        if name.endswith((".yml", ".yaml")):
            with open(os.path.join(WF_DIR, name), encoding="utf-8") as f:
                out[name] = f.read()
    return out


def parse(text):
    d = yaml.safe_load(text) or {}
    if True in d and "on" not in d:  # PyYAML يقرأ المفتاحَ on قيمةً منطقيّة
        d["on"] = d.pop(True)
    return d


def env_names(job):
    env = job.get("environment")
    if env is None:
        return []
    if isinstance(env, dict):
        env = env.get("name", "")
    return [str(env)]


def steps(job):
    return job.get("steps") or []


def find_violations(files):
    """يُعيد قائمةَ مخالفاتٍ نصّيّة (فارغةٌ = سليم). منفصلةٌ عن unittest ليختبرها test_guard بأمثلةٍ مزروعة."""
    v = []
    for name, text in files.items():
        if name in (MAIN, SWEEPER):
            continue
        for s in NEW_SECRETS:
            if s in text:
                v.append(f"{name}: يذكر السرَّ {s}")
        if re.search(r"uses:\s*\./\.github/workflows/private-ci", text):
            v.append(f"{name}: يستدعي private-ci.yml")
        try:
            d = parse(text)
        except yaml.YAMLError:
            v.append(f"{name}: YAML غيرُ مقروء")
            continue
        for jid, job in (d.get("jobs") or {}).items():
            if not isinstance(job, dict):
                continue
            for e in env_names(job):
                if "${{" in e:
                    v.append(f"{name}/{jid}: اسمُ بيئةٍ تعبيريّ")
                elif e.strip().lower().replace("_", "-") == ENV_NAME:
                    v.append(f"{name}/{jid}: يذكر البيئة {ENV_NAME}")
        if LEGACY_KEY in text and name not in LEGACY_KEY_USERS:
            v.append(f"{name}: مستعملٌ جديدٌ للمفتاح القديم {LEGACY_KEY}")
    if MAIN in files:
        v += main_violations(files[MAIN])
    if SWEEPER in files:
        v += sweeper_violations(files[SWEEPER])
    return v


def main_violations(text):
    v = []
    d = parse(text)
    on = d.get("on") or {}
    if set(on) != {"repository_dispatch", "workflow_dispatch"}:
        v.append(f"{MAIN}: الزنادُ يجب أن يكون repository_dispatch وworkflow_dispatch وحدهما")
    rd = on.get("repository_dispatch") or {}
    if (rd.get("types") if isinstance(rd, dict) else None) != ["private-ci"]:
        v.append(f"{MAIN}: repository_dispatch بنوعٍ غير private-ci")
    wd = on.get("workflow_dispatch") or {}
    if "dry_run" not in ((wd.get("inputs") or {}) if isinstance(wd, dict) else {}):
        v.append(f"{MAIN}: workflow_dispatch بلا dry_run")
    if (d.get("permissions") or {}) != {"contents": "read"}:
        v.append(f"{MAIN}: الصلاحياتُ أوسعُ من contents: read")
    if "concurrency" not in d:
        v.append(f"{MAIN}: بلا concurrency")
    if re.search(r"(?m)^\s*set\s+-[a-z]*x|set\s+-o\s+xtrace|\bbash\s+-x\b", text):
        v.append(f"{MAIN}: set -x")
    if re.search(r"\b(?:cat|tail|head\s+-n)\b[^\n|]*log\.txt", text):
        v.append(f"{MAIN}: يطبع السجلّ")
    for jid, job in (d.get("jobs") or {}).items():
        if "timeout-minutes" not in job:
            v.append(f"{MAIN}/{jid}: بلا timeout-minutes")
        if "permissions" in job:
            v.append(f"{MAIN}/{jid}: صلاحياتٌ على مستوى المهمّة")
        envs = env_names(job)
        if envs and envs != [ENV_NAME]:
            v.append(f"{MAIN}/{jid}: بيئةٌ غيرُ private-ci")
        for st in steps(job):
            uses = st.get("uses", "")
            if uses:
                if any(uses.startswith(f) for f in FORBIDDEN_USES):
                    v.append(f"{MAIN}/{jid}: إجراءٌ ممنوع {uses.split('@')[0]}")
                if not uses.startswith("./") and not SHA_PIN.match(uses):
                    v.append(f"{MAIN}/{jid}: إجراءٌ غيرُ مثبَّتٍ بـSHA {uses.split('@')[0]}")
                w = st.get("with") or {}
                if uses.startswith("actions/checkout") and w.get("persist-credentials") is not False:
                    v.append(f"{MAIN}/{jid}: checkout يحفظ الاعتماد")
                if uses.startswith("actions/setup-java") and "cache" in w:
                    v.append(f"{MAIN}/{jid}: setup-java بذاكرةٍ مؤقّتة")
            env_txt = str(st.get("env") or {})
            run = st.get("run", "") or ""
            for sec, must in ALLOWED_SECRET_STEPS.items():
                if f"secrets.{sec}" in env_txt and must not in run:
                    v.append(f"{MAIN}/{jid}: السرّ {sec} في خطوةٍ لا تستدعي {must}")
            if "secrets." in run or "secrets." in str(st.get("with") or {}):
                v.append(f"{MAIN}/{jid}: سرٌّ داخل run/with لا في env")
        # ⛔ لا سرَّ على مستوى المهمّة: يرثه كلُّ خطوة (‏ومنها البناءُ الذي يشغّل شيفرةَ الخاص)
        if "secrets." in str(job.get("env") or {}):
            v.append(f"{MAIN}/{jid}: سرٌّ في env المهمّة")
    return v


def sweeper_violations(text):
    v = []
    d = parse(text)
    if set((d.get("on") or {})) != {"workflow_run"}:
        v.append(f"{SWEEPER}: الزنادُ غيرُ workflow_run")
    if (d.get("permissions") or {}) != {"actions": "write", "contents": "read"}:
        v.append(f"{SWEEPER}: صلاحياتٌ غيرُ actions: write وcontents: read")
    if re.findall(r"secrets\.(\w+)", text):
        v.append(f"{SWEEPER}: يستعمل سرّاً")
    for jid, job in (d.get("jobs") or {}).items():
        if env_names(job):
            v.append(f"{SWEEPER}/{jid}: يذكر بيئة")
    return v


def jobs_dir_violations(jobs_dir):
    v = []
    for name in os.listdir(jobs_dir):
        if name.endswith(".sh") and name != "run.sh":
            v.append(f"jobs/private_ci/{name}: سكربتٌ ‎.sh سيُنفّذه agent-job.yml")
    run = os.path.join(jobs_dir, "run.sh")
    if os.path.isfile(run):
        with open(run, encoding="utf-8") as f:
            body = f.read()
        head = body.split("exec >>", 1)[0]
        if "*/.github/workflows/private-ci.yml@*" not in head or "GITHUB_WORKFLOW_REF" not in head:
            v.append("jobs/private_ci/run.sh: شرطُ الاستدعاء من private-ci.yml غائبٌ قبل أوّل أمر")
        if re.search(r"(?m)^\s*set\s+-[a-z]*x", body):
            v.append("jobs/private_ci/run.sh: set -x")
    return v


@unittest.skipIf(yaml is None, "PyYAML غيرُ مثبّت")
class EnvScopeTest(unittest.TestCase):
    def setUp(self):
        self.files = workflows()
        if not self.files:
            self.skipTest("لا مجلّدَ .github/workflows في هذه الشجرة (التجربةُ الجزئيّة)")

    def test_repository_is_clean(self):
        self.assertEqual(find_violations(self.files), [])

    def test_private_ci_present(self):
        self.assertIn(MAIN, self.files)
        self.assertIn(SWEEPER, self.files)

    def test_jobs_dir(self):
        self.assertEqual(jobs_dir_violations(HERE), [])


if __name__ == "__main__":
    unittest.main()
