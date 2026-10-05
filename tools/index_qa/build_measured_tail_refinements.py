"""Offline proposals for five terminal clipping findings, preserving all other data.

Free token emissions and full-EOF target diagnostics support the changed ends.
Model disagreements and LOW scores remain visible; fresh QA is mandatory.
"""
import copy
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys
import unicodedata
sys.path.insert(0,str(Path(__file__).resolve().parent))
import stage_transform as T
ROOT=Path(__file__).resolve().parents[2]
DIAG='fb06b3e2173a9472017f30608d36268dc13b36b97c012ad8520f4d44ff0d1ae8'
BUNDLE='29e67d2840d61adfb565b13a21aefb8728ca7de966bb495a003b30815a6345ff'
FIRST='ed849b75af2fb1a5d0b0231096439a9cb08c6ec585a3fcfedd6fdba4e551d9b3'
PLAN='a6560d3ba1c6da054bf95acee4cbadcba407734cd3aa83c6e668e90dbfa085b4'
WORDS={'derini_warsh-s11':'تعملون','derini_warsh-s23':'الراحمين','derini_warsh-s83':'يفعلون','f_khamery-s6':'رحيم','zahrani-s6':'رحيم'}
OLD_ENDS={'derini_warsh-s11':3055138,'derini_warsh-s23':1686350,'derini_warsh-s83':308661,'f_khamery-s6':2664448,'zahrani-s6':5033038}
NEW_ENDS={'derini_warsh-s11':3058000,'derini_warsh-s23':1688400,'derini_warsh-s83':311500,'f_khamery-s6':2665900,'zahrani-s6':5044600}


def need(ok,msg):
    if not ok:raise ValueError(msg)


def read(path,sha,compressed=False):
    b=(ROOT/path).read_bytes();need(hashlib.sha256(b).hexdigest()==sha,'input digest mismatch: '+path)
    return json.loads(gzip.decompress(b) if compressed else b)


def verify_records(records):
    for r in records:
        raw=json.dumps(r['payload'],ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
        need(len(raw)==r['bytes'] and hashlib.sha256(raw).hexdigest()==r['sha256'],'raw frame envelope changed')


def terminal_observations(source,records,models):
    vocab={v:k for k,v in next(m['vocabulary'] for m in models if m['name']=='quran').items()}
    selected={}
    for r in records:
        p=r['payload']
        if 'rawChunk' not in p or p['model']!='quran' or p['sourceSha256']!=source['sha256']:continue
        ch=p['channel'];c=p['rawChunk']
        if ch not in selected or c['chunk']>selected[ch]['payload']['rawChunk']['chunk']:selected[ch]=r
    need(set(selected)=={'native-1','native-2'},'both native channels required')
    observations=[]
    for ch,r in selected.items():
        p=r['payload'];c=p['rawChunk']
        text=''.join(x for x in unicodedata.normalize('NFKD',c['text']) if unicodedata.category(x)!='Mn')
        need(text.rstrip().endswith(WORDS[source['id']]),'terminal word not freely decoded')
        runs=[x for x in c['argmaxRuns'] if x[0]>4]
        letters=[x for x in runs if unicodedata.category(vocab[x[0]]).startswith('L')]
        need(letters and vocab[letters[-1][0]]==WORDS[source['id']][-1] and letters[-1][4]>=.95,'weak or absent final consonant')
        g=c['frameTiming']
        def at(f):return 1000*(c['absoluteInputStartSeconds']+(g['firstFrameCenterSample']+f*g['strideSamples'])/16000)
        observations.append({'channel':ch,'rawPartSha256':r['sha256'],'terminalConsonant':vocab[letters[-1][0]],
          'consonantCenterMs':at(letters[-1][1]),'lastTokenCenterMs':at(runs[-1][2]-1),
          'posteriorIsCalibratedConfidence':False})
    return observations


def main():
    diag=read('ops/out/codex-tail-clipping-37389928059.json',DIAG)
    latest=read('ops/out/codex-tail-clipping-37389928059-complete.json.gz',BUNDLE,True)
    original=read('ops/out/codex-final-verse-free-asr-37388055996-complete.json.gz',FIRST,True)
    plan=read('ops/source-repair/codex-tail-clipping-followup-plan-20261005.json',PLAN)
    verify_records(latest);verify_records(original)
    need(diag['measurementComplete'] and not diag['errors'] and len(diag['measurements'])==40,'incomplete diagnostic')
    grouped={}
    for source in plan['sources']:
        rid=source['reciterId'];grouped.setdefault(rid,[]).append(source)
    outputs=[]
    for rid,sources in grouped.items():
        first=sources[0];base=read(first['candidatePath'],first['candidateSha256'],True)
        parent_path=f"ops/source-repair/parents/codex-{first['riwaya']}-{rid}-{first['parentSha256'][:8]}.jz"
        parent=read(parent_path,first['parentSha256'],True);candidate=copy.deepcopy(base);proofs=[]
        entries={e['ayahId']:e for e in candidate['entries']}
        for source in sources:
            need(source['candidateSha256']==first['candidateSha256'],'mixed candidate bases')
            need(base['audioSha256'][source['surah']-1]==source['sha256'],'source mismatch')
            row=entries[source['target']['ayahId']]
            need(row==source['target'] and row['endMs']==OLD_ENDS[source['id']],'old bounds changed')
            records=latest if source['id']=='zahrani-s6' else original
            model_report=diag if source['id']=='zahrani-s6' else next(r['payload'] for r in original if r['prefix']=='FINAL_VERSE_FREE_ASR_REPORT' and any(x['id']==source['id'] for x in r['payload']['sources']))
            frames=terminal_observations(source,records,model_report['models'])
            measurements=[x for x in diag['measurements'] if x['id']==source['id']]
            need(len(measurements)==8 and all(x['sourceSha256']==source['sha256'] for x in measurements),'incomplete target matrix')
            q=[x['entries'][0] for x in measurements if x['model']=='quran']
            need(len(q)==4 and max(e['endMs'] for e in q)-min(e['endMs'] for e in q)<=80,'unstable Quran endpoint')
            need(max(abs(e['startMs']-row['startMs']) for e in q)<=500,'start requires separate repair')
            last=max([e['endMs'] for e in q]+[f['lastTokenCenterMs'] for f in frames])
            end=math.ceil(last/100)*100+200
            need(end==NEW_ENDS[source['id']] and row['endMs']<end<source['decodedDurationSeconds']*1000,'unexpected proposed end or EOF')
            before=copy.deepcopy(row);row['endMs']=end
            proofs.append({'id':source['id'],'before':before,'after':copy.deepcopy(row),'sourceSha256':source['sha256'],
              'terminalFrames':frames,'modelMeasurements':measurements,'qualityClaim':False})
        changes=[(a,b) for a,b in zip(base['entries'],candidate['entries']) if a!=b]
        need(len(changes)==len(sources),'unexpected changed entries')
        for before,after in changes:need({k:v for k,v in before.items() if k!='endMs'}=={k:v for k,v in after.items() if k!='endMs'},'non-end metadata changed')
        proof={'kind':'source-measured-final-end-refinement','qualityClaim':False,'baseCandidateSha256':first['candidateSha256'],
          'diagnosticReportSha256':DIAG,'rawBundleSha256':BUNDLE,'initialFreeBundleSha256':FIRST,
          'endRule':'ceil(max(Quran target endpoints, free terminal token center)/100ms)*100ms + 200ms',
          'changes':proofs,'limits':['Disagreements and low diagnostic confidence preserved; not a passing two-model certificate.','Original confidence is unchanged; all final-SHA post-stage QA must run again.']}
        tr=candidate['transform'];tr['sameSourceRepair']['tailRefinement']=proof
        tr['entriesSha256']=T.entries_sha(candidate['entries']);tr['parentEntriesSha256']=T.entries_sha(parent['entries'])
        moved,added,removed=T.entry_change_counts(parent['entries'],candidate['entries']);tr.update(movedEntries=moved,addedEntries=added,removedEntries=removed)
        need(tr['fromSha256']==first['parentSha256'],'parent chain changed')
        why=T.promote.index_gate(candidate,parent=parent,parent_sha=first['parentSha256']);need(not why,str(why))
        import run as R
        fatal,warn,info=R.structural(candidate,'timings/'+first['riwaya']+'/'+rid+'.jz',False)
        need(not fatal,str(fatal));need(len(candidate['entries'])==6236,'entry count changed')
        path=f'ops/source-repair/candidates/codex-{rid}-tail-refined-20261005-v2.jz'
        b=gzip.compress(json.dumps(candidate,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode(),mtime=0)
        with (ROOT/path).open('xb') as f:f.write(b)
        outputs.append({'reciterId':rid,'riwaya':first['riwaya'],'path':path,'sha256':hashlib.sha256(b).hexdigest(),
          'parentKey':tr['fromKey'],'parentSha256':first['parentSha256'],'changedFinalEnds':len(changes),'structuralFatal':fatal,'structuralWarnings':warn,'proof':proof})
    out=ROOT/'ops/out/codex-five-tail-refinements-20261005.json'
    with out.open('x') as f:json.dump(outputs,f,ensure_ascii=False,indent=2)
    print(json.dumps([{k:v for k,v in r.items() if k!='proof'} for r in outputs],ensure_ascii=False))

if __name__=='__main__':main()
