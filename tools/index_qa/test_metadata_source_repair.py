import copy
import pathlib
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import stage_transform as T
import source_registry

class SourceMetadataRepairTest(unittest.TestCase):
    def setUp(self):
        self.url = 'https://example.org/001.mp3'
        self.parent = dict(riwaya='hafs', reciterId='reader', audioSha256=['a'*64],
                           entries=[dict(ayahId='1:1', fileRef=self.url, startMs=100, endMs=200, conf=.4)])
        self.candidate = copy.deepcopy(self.parent)
        self.candidate['sourceBySurah'] = {'1': self.url}
        self.registry = patch.object(source_registry, 'registered_source', return_value=dict(url=self.url, audio_sha256='a'*64))
        self.registry.start(); self.addCleanup(self.registry.stop)

    def test_explicit_metadata_only_addition_with_exact_registered_bytes(self):
        self.assertEqual(T.verified_metadata_source_additions(self.parent,self.candidate,'measured'), {'1'})
        self.assertEqual(T.verified_metadata_source_additions(self.parent,self.candidate,None),set())

    def test_timing_confidence_source_hash_identity_or_url_changes_fail(self):
        changes = [lambda x:x['entries'][0].update(startMs=101), lambda x:x['entries'][0].update(conf=.9),
                   lambda x:x['entries'][0].update(fileRef=self.url+'?other'),lambda x:x['audioSha256'].__setitem__(0,'b'*64),
                   lambda x:x.update(reciterId='other'),lambda x:x['sourceBySurah'].update({'1':self.url+'?other'})]
        for change in changes:
            candidate=copy.deepcopy(self.candidate);change(candidate)
            with self.subTest(change=change),self.assertRaises(ValueError):
                T.verified_metadata_source_additions(self.parent,candidate,'measured')

    def test_inherited_declaration_cannot_be_removed(self):
        self.parent['sourceBySurah']={'2':'https://example.org/002.mp3'}
        with self.assertRaises(ValueError):T.verified_metadata_source_additions(self.parent,self.candidate,'measured')

    def test_no_registry_hash_no_proof(self):
        with patch.object(source_registry,'registered_source',return_value=dict(url=self.url)),self.assertRaises(ValueError):
            T.verified_metadata_source_additions(self.parent,self.candidate,'measured')

if __name__=='__main__':unittest.main()
