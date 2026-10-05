"""Offline, unapproved candidate correcting measured clipping at Peshawa 63:11.

The original two-model witness remains rejected. These diagnostic observations
propose new bounds only; no confidence, quality verdict or census is rewritten.
"""
import copy
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import stage_transform as T

BASE = '00fbc75a874d45f80600ccf8f1f7bfe774aae5bffaba89cad3f37eb381997aee'
PARENT = '435095f6f5a9e737854f5fdea9b434d17034b7e58ef15aa9a56b3f948f21f124'
PILOT = '3247788b04216cb02bdf958f5fca0ce05a893b07c76eebd0b3bead44ec1a8cae'
FREE = 'f41beee90c7cd3dc0d729046b661329329f36432ca5b54bffcf598441fa84f5b'
BUNDLE = 'f86ed3e142e7c8b198adcbda4c4ced53f66de71373c380ff8fd970bf9164b8cc'
SOURCE = 'bbfc9570680b5172ad15e417ce0ef5b8aaf8d15e16ec6f12fe46ea1752243301'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read_bound(path, sha, compressed=False):
    raw = Path(path).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == sha, 'input digest mismatch')
    return json.loads(gzip.decompress(raw) if compressed else raw)


def terminal_frames(report, records):
    quran = next(m for m in report['models'] if m['name'] == 'quran')
    vocab = {v: k for k, v in quran['vocabulary'].items()}
    result = []
    for record in records:
        p = record['payload']
        # Every preserved payload must still match its original log envelope.
        raw = json.dumps(p, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
        require(len(raw) == record['bytes'] and hashlib.sha256(raw).hexdigest() == record['sha256'],
                'raw frame envelope mismatch')
        if (record['prefix'] != 'PESHAWA_FREE_ASR_PART' or p['model'] != 'quran'
                or p['windowSeconds'] != [244, 284]):
            continue
        c = p['rawChunk']
        if c['absoluteInputStartSeconds'] != 267:
            continue
        require(p['sourceSha256'] == SOURCE and p['canonicalTextInput'] is False
                and p['forcedAlignment'] is False, 'not unprompted source evidence')
        text = ''.join(x for x in unicodedata.normalize('NFKD', c['text'])
                       if unicodedata.category(x) != 'Mn')
        require(text.rstrip().endswith('تعملون'), 'terminal word not decoded')
        runs = [r for r in c['argmaxRuns'] if r[0] != c['blankTokenId']]
        require(runs and all(r[4] >= .95 for r in runs[-2:]), 'weak terminal token emission')
        require(vocab[runs[-2][0]] == 'ن', 'missing terminal nun')
        geometry = c['frameTiming']
        def ms(frame):
            return 1000 * (267 + (geometry['firstFrameCenterSample']
                                 + frame * geometry['strideSamples']) / 16000)
        result.append({'channel': p['channel'], 'partSha256': record['sha256'],
                       'lastTokenCenterMs': ms(runs[-1][2] - 1),
                       'terminalNunCenterMs': ms(runs[-2][1]),
                       'posteriorIsCalibratedConfidence': False})
    require({x['channel'] for x in result} == {'native-1', 'native-2'} and len(result) == 2,
            'both native channel observations required')
    return result


def propose(base, parent, pilot, report, records):
    require(base['reciterId'] == 'peshawa' and base['riwaya'] == 'hafs'
            and base['audioSha256'][62] == SOURCE, 'candidate source mismatch')
    require(report['ok'] is True and report['source']['sha256'] == SOURCE
            and report['canonicalTextRead'] is False and report['forcedAlignment'] is False
            and report['audio']['decoded']['decodedWithoutErrors'] is True,
            'free diagnostic incomplete')
    require(pilot['candidate']['sha256'] == BASE and pilot['errors'] == []
            and pilot['pilotBoundariesVerified'] is False, 'original failed witness not preserved')
    q = pilot['rows']['63:11']['proof']['models']['quran']['rawEntries'][-1]
    require(q['ayahId'] == '63:11' and q['conf'] >= .60 and q['startMs'] == 264706,
            'unexpected independent diagnostic start')
    frames = terminal_frames(report, records)
    start = q['startMs']
    end = math.ceil(max(x['lastTokenCenterMs'] for x in frames) / 100) * 100 + 200
    require(end == 282300 and end < report['audio']['decoded']['durationSeconds'] * 1000,
            'unexpected terminal frame or EOF')
    revised = copy.deepcopy(base)
    rows = {e['ayahId']: e for e in revised['entries']}
    require((rows['63:10']['endMs'], rows['63:11']['startMs'], rows['63:11']['endMs'])
            == (266091, 266091, 279139), 'base boundary differs')
    rows['63:10']['endMs'] = rows['63:11']['startMs'] = start
    rows['63:11']['endMs'] = end
    changes = []
    for before, after in zip(base['entries'], revised['entries']):
        if before != after:
            require(before['ayahId'] in ('63:10', '63:11'), 'unrelated entry changed')
            require({k: v for k, v in before.items() if k not in ('startMs', 'endMs')}
                    == {k: v for k, v in after.items() if k not in ('startMs', 'endMs')},
                    'confidence, source or entry metadata changed')
            changes.append({'before': before, 'after': after})
    proof = {'kind': 'diagnostic-tail-boundary-proposal', 'qualityClaim': False,
             'independentWindowWitnessStillRejected': True, 'sourceSha256': SOURCE,
             'baseLocalCandidateSha256': BASE, 'originalParentSha256': PARENT,
             'pilotReportSha256': PILOT, 'freeAsrReportSha256': FREE,
             'rawFrameBundleSha256': BUNDLE, 'freeAsrRun': '37386012711',
             'startRule': 'Quran diagnostic raw start from full previous-verse context; not a passing dual witness',
             'endRule': 'ceil(last Quran token frame center / 100ms)*100ms + 200ms proposal padding',
             'terminalFrames': frames, 'changes': changes,
             'limits': ['Native channels share one Quran model; not independent model agreement',
                        'CTC frame posteriors are not calibrated boundary confidence',
                        'Candidate requires fresh audio QA and tail verification before adoption']}
    tr = revised['transform']
    tr['sourceRepair']['tailCorrection'] = proof
    tr['entriesSha256'] = T.entries_sha(revised['entries'])
    tr['parentEntriesSha256'] = T.entries_sha(parent['entries'])
    moved, added, removed = T.entry_change_counts(parent['entries'], revised['entries'])
    tr.update(movedEntries=moved, addedEntries=added, removedEntries=removed,
              by='build_registered_candidate + diagnostic-tail-refinement',
              note='Unpublished local candidate; failed original witness retained; new quality and tail checks mandatory')
    require(tr['fromSha256'] == PARENT and tr['fromKey'] == 'timings/hafs/peshawa.jz',
            'published parent changed')
    reason = T.promote.index_gate(revised, parent=parent, parent_sha=PARENT)
    require(not reason, 'index gate: ' + str(reason))
    return revised, proof


def main():
    base = read_bound(ROOT/'ops/source-repair/candidates/codex-peshawa-s63-20261005-v2.jz', BASE, True)
    parent = read_bound(ROOT/'ops/source-repair/parents/codex-peshawa-435095f6.jz', PARENT, True)
    pilot = read_bound(ROOT/'ops/out/codex-peshawa-pilot-37383250194.json', PILOT)
    report = read_bound(ROOT/'ops/out/codex-peshawa-tail-free-asr-37386012711.json', FREE)
    records = read_bound(ROOT/'ops/out/codex-peshawa-tail-free-asr-37386012711-complete.json.gz', BUNDLE, True)
    revised, proof = propose(base, parent, pilot, report, records)
    target = ROOT/'ops/source-repair/candidates/codex-peshawa-s63-20261005-v3.jz'
    payload = gzip.compress(json.dumps(revised, ensure_ascii=False, separators=(',', ':'),
                                      allow_nan=False).encode(), mtime=0)
    with target.open('xb') as f:
        f.write(payload)
    proof.update(candidatePath=str(target.relative_to(ROOT)), candidateSha256=hashlib.sha256(payload).hexdigest())
    with (ROOT/'ops/out/codex-peshawa-tail-correction-20261005.json').open('x') as f:
        json.dump(proof, f, ensure_ascii=False, indent=2)
    print(json.dumps({'candidate': proof['candidatePath'], 'sha256': proof['candidateSha256'],
                      'qualityClaim': False, 'changedEntries': len(proof['changes'])}))


if __name__ == '__main__':
    main()
