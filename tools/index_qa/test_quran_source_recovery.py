import json
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
        self.assertIsNone(
            recovery.require_source_engine_eligible(
                recovery.SOURCES['fakhfakh38_archive_2025']))

    def test_recorded_exact_source_fails_with_its_run_not_a_none_subscript(self):
        run = recovery.source_engine_blocked(
            recovery.SOURCES['shamrani79'])['run']
        with self.assertRaisesRegex(
                recovery.S.metadata.ProbeError,
                rf'exact source/engine already failed.*{run}'):
            recovery.require_source_engine_eligible(
                recovery.SOURCES['shamrani79'])

    def test_fakhfakh_archive_mirror_is_pinned_to_publisher_pcm(self):
        source = recovery.SOURCES['fakhfakh38_archive_2025']
        self.assertEqual(source['surah'], 38)
        self.assertEqual(source['riwaya'], 'qalun')
        self.assertEqual(
            source['sha256'],
            'fded733764386de895b63df4b067f44accee12186785396a3f61928a0fa3c212')
        self.assertIsNone(recovery.source_engine_blocked(source))
        audit = json.loads((recovery.B.ROOT / 'ops/source-repair/fakhfakh-qalun-38-archive-mirror-audit-20261006.json').read_text())
        self.assertEqual(source['url'], audit['archive2025Mirror']['url'])
        self.assertEqual(
            audit['archive2025Mirror']['decodedMono16k']['sha256'],
            audit['publisherSource']['decodedMono16k']['sha256'])
        self.assertTrue(audit['comparisons']['archive2025PublisherPcmBytesEqual'])


if __name__ == '__main__':
    unittest.main()
