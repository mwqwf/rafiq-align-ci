"""Offline proposals from pinned native opener evidence; no publication or confidence upgrade."""
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
REPORT = 'ops/out/codex-short-openers-37399039017-reports.json'
REPORT_SHA = 'd7f32ae6737470c6fefc78115cd70f2dca3606e40659edcf90f32cd3488d575f'
BUNDLE = 'ops/out/codex-short-openers-37399039017-complete.json.gz'
BUNDLE_SHA = 'cb3fdc970c6edd70869d2b95ae5e9160096c06600726b8c96cce39480bacd2ee'

def checked(path, sha, compressed=False):
    b=(ROOT/path).read_bytes()
    C.require(hashlib.sha256(b).hexdigest()==sha, 'input digest mismatch: '+path)
    return json.loads(gzip.decompress(b) if compressed else b)

def main():
    reports=checked(REPORT,REPORT_SHA)
    raw=checked(BUNDLE,BUNDLE_SHA,True)
    for record in raw:
        b=json.dumps(record['payload'],ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
        C.require(len(b)==record['bytes'] and hashlib.sha256(b).hexdigest()==record['sha256'],'raw evidence changed')
    result=[]
    for rid in ('hatem','mukhtar_haj','rabbani_warsh'):
        selected=[r for r in reports if r['source']['reciterId']==rid]
        src=selected[0]['source'];sha=src['parentSha256'];key=src['parentKey']
        parent=checked(f'ops/source-repair/parents/codex-opener-{rid}-{sha[:8]}.jz',sha,True)
        C.require(parent['reciterId']==rid and parent['riwaya']==src['riwaya'],'parent identity mismatch')
        candidate=copy.deepcopy(parent);rows={e['ayahId']:e for e in candidate['entries']}
        changes=[];surahs=[];proofs=[]
        for rep in selected:
            source=rep['source'];s=source['surah'];surahs.append(s)
            C.require(rep['measurementComplete'] and not rep['errors'] and source['parentSha256']==sha,'incomplete/stale measurement')
            C.require(parent['audioSha256'][s-1]==source['sha256'],'audio identity mismatch')
            C.require([rows[e['ayahId']] for e in source['parentEntries']]==source['parentEntries'],'parent context changed')
            ms=rep['measurements']
            C.require({(m['model'],m['channel']) for m in ms}=={(m,c) for m in ('generic','quran') for c in ('native-1','native-2')},'missing matrix')
            C.require(len(rep['freeResults'])==4 and all(not x['canonicalTextInput'] and not x['forcedAlignment'] for x in rep['freeResults']),'missing free evidence')
            qs=[m for m in ms if m['model']=='quran']
            starts=[]
            for i in range(3):
                es=[m['rawEntries'][i] for m in ms]
                C.require(all(e['ayahId']==f'{s}:{i+1}' for e in es),'wrong verse measurement')
                C.require(max(e['startMs'] for e in es)-min(e['startMs'] for e in es)<=300,'disagreeing start')
                C.require(min(m['rawEntries'][i]['conf'] for m in qs)>=.45,'weak Quran context')
                starts.append(min(m['rawEntries'][i]['startMs'] for m in qs))
            C.require(max(abs(rows[f'{s}:1']['startMs']-starts[0]),abs(rows[f'{s}:1']['endMs']-starts[1]))>1500,'not the diagnosed displaced opener')
            for i in range(1 if rid=='hatem' else 3):
                aid=f'{s}:{i+1}';before=copy.deepcopy(rows[aid]);rows[aid]['startMs']=starts[i]
                if i<2 and rid!='hatem':rows[aid]['endMs']=starts[i+1]
                # All three Kawthar verses were measured through strict decoded EOF.
                if s==108 and i==2:
                    dec=rep['audio']['decoded']
                    C.require(dec['decodedWithoutErrors'] and dec['windowStartSample']==0 and dec['windowEndSampleExclusive']==dec['frames'],'incomplete EOF measurement')
                    eof=dec['frames']*1000//16000
                    C.require(max(m['rawEntries'][2]['endMs'] for m in ms)<eof,'alignment beyond EOF')
                    rows[aid]['endMs']=eof
                C.require(rows[aid]['startMs']<rows[aid]['endMs'],'invalid repaired interval')
                # Retained ends must cover measured speech; connected new boundaries remain proposals for fresh QA.
                if i==2 or rid=='hatem':
                    C.require(rows[aid]['endMs']>=max(m['rawEntries'][i]['endMs'] for m in ms),'retained end would clip measured speech')
                if rows[aid]!=before:changes.append({'before':before,'after':copy.deepcopy(rows[aid])})
            candidate.setdefault('engineBySurah',{})[str(s)]='ctc-quran-window-1'
            model=copy.deepcopy(qs[0]['alignmentModel']);model['canonicalTextChanged']=False
            candidate.setdefault('alignmentModelBySurah',{})[str(s)]=model
            proofs.append({'reader':rep['reader'],'sourceSha256':source['sha256'],'provenance':rep['provenance'],'measurements':ms})
        changed={x['before']['ayahId'] for x in changes}
        C.require([e for e in parent['entries'] if e['ayahId'] not in changed]==[e for e in candidate['entries'] if e['ayahId'] not in changed],'unrelated entry changed')
        for c in changes:
            strip=lambda e:{k:v for k,v in e.items() if k not in ('startMs','endMs')}
            C.require(strip(c['before'])==strip(c['after']),'confidence/source changed')
        tr=C.repaired_transform(parent,candidate,surahs,sha,key);tr.pop('sourceRepair',None)
        moved,added,removed=T.entry_change_counts(parent['entries'],candidate['entries'])
        C.require(moved==len(changes) and added==removed==0,'population change')
        proof={'qualityClaim':False,'reportPath':REPORT,'reportSha256':REPORT_SHA,'rawBundlePath':BUNDLE,'rawBundleSha256':BUNDLE_SHA,'changes':changes,'measurements':proofs,'limits':['Original confidence, including LOW and zero, is unchanged.','Independent full-surah census and exact-SHA quality gates are required.','Free CTC outputs are supporting evidence, not calibrated certainty.']}
        tr.update(op='ctc_quran_window:'+','.join(map(str,sorted(surahs))),fromSha256=sha,fromKey=key,entriesSha256=T.entries_sha(candidate['entries']),parentEntriesSha256=T.entries_sha(parent['entries']),movedEntries=moved,addedEntries=0,removedEntries=0,by='build_short_opener_repairs_second_batch',reason='Restore measured surah beginnings and adjacent boundaries from unchanged audio',unpublishedLocalCandidate=True,sameSourceRepair=proof)
        candidate['transform']=tr
        C.require(not T.promote.index_gate(candidate,parent=parent,parent_sha=sha),'index gate failed')
        fatal,warnings,info=R.structural(candidate,key,False);C.require(not fatal,str(fatal))
        C.require(set(map(str,surahs))<=T.promote.census_surahs(candidate),'changed surah escaped census')
        path=f'ops/source-repair/candidates/codex-{rid}-opener-repair-20261006.jz'
        b=gzip.compress(json.dumps(candidate,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode(),mtime=0)
        p=ROOT/path
        if p.exists():C.require(p.read_bytes()==b,'existing candidate differs')
        else:p.write_bytes(b)
        result.append({'reciterId':rid,'riwaya':parent['riwaya'],'path':path,'sha256':hashlib.sha256(b).hexdigest(),'parentKey':key,'parentSha256':sha,'op':tr['op'],'changedEntries':moved,'structuralFatal':fatal,'structuralWarnings':warnings,'proof':proof})
    (ROOT/'ops/out/codex-opener-second-batch-repairs-20261006.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps([{k:v for k,v in r.items() if k!='proof'} for r in result],ensure_ascii=False))

if __name__=='__main__':main()
