"""اختبار عقد النبض دون اتصال بالدلو أو إطلاق عمل إنتاجي."""
import ast
from pathlib import Path
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


if __name__ == '__main__':
    unittest.main()
