"""اختبار عقد النبض دون اتصال بالدلو أو إطلاق عمل إنتاجي."""
import ast
import os
from pathlib import Path
import subprocess
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[2]


class KeepaliveContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = yaml.load(
            (ROOT / '.github/workflows/keepalive.yml').read_text(encoding='utf-8'),
            Loader=yaml.BaseLoader,
        )

    def scan(self):
        steps = self.workflow['jobs']['gate_and_promote']['steps']
        body = next(s['run'] for s in steps if s.get('id') == 'scan')
        code = body.split('\n', 1)[1].rsplit('\nPY', 1)[0]
        return ast.parse(code)

    def test_chain_survives_failed_dependency(self):
        chain = self.workflow['jobs']['chain']
        self.assertEqual(set(chain['needs']), {'pulse', 'gate_and_promote'})
        self.assertEqual(chain['if'], '${{ always() }}')
        self.assertGreater(int(chain['timeout-minutes']), 15)
        body = chain['steps'][0]['run']
        self.assertIn('sleep 900', body)
        self.assertIn('gh workflow run keepalive.yml', body)
        self.assertNotIn('||', body)  # فشل الإطلاق لا يتحول إلى نجاح وهمي.
        for step in self.workflow['jobs']['gate_and_promote']['steps']:
            self.assertNotIn('sleep 900', step.get('run', ''))

    def test_missing_queue_or_exclusion_fails_closed(self):
        handlers = [n for n in ast.walk(self.scan()) if isinstance(n, ast.ExceptHandler)]
        self.assertEqual(len(handlers), 2)
        self.assertTrue(all(any(isinstance(n, ast.Raise) for n in h.body) for h in handlers))

    def test_output_lines_are_not_concatenated(self):
        for node in ast.walk(self.scan()):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'print':
                self.assertFalse(any(k.arg == 'end' and isinstance(k.value, ast.Constant)
                                     and k.value.value == '' for k in node.keywords))

    def test_hourly_backup_and_no_parallel_pulses(self):
        self.assertTrue(self.workflow['on']['schedule'])
        self.assertEqual(self.workflow['concurrency']['cancel-in-progress'], 'false')

    def test_wave_size_tracks_live_rows_and_empty_list_does_not_launch(self):
        steps = self.workflow['jobs']['pulse']['steps']
        launch = next(s for s in steps if s.get('name') == 'أطلق موجةً عند الفراغ')
        body = launch['run']
        summary = next(s['run'] for s in steps if s.get('name') == 'خلاصة')
        self.assertEqual(launch['id'], 'launch')
        self.assertIn('ROWS=$(awk', body)
        self.assertIn('[ "$SHARDS" -le 12 ] || SHARDS=12', body)
        self.assertIn('if [ "$ROWS" -eq 0 ]', body)
        self.assertIn('-f shards="$SHARDS"', body)
        self.assertLess(body.index('launched=false'), body.index('if [ "$ROWS" -eq 0 ]'))
        self.assertGreater(body.index('launched=true'), body.index('gh workflow run align.yml'))
        self.assertIn('steps.launch.outputs.launched', summary)
        self.assertIn('لم تُطلق موجة', summary)

    def promotion_script(self):
        steps = self.workflow['jobs']['gate_and_promote']['steps']
        return next(s['run'] for s in steps if s.get('name') == 'رقِّ من عبر')

    def test_promotion_does_not_hide_infrastructure_errors(self):
        script = self.promotion_script()
        self.assertIn('set -euo pipefail', script)
        self.assertNotIn('||', script)
        self.assertIn('python tools/index_qa/promote.py --yes 2>&1 | tail -25', script)

    @unittest.skipIf(os.name == 'nt', 'فحص Bash الفعلي يعمل على عداء Linux السحابي')
    def test_promotion_exit_status_reaches_job_without_touching_r2(self):
        for code in (0, 7):
            with self.subTest(code=code):
                script = self.promotion_script().replace(
                    'python tools/index_qa/promote.py --yes',
                    f'python -c "raise SystemExit({code})"',
                )
                result = subprocess.run(['bash', '-c', script], capture_output=True, timeout=10)
                self.assertEqual(result.returncode, code)


if __name__ == '__main__':
    unittest.main()
