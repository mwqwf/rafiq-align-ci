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
                    'changes': {'11:20': {'endMs':454502}, '11:21': {'startMs':454502}, '11:94': {'endMs':1960033}, '11:95': {'startMs':1960033}, '11:117': {'endMs': 2320730}, '11:118': {'startMs': 2320730}}},
    'm_abdulkareem_warsh': {'surah': 21, 'target': '21:48', 'start': 639760, 'end': 650789,
                    'changes': {'21:26': {'endMs':327950}, '21:27': {'startMs':327950,'endMs':335156}, '21:28': {'startMs':335156}, '21:35': {'endMs':451280}, '21:36': {'startMs':451280}, '21:92': {'endMs':1201170}, '21:93': {'startMs':1201170,'endMs':1210358}, '21:94': {'startMs':1210358}, '21:47': {'endMs': 639760}, '21:48': {'startMs': 639760, 'endMs': 650789},
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
    follow=checked('ops/out/codex-source-context-37395546994-and-37395853329-reports.json', 'cefb8f1d30cae7276120f2e6d6bd6e8286ab85f87ff47394d2c237afe6978d7b')
    raw_follow=checked('ops/out/codex-source-context-37395546994-and-37395853329-complete.json.gz', 'bfcba41a35343a69709510858aa49b0899a01ba17f71eee3f1452911045d2ca3',True)
    for rec in raw_follow:
        b=json.dumps(rec['payload'],ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
        C.require(len(b)==rec['bytes'] and hashlib.sha256(b).hexdigest()==rec['sha256'],'followup raw evidence changed')
    follow_targets={'koshi_warsh': [('koshi20_22','11:21',454502),('koshi94_96','11:95',1960033)],
      'm_abdulkareem_warsh':[('m_ab26_29','21:27',327950),('m_ab26_29','21:28',335156),('m_ab34_37','21:36',451280),('m_ab91_95','21:93',1201170),('m_ab91_95','21:94',1210358)]}
    result=[]
    for rid, plan in PLANS.items():
        rep=next(r for r in reports if r['reader']==rid)
        C.require(rep['measurementComplete'] and not rep['errors'], 'incomplete source measurement')
        source=rep['source']; sha=source['parentSha256']; s=plan['surah']; key=f'timings/warsh/{rid}.jz'
        parent=checked(f'ops/source-repair/parents/codex-warsh-{rid}-{sha[:8]}.jz',sha,True)
        C.require(parent['riwaya']=='warsh' and parent['reciterId']==rid and parent['audioSha256'][s-1]==source['sha256'], 'identity/source mismatch')
        follow_proofs=[]
        for ident,aid,start in follow_targets[rid]:
            f=next(r for r in follow if r['reader']==ident)
            C.require(f['measurementComplete'] and not f['errors'] and f['source']['sha256']==source['sha256'],'follow source mismatch')
            ms=f['measurements'];C.require({(m['model'],m['channel']) for m in ms}=={(m,c) for m in ('generic','quran') for c in ('native-1','native-2')},'missing follow matrix')
            es=[next(e for e in m['rawEntries'] if e['ayahId']==aid) for m in ms]
            C.require(min(e['conf'] for e in es)>=.48 and max(e['startMs'] for e in es)-min(e['startMs'] for e in es)<=550,'weak/disagreeing follow measurement')
            qs=[next(e for e in m['rawEntries'] if e['ayahId']==aid) for m in ms if m['model']=='quran']
            C.require(min(e['startMs'] for e in qs)==start and max(e['startMs'] for e in qs)-start<=20,'unmeasured follow boundary')
            C.require(all(e['endMs']>start for e in es),'invalid follow span')
            C.require(len(f['freeResults'])==4 and all(not x['canonicalTextInput'] and not x['forcedAlignment'] for x in f['freeResults']),'free evidence absent')
            follow_proofs.append({'reader':ident,'ayahId':aid,'proposedStartMs':start,'measurements':ms,'provenance':f['provenance']})
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
               'changes':changes,'measurements':matrix,'followupMeasurements':follow_proofs,'followupReportSha256':'cefb8f1d30cae7276120f2e6d6bd6e8286ab85f87ff47394d2c237afe6978d7b','followupRawSha256':'bfcba41a35343a69709510858aa49b0899a01ba17f71eee3f1452911045d2ca3',
               'selection':'Quran-native context starts confirmed by generic/native context and freely decoded speech; adjacent boundary moved consistently.',
               'limits':['Original confidence retained, including LOW.','Only listed bounds changed; entire-surah census and exact-SHA quality gates remain mandatory.','Free frame centers are not calibrated boundary confidence.']}
        tr=C.repaired_transform(parent,candidate,[s],sha,key)
        tr.pop('sourceRepair',None)
        moved,added,removed=T.entry_change_counts(parent['entries'],candidate['entries'])
        C.require(added==removed==0 and moved==len(changes), 'unexpected entry population change')
        tr.update(op=f'ctc_quran_window:{s}',fromSha256=sha,fromKey=key,
                  entriesSha256=T.entries_sha(candidate['entries']),parentEntriesSha256=T.entries_sha(parent['entries']),
                  movedEntries=moved,addedEntries=added,removedEntries=removed,
                  by='build_duration_context_repairs_v2',reason='Source-measured repair of collapsed verse boundaries; preserve all unrelated data',
                  unpublishedLocalCandidate=True,sameSourceRepair=proof)
        candidate['transform']=tr
        C.require(not T.promote.index_gate(candidate,parent=parent,parent_sha=sha),'index gate failed')
        fatal,warnings,info=R.structural(candidate,key,False);C.require(not fatal,str(fatal))
        C.require(str(s) in T.promote.census_surahs(candidate),'changed surah escaped census')
        path=f'ops/source-repair/candidates/codex-{rid}-context-repair-v2-20261006.jz'
        b=gzip.compress(json.dumps(candidate,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode(),mtime=0)
        p=ROOT/path
        if p.exists(): C.require(p.read_bytes()==b,'existing output differs')
        else: p.write_bytes(b)
        result.append({'reciterId':rid,'riwaya':'warsh','path':path,'sha256':hashlib.sha256(b).hexdigest(),
                       'parentKey':key,'parentSha256':sha,'op':tr['op'],'changedEntries':moved,'structuralFatal':fatal,'structuralWarnings':warnings,'proof':proof})
    (ROOT/'ops/out/codex-two-duration-context-repairs-v2-20261006.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps([{k:v for k,v in r.items() if k!='proof'} for r in result],ensure_ascii=False))


if __name__=='__main__':main()
