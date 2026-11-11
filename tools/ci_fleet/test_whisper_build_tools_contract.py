"""اختبارات محلية لأدوات realign؛ كل أوامر apt وsudo وهمية بلا شبكة."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / 'tools/ci_fleet/ensure_whisper_build_tools.sh'
TOOLS = ('cmake', 'make', 'gcc', 'g++')
BASH = shutil.which('bash')


@unittest.skipUnless(BASH, 'يتطلب اختبار الصدفة Bash')
class BuildToolsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='whisper-build-tools-')
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        self.log = self.path / 'calls.jsonl'
        self.env = {
            'PATH': str(self.path), 'CALL_LOG': str(self.log),
            'FAKE_BIN': str(self.path),
        }
        self.write_tool('timeout', '''#!/bin/sh
printf '["timeout","%s"]\\n' "$1" >> "$CALL_LOG"
shift
exec "$@"
''')
        self.write_tool('dpkg', '''#!/bin/sh
printf '["dpkg"]\\n' >> "$CALL_LOG"
exit 1
''')
        self.write_tool('sudo', f'#!{sys.executable}\n' + '''import json, os, pathlib, sys
args = sys.argv[1:]
with open(os.environ['CALL_LOG'], 'a') as log:
    log.write(json.dumps(['sudo'] + args) + '\\n')
if args[:2] == ['apt-get', 'update']:
    sys.exit(int(os.environ.get('UPDATE_RC', '0')))
if args[:2] != ['apt-get', 'install']:
    sys.exit(91)
rc = int(os.environ.get('INSTALL_RC', '0'))
if rc or os.environ.get('INSTALL_NOOP'):
    sys.exit(rc)
for package, names in [('cmake', ['cmake']),
                       ('build-essential', ['make', 'gcc', 'g++'])]:
    if package not in args:
        continue
    for name in names:
        p = pathlib.Path(os.environ['FAKE_BIN']) / name
        p.write_text('#!/bin/sh\\nexit 0\\n')
        p.chmod(0o755)
''')
        for tool in TOOLS:
            self.write_tool(tool)

    def write_tool(self, name, text='#!/bin/sh\nexit 0\n'):
        path = self.path / name
        path.write_text(text, encoding='utf-8')
        path.chmod(0o755)

    def run_helper(self):
        return subprocess.run([BASH, str(HELPER)], env=self.env,
                              capture_output=True, text=True, timeout=10)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] \
            if self.log.exists() else []

    def installs(self):
        return [row for row in self.calls() if row[:3] == ['sudo', 'apt-get', 'install']]

    def test_ready_tools_outside_dpkg_do_not_invoke_apt(self):
        # حالة Ubuntu 26.04: الأدوات تعمل، لكن dpkg لا يعرف CMake.
        self.env['UPDATE_RC'] = '124'
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), [])

    def test_reproduces_old_package_probe_timeout_with_ready_tools(self):
        old = ('for p in cmake build-essential; do dpkg -s $p >/dev/null 2>&1 || '
               '{ timeout 150 sudo apt-get update -qq; '
               'timeout 300 sudo apt-get install -y -qq $p; }; done')
        self.env['UPDATE_RC'] = '124'
        result = subprocess.run([BASH, '-e', '-c', old], env=self.env,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 124)
        self.assertIn(['dpkg'], self.calls())
        self.assertEqual(self.installs(), [])

    def test_missing_cmake_installs_only_cmake(self):
        (self.path / 'cmake').unlink()
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.installs()), 1)
        self.assertEqual(self.installs()[0][-1], 'cmake')
        self.assertNotIn('build-essential', self.installs()[0])

    def test_missing_build_tool_installs_build_essential_once(self):
        for tool in ('make', 'gcc', 'g++'):
            with self.subTest(tool=tool):
                (self.path / tool).unlink()
                self.log.unlink(missing_ok=True)
                result = self.run_helper()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(len(self.installs()), 1)
                self.assertEqual(self.installs()[0][-1], 'build-essential')
                self.assertNotIn('cmake', self.installs()[0])

    def test_all_tools_missing_use_one_bounded_update_and_install(self):
        for tool in TOOLS:
            (self.path / tool).unlink()
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.installs()[0][-2:], ['cmake', 'build-essential'])
        calls = self.calls()
        self.assertEqual([r for r in calls if r[0] == 'timeout'],
                         [['timeout', '150'], ['timeout', '300']])
        self.assertEqual(sum(r[:3] == ['sudo', 'apt-get', 'update'] for r in calls), 1)
        for row in (r for r in calls if r[0] == 'sudo'):
            self.assertIn('Acquire::http::Timeout=20', row)
            self.assertIn('Acquire::https::Timeout=20', row)
            self.assertIn('Acquire::Retries=2', row)

    def test_broken_tool_is_not_treated_as_ready(self):
        self.write_tool('cmake', '#!/bin/sh\nexit 3\n')
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.installs()[0][-1], 'cmake')

    def test_update_failure_stops_before_install(self):
        (self.path / 'cmake').unlink()
        self.env['UPDATE_RC'] = '124'
        result = self.run_helper()
        self.assertEqual(result.returncode, 124)
        self.assertEqual(self.installs(), [])

    def test_install_failure_is_not_hidden(self):
        (self.path / 'gcc').unlink()
        self.env['INSTALL_RC'] = '100'
        self.assertEqual(self.run_helper().returncode, 100)

    def test_successful_package_manager_must_leave_working_tools(self):
        self.write_tool('cmake', '#!/bin/sh\nexit 3\n')
        self.env['INSTALL_NOOP'] = '1'
        result = self.run_helper()
        self.assertEqual(result.returncode, 1)
        self.assertIn('cmake', result.stderr)


class RealignBuildWorkflowTests(unittest.TestCase):
    def test_builder_dependency_check_only_runs_on_whisper_cache_miss(self):
        workflow = yaml.load((ROOT / '.github/workflows/realign_surah.yml')
                             .read_text(encoding='utf-8'), Loader=yaml.BaseLoader)
        steps = workflow['jobs']['realign']['steps']
        call = 'bash tools/ci_fleet/ensure_whisper_build_tools.sh'
        builders = [s for s in steps if call in s.get('run', '')]
        self.assertEqual(len(builders), 1)
        builder = builders[0]
        self.assertEqual(builder['if'], "steps.whisper-cache.outputs.cache-hit != 'true'")
        self.assertLess(builder['run'].index(call), builder['run'].index('git fetch'))
        cache = next(s for s in steps if s.get('id') == 'whisper-cache')
        self.assertEqual(cache['uses'], 'actions/cache/restore@v4')
        self.assertLess(steps.index(cache), steps.index(builder))
        system = next(s['run'] for s in steps if s.get('name') == 'أدوات النظام')
        self.assertNotIn('dpkg', system)
        self.assertNotIn('apt-get', system)
        self.assertIn('QA_FFMPEG_APT_ONLY=1 python tools/ci_fleet/install_qa_ffmpeg.py', system)
        self.assertIn('-DGGML_NATIVE=OFF', builder['run'])


if __name__ == '__main__':
    unittest.main()
