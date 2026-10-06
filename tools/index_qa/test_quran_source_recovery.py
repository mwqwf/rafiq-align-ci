import unittest

import quran_source_recovery as recovery


class BlockedSourceEngineTests(unittest.TestCase):
    def test_exact_failed_shamrani_sources_are_blocked(self):
        for source_id in ('shamrani79', 'shamrani_new_archive_s79'):
            row = recovery.source_engine_blocked(recovery.SOURCES[source_id])
            self.assertIsNotNone(row)
            self.assertEqual(row['engine'], recovery.ALIGNMENT_ENGINE)

    def test_other_source_and_changed_engine_remain_eligible(self):
        self.assertIsNone(
            recovery.source_engine_blocked(recovery.SOURCES['iraoui86_surahs_s41']))


if __name__ == '__main__':
    unittest.main()
