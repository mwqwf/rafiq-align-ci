"""حجز مرشح واحد عن الإطلاق التقليدي، مع بقاء سلوك المرشحين الآخرين والحراس."""
import ast
import copy
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch

from tools.ci_fleet.qa_dispatch_guard import manual_qa_reason, manual_qa_policy, MANUAL_QA_REASON

ROOT = Path(__file__).resolve().parents[2]
SHA = 'a' * 64
KEY = 'timings-staging/hafs/peshawa.12345678.jz'
LIVE = 'timings/hafs/peshawa.jz'


def candidate(marked=True, reciter='peshawa'):
    index = {'riwaya': 'hafs', 'reciterId': reciter, 'engineVersion': 'ctc-seg-1',
             'entries': [None] * 11, 'transform': {'fromKey': f'timings/hafs/{reciter}.jz',
                                                'fromSha256': SHA}}
    if marked:
        index['transform']['qaDispatch'] = manual_qa_policy(index, index['transform']['fromKey'], SHA)
    return index


def functions_from(path, names, scope):
    """اختبر دوال الإنتاج نفسها دون استيراد SDK أو تهيئة اعتماد الدلو."""
    tree = ast.parse(path.read_text())
    body = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert len(body) == len(names)
    exec(compile(ast.Module(body=body, type_ignores=[]), str(path), 'exec'), scope)
    return scope


class ManualPolicyTest(unittest.TestCase):
    def test_binding_and_legacy_behavior(self):
        self.assertEqual(manual_qa_reason(candidate(), KEY, SHA), MANUAL_QA_REASON)
        self.assertIsNone(manual_qa_reason(candidate(False), KEY))
        self.assertIsNone(manual_qa_reason(candidate(), LIVE))

    def test_bad_policy_or_parent_identity_stops_only_that_candidate(self):
        mutations = [lambda d: d['transform']['qaDispatch'].update(parentSha256='b' * 64),
                     lambda d: d['transform'].update(fromKey='timings/hafs/other.jz'),
                     lambda d: d['transform'].update(fromSha256=SHA[:8]),
                     lambda d: d.update(reciterId='other'),
                     lambda d: d['transform'].update(qaDispatch=True)]
        for change in mutations:
            item = candidate(); change(item)
            with self.subTest(index=item):
                self.assertIn('لا تطابق', manual_qa_reason(item, KEY))
        self.assertIn('لا تطابق', manual_qa_reason(candidate(), KEY, 'c' * 64))

    def test_factory_rejects_wrong_identity_and_inheritance_requires_opt_in(self):
        index = candidate()
        for parent, sha in (('timings/hafs/other.jz', SHA), (LIVE, SHA[:8])):
            with self.assertRaises(ValueError):
                manual_qa_policy(index, parent, sha)
        from tools.index_qa.stage_transform import apply_dispatch_policy
        old_entries = copy.deepcopy(index['entries'])
        apply_dispatch_policy(index, False, LIVE, SHA)
        self.assertNotIn('qaDispatch', index['transform'])
        apply_dispatch_policy(index, True, LIVE, SHA)
        self.assertEqual(manual_qa_reason(index, KEY, SHA), MANUAL_QA_REASON)
        self.assertEqual(index['entries'], old_entries)


class RestoreDispatchTest(unittest.TestCase):
    def scope(self, include_other):
        other_key = 'timings-staging/hafs/other.abcdef00.jz'
        objects = {KEY: candidate(), LIVE: dict(candidate(False), entries=[None] * 9)}
        staged = [{'Key': KEY, 'LastModified': 2}]
        published = [{'Key': LIVE, 'LastModified': 1}]
        if include_other:
            objects[other_key] = candidate(False, 'other')
            objects['timings/hafs/other.jz'] = dict(candidate(False, 'other'), entries=[None] * 9)
            staged.append({'Key': other_key, 'LastModified': 2})
            published.append({'Key': 'timings/hafs/other.jz', 'LastModified': 1})
        class Store:
            def get_paginator(self, name):
                return self
            def paginate(self, **args):
                return [{'Contents': published if args['Prefix'] == 'timings/' else staged}]
        dispatched = []
        scope = {'s3': lambda: (Store(), 'bucket'), 'fetch_index': lambda k: (objects[k], SHA),
                 'manual_qa_reason': manual_qa_reason, 'is_partial': lambda k: False,
                 'os': os, 'inflight_reciters': lambda: [], '_salt_count': lambda k: 0,
                 '_struct_fatal': lambda k: None, '_census_due': lambda k: True,
                 '_heard_due': lambda k: True, 'gh': lambda *args: dispatched.append(args)}
        names = ['_staged_improvements', '_who', '_grouped_by_best', 'gate_picks', 'census_keys', 'cmd_gate']
        return functions_from(ROOT / 'tools/ci_fleet/restore_loop.py', names, scope), dispatched

    def test_manual_candidate_never_dispatches_any_of_seven_quality_jobs(self):
        scope, dispatched = self.scope(False)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(scope['_staged_improvements'](), [])
            scope['cmd_gate'](types.SimpleNamespace(limit=12))
        self.assertEqual(dispatched, [])

    def test_unmarked_candidate_keeps_all_existing_dispatches(self):
        scope, dispatched = self.scope(True)
        with redirect_stdout(io.StringIO()):
            scope['cmd_gate'](types.SimpleNamespace(limit=12))
        self.assertEqual([args[2] for args in dispatched],
                         ['splice_census.yml', 'heard_gate.yml', 'openers.yml'] + ['audio_qa.yml'] * 4)
        self.assertTrue(all('peshawa' not in str(args) and 'other.abcdef00' in str(args)
                            for args in dispatched))

    def test_scan_does_not_launch_new_alignment_from_manual_candidate(self):
        scope = {'catalog_bases': lambda: {}, 'catalog_file_tables': lambda: {},
                 'REFS': ['ref1', 'ref2'], 'surah_ends': lambda x: {},
                 'fetch_index': lambda k: (candidate(), SHA), 'inflight_reciters': lambda: [],
                 'candidates': lambda: [{'reciter': 'peshawa', 'riwaya': 'hafs', 'surah': 63,
                                        'key': KEY, 'gap': 2}],
                 'source_base': lambda *a: 'https://example.org/', 'SOURCE_OVERRIDES': {},
                 'blocked_realign': lambda *a: False, 'manual_qa_reason': manual_qa_reason,
                 'source_ratio': lambda *a, **k: self.fail('لا قياس ولا محاذاة تقليدية'),
                 'gh': lambda *a: self.fail('لا إطلاق')}
        functions_from(ROOT / 'tools/ci_fleet/restore_loop.py', ['cmd_scan'], scope)
        with redirect_stdout(io.StringIO()):
            scope['cmd_scan'](types.SimpleNamespace(limit=12))


class OtherSchedulersTest(unittest.TestCase):
    def test_ctc_driver_skips_manual_but_keeps_unmarked_candidate(self):
        path = ROOT / 'tools/ci_fleet/ctc_driver.py'
        tree = ast.parse(path.read_text())
        loop = next(n for n in tree.body if isinstance(n, ast.For)
                    and ast.unparse(n.target) == '(rid, o)')
        other = 'timings-staging/hafs/other.abcdef00.jz'
        docs = {KEY: candidate(), other: candidate(False, 'other')}
        calls, writes = [], []
        scope = {'latest': {'peshawa': {'Key': KEY}, 'other': {'Key': other}},
                 'busy': set(), 'frozen': '', 'get': lambda k: gzip.compress(json.dumps(docs[k]).encode()),
                 'gzip': gzip, 'json': json, 'hashlib': hashlib, 'manual_qa_reason': manual_qa_reason,
                 'state': set(), 'SALTS': ['k1', 'k2', 'k3', 'k4'], 'REPO': 'mwqwf/rafiq-align-ci',
                 'sh': lambda *a: calls.append(a), 's3': types.SimpleNamespace(put_object=lambda **k: writes.append(k)),
                 'B': 'bucket'}
        with redirect_stdout(io.StringIO()):
            exec(compile(ast.Module(body=[loop], type_ignores=[]), str(path), 'exec'), scope)
        self.assertEqual(len(calls), 5)
        self.assertTrue(all('peshawa' not in str(args) for args in calls))
        self.assertEqual(len(writes), 1)
        self.assertIn('other.abcdef00', writes[0]['Key'])

    def test_keepalive_filters_exact_candidate_before_dispatch(self):
        # نفّذ كتلة المصفاة نفسها كما في YAML، دون محاكاة قائمة المخرجات يدوياً.
        text = (ROOT / '.github/workflows/keepalive.yml').read_text()
        start = text.index('          # هذا المرشح وحده')
        end = text.index('          print("need="', start)
        code = '\n'.join(line[10:] for line in text[start:end].splitlines())
        other = 'timings-staging/hafs/other.abcdef00.jz'
        docs = {KEY: candidate(), other: candidate(False, 'other')}
        store = types.SimpleNamespace(get_object=lambda **a: {'Body': io.BytesIO(
            gzip.compress(json.dumps(docs[a['Key']]).encode()))})
        scope = {'batch': [KEY, other], 's': store, 'b': 'bucket', 'sys': sys, 'json': json}
        with redirect_stderr(io.StringIO()):
            exec(code, scope)
        self.assertEqual(scope['batch'], [other])

    def test_keepalive_manual_candidates_do_not_consume_batch_slots(self):
        text = (ROOT / '.github/workflows/keepalive.yml').read_text()
        self.assertIn('batch = sorted(need)\n', text)
        start = text.index('          # هذا المرشح وحده')
        end = text.index('          print("need="', start)
        code = '\n'.join(line[10:] for line in text[start:end].splitlines())
        keys = [f'timings-staging/hafs/r{i}.abcdef00.jz' for i in range(30)]
        docs = {key: candidate(i < 14, f'r{i}') for i, key in enumerate(keys)}
        store = types.SimpleNamespace(get_object=lambda **a: {'Body': io.BytesIO(
            gzip.compress(json.dumps(docs[a['Key']]).encode()))})
        scope = {'batch': keys, 's': store, 'b': 'bucket', 'sys': sys, 'json': json}
        with redirect_stderr(io.StringIO()):
            exec(code, scope)
        self.assertEqual(scope['batch'], keys[14:28])


if __name__ == '__main__':
    unittest.main()
