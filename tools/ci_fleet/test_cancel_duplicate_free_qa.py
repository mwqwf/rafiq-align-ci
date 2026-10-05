import copy
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cancel_duplicate_free_qa as C


class DuplicateTests(unittest.TestCase):
    def runs(self):
        common = {'path': C.WORKFLOW, 'display_title': C.TITLE, 'event': 'workflow_dispatch',
                  'repository': {'full_name': C.REPO, 'private': False}}
        return ({**copy.deepcopy(common), 'id': C.ORIGINAL, 'status': 'in_progress', 'created_at': '2026-10-05T22:00:00Z'},
                {**copy.deepcopy(common), 'id': C.DUPLICATE, 'status': 'pending', 'created_at': '2026-10-05T22:01:00Z'})

    def test_only_identified_unstarted_duplicate_with_live_original_is_eligible(self):
        original, duplicate = self.runs()
        self.assertTrue(C.eligible(original, duplicate, []))
        for field, value in [('id', C.ORIGINAL), ('path', '.github/workflows/other.yml'),
                             ('display_title', 'different'), ('status', 'in_progress')]:
            changed = {**duplicate, field: value}
            self.assertFalse(C.eligible(original, changed, []))
        self.assertFalse(C.eligible({**original, 'status': 'completed', 'conclusion': 'failure'}, duplicate, []))
        self.assertFalse(C.eligible(original, duplicate, [{'status': 'in_progress'}]))
        self.assertFalse(C.eligible(original, duplicate, [{'status': 'completed'}]))


if __name__ == '__main__':
    unittest.main()
