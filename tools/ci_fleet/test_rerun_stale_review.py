import copy
import unittest
from tools.ci_fleet.rerun_stale_review import eligible, EXPECTED, REPO


class ReviewRecoveryTest(unittest.TestCase):
    def setUp(self):
        self.sha = 'a' * 40
        self.key = 'timings-staging/hafs/s_sadeiq.927e8bbe.jz'
        self.run = dict(id=123, head_sha=self.sha, event='workflow_dispatch',
            path='.github/workflows/free-post-stage-quality.yml',
            display_title='free-post-stage ' + self.key,
            repository=dict(full_name=REPO, private=False), status='completed',
            conclusion='failure', run_attempt=1)
        self.jobs = [dict(name=n, status='completed',
            conclusion='failure' if n == 'review' else 'success') for n in EXPECTED]
        self.log = 'تشخيص الكتالوج يصف فهرساً آخر؛ الحراس الأصلية لم تقبل أهلية الترقية'

    def accepted(self):
        return eligible(self.run, self.jobs, self.log, 123, self.sha, self.key)

    def test_only_matching_review(self):
        self.assertTrue(self.accepted())
        self.run['head_sha'] = 'b' * 40
        self.assertFalse(self.accepted())

    def test_no_retry_audio_failure(self):
        next(j for j in self.jobs if j['name'] == 'heard')['conclusion'] = 'failure'
        self.assertFalse(self.accepted())

    def test_no_other_failure_or_repeated_retry(self):
        self.log = 'other failure'
        self.assertFalse(self.accepted())
        self.log = 'تشخيص الكتالوج يصف فهرساً آخر؛ الحراس الأصلية لم تقبل أهلية الترقية'
        self.run['run_attempt'] = 2
        self.assertFalse(self.accepted())

    def test_public_pinned_workflow_only(self):
        for field, value in [('repository', dict(full_name=REPO, private=True)),
                             ('path', '.github/workflows/align.yml'),
                             ('display_title', 'different')]:
            old = copy.deepcopy(self.run)
            self.run[field] = value
            self.assertFalse(self.accepted())
            self.run = old
        self.jobs.append(dict(name='extra', status='completed', conclusion='success'))
        self.assertFalse(self.accepted())


if __name__ == '__main__':
    unittest.main()
