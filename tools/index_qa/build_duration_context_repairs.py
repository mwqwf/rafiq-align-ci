"""Offline, source-pinned boundary proposals; retain confidence and require fresh QA."""
import copy
import gzip
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import stage_transform as T
import build_registered_candidate as C
import run as R

ROOT = Path(__file__).resolve().parents[2]
REPORT_SHA = '11d151b26e8789739a5e0ef22a16f100e1c9357aee547b331735cb123c78f7f3'
BUNDLE_SHA = 'a4a30860ec0c9c5534ceb28c3e4841013d4fad4692e1ba92250802d32751cc58'
PLANS = {
    'koshi_warsh': {'surah': 11, 'target': '11:118', 'start': 2320730, 'end': 2334826,
                    'changes': {'11:117': {'endMs': 2320730}, '11:118': {'startMs': 2320730}}},
    'm_abdulkareem_warsh': {'surah': 21, 'target': '21:48', 'start': 639760, 'end': 650789,
                    'changes': {'21:47': {'endMs': 639760}, '21:48': {'startMs': 639760, 'endMs': 650789},
                                '21:49': {'startMs': 650789}}},
}


def checked(path, sha, compressed=False):
    b=(ROOT/path).read_bytes()
    C.require(hashlib.sha256(b).hexdigest()==sha, 'input digest mismatch: '+path)
    return json.loads(gzip.decompress(b) if compressed else b)


def main():
    reports=checked('ops/out/codex-duration-defects-37391351958-reports.json', REPORT_SHA)
    records=checked('ops/out/codex-duration-defects-37391351958-complete.json.gz', BUNDLE_SHA, True)
    for rec in records:
        b=json.dumps(rec['payload'],ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
        C.require(len(b)==rec['bytes'] and hashlib.sha256(b).hexdigest()==rec['sha256'], 'raw envelope changed')
    result=[]
    for rid, plan in PLANS.items():
        rep=next(r for r in reports if r['reader']==rid)
        C.require(rep['measurementComplete'] and not rep['errors'], 'incomplete source measurement')
        source=rep['source']; sha=source['parentSha256']; s=plan['surah']; key=f'timings/warsh/{rid}.jz'
        parent=checked(f'ops/source-repair/parents/codex-warsh-{rid}-{sha[:8]}.jz',sha,True)
        C.require(parent['riwaya']=='warsh' and parent['reciterId']==rid and parent['audioSha256'][s-1]==source['sha256'], 'identity/source mismatch')
        matrix=rep['measurements']
        C.require({(m['model'],m['channel']) for m in matrix}=={(m,c) for m in ('generic','quran') for c in ('native-1','native-2')}, 'incomplete model/channel matrix')
        target=[next(e for e in m['rawEntries'] if e['ayahId']==plan['target']) for m in matrix]
        C.require(min(e['conf'] for e in target)>=.70, 'weak target diagnostic')
        C.require(max(e['startMs'] for e in target)-min(e['startMs'] for e in target)<=500 and max(e['endMs'] for e in target)-min(e['endMs'] for e in target)<=100, 'models disagree')
        q=[m for m in matrix if m['model']=='quran']
        C.require(all(next(e['startMs'] for e in m['rawEntries'] if e['ayahId']==plan['target'])==plan['start'] for m in q), 'unmeasured start proposal')
        candidate=copy.deepcopy(parent); changes=[]
        rows={e['ayahId']:e for e in candidate['entries']}
        C.require([rows[e['ayahId']] for e in source['contextEntries']]==source['contextEntries'], 'measured parent context changed')
        for aid, fields in plan['changes'].items():
            before=copy.deepcopy(rows[aid]); rows[aid].update(fields)
            C.require(before!=rows[aid] and rows[aid]['endMs']>rows[aid]['startMs'], 'invalid/no-op boundary change')
            changes.append({'before':before,'after':copy.deepcopy(rows[aid])})
        C.require([e for e in parent['entries'] if e['ayahId'] not in plan['changes']]==[e for e in candidate['entries'] if e['ayahId'] not in plan['changes']], 'unrelated entry changed')
        C.require(rows[plan['target']]['startMs']==plan['start'] and rows[plan['target']]['endMs']==plan['end'], 'unexpected target bounds')
        for change in changes:
            strip=lambda e:{k:v for k,v in e.items() if k not in ('startMs','endMs')}
            C.require(strip(change['before'])==strip(change['after']), 'confidence or source changed')
        # Quran context windows are a declared engine change, enforcing whole-surah census.
        candidate.setdefault('engineBySurah',{})[str(s)]='ctc-quran-window-1'
        model=copy.deepcopy(q[0]['alignmentModel']);model['canonicalTextChanged']=False
        candidate.setdefault('alignmentModelBySurah',{})[str(s)]=model
        proof={'kind':'measured-context-boundary-repair','qualityClaim':False,'sourceSha256':source['sha256'],
               'reportSha256':REPORT_SHA,'rawBundleSha256':BUNDLE_SHA,'runId':rep['provenance']['runId'],
               'changes':changes,'measurements':matrix,
               'selection':'Quran-native context starts confirmed by generic/native context and freely decoded speech; adjacent boundary moved consistently.',
               'limits':['Original confidence retained, including LOW.','Only listed bounds changed; entire-surah census and exact-SHA quality gates remain mandatory.','Free frame centers are not calibrated boundary confidence.']}
        tr=C.repaired_transform(parent,candidate,[s],sha,key)
        tr.pop('sourceRepair',None)
        moved,added,removed=T.entry_change_counts(parent['entries'],candidate['entries'])
        C.require(added==removed==0 and moved==len(changes), 'unexpected entry population change')
        tr.update(op=f'ctc_quran_window:{s}',fromSha256=sha,fromKey=key,
                  entriesSha256=T.entries_sha(candidate['entries']),parentEntriesSha256=T.entries_sha(parent['entries']),
                  movedEntries=moved,addedEntries=added,removedEntries=removed,
                  by='build_duration_context_repairs',reason='Source-measured repair of collapsed verse boundaries; preserve all unrelated data',
                  unpublishedLocalCandidate=True,sameSourceRepair=proof)
        candidate['transform']=tr
        C.require(not T.promote.index_gate(candidate,parent=parent,parent_sha=sha),'index gate failed')
        fatal,warnings,info=R.structural(candidate,key,False);C.require(not fatal,str(fatal))
        C.require(str(s) in T.promote.census_surahs(candidate),'changed surah escaped census')
        path=f'ops/source-repair/candidates/codex-{rid}-context-repair-20261006.jz'
        b=gzip.compress(json.dumps(candidate,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode(),mtime=0)
        p=ROOT/path
        if p.exists(): C.require(p.read_bytes()==b,'existing output differs')
        else: p.write_bytes(b)
        result.append({'reciterId':rid,'riwaya':'warsh','path':path,'sha256':hashlib.sha256(b).hexdigest(),
                       'parentKey':key,'parentSha256':sha,'op':tr['op'],'changedEntries':moved,'structuralFatal':fatal,'structuralWarnings':warnings,'proof':proof})
    (ROOT/'ops/out/codex-two-duration-context-repairs-20261006.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps([{k:v for k,v in r.items() if k!='proof'} for r in result],ensure_ascii=False))


if __name__=='__main__':main()
