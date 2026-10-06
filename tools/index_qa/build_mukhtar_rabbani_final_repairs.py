"""Offline, source-bound repairs from native contexts; original confidence retained."""
import argparse,copy,gzip,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_registered_candidate as C
import stage_transform as T
import run as R
ROOT=Path(__file__).resolve().parents[2]

def checked(path,sha):
    b=(ROOT/path).read_bytes();C.require(hashlib.sha256(b).hexdigest()==sha,'changed input '+path)
    return json.loads(gzip.decompress(b) if path.endswith(('.jz','.gz')) else b)

def evidence(name,report_sha,raw_sha):
    rp=f'ops/out/codex-{name}-20261006.json';bp=f'ops/out/codex-{name}-20261006-complete.json.gz'
    reports=checked(rp,report_sha);raw=checked(bp,raw_sha)
    for r in raw:
        b=json.dumps(r['payload'],ensure_ascii=False,separators=(',',':')).encode()
        C.require(len(b)==r['bytes'] and hashlib.sha256(b).hexdigest()==r['sha256'],'raw evidence changed')
    return reports,raw,{'reports':rp,'reportsSha256':report_sha,'raw':bp,'rawSha256':raw_sha}

def check_report(rep,parent):
    src=rep['source'];s=src['surah']
    C.require(rep['measurementComplete'] and not rep['errors'] and src['sha256']==parent['audioSha256'][s-1] and src['riwaya']==parent['riwaya'],'source/evidence mismatch')
    C.require({(m['model'],m['channel']) for m in rep['measurements']}=={(m,c) for m in ('generic','quran') for c in ('native-1','native-2')},'missing native matrix')
    C.require(len(rep['freeResults'])==4 and all(not m['forcedAlignment'] and not m['canonicalTextInput'] for m in rep['freeResults']),'missing independent free evidence')

def main(argv=None):
    ap=argparse.ArgumentParser();ap.add_argument('--reader',choices=['mukhtar','rabbani'],required=True);a=ap.parse_args(argv)
    reader='mukhtar_haj' if a.reader=='mukhtar' else 'rabbani_warsh';riwaya='hafs' if a.reader=='mukhtar' else 'warsh'
    parent_sha='a01f926802dc95b0ae76ea74ac5f9b5521b1b94d5a7977e3c0fdb6f7bd5d25d1' if a.reader=='mukhtar' else 'd9534de9ed7aed07154a5784f2cefc5b7fef16981061bf9e4c3f9bc22a44b2aa'
    key=f'timings/{riwaya}/{reader}.jz'
    parent=checked(f'ops/source-repair/parents/codex-opener-{reader}-{parent_sha[:8]}.jz',parent_sha)
    oldpath='ops/source-repair/candidates/codex-mukhtar_haj-opener-repair-20261006.jz' if a.reader=='mukhtar' else 'ops/source-repair/candidates/codex-rabbani-openers-eof-20261006.jz'
    oldsha='0d9cba79502432d7861791bd6a9f32833b1ca9ce2f3f00bb99c58b8d0a3bd042' if a.reader=='mukhtar' else '5e9547a6890985ab372a377e2fd39c21acf1d2b04f41ab3ff618fa3cd879f292'
    candidate=checked(oldpath,oldsha);rows={e['ayahId']:e for e in candidate['entries']};proofs=[];reports=[];limits=[]
    if a.reader=='mukhtar':
        for args in [('mukhtar-rejected-contexts','3092106692dfce72b694f5f6049474cbb5d19fc53ea3707e15afb7aedc2ec091','b4b139424428f126f936bad910a01f8257d9c7028ebbf03d8e2db17d6e5099f6'),('mukhtar-adjacent-context','cd5a68fb9998e2e14aa4145246b21ad2c4962c5654f1cc05d6baffc0197d7a0d','55d45d0270d8e5b2bd01a0b94b0c553225c3efd5b6ce28ca0f2887d992021e5f')]:
            rs,_,p=evidence(*args);reports.extend(rs);proofs.append(p)
        C.require(len(reports)==7,'wrong context population')
        selected={'mukhtar37_19':[18,19],'mukhtar37_20_22':[20,21,22],'mukhtar37_25':[24,25,26],'mukhtar37_84':[83,84,85],'mukhtar37_153':[152,153,154],'mukhtar37_163':[162,163,164],'mukhtar37_166':[165,166,167]}
        for rep in reports:
            check_report(rep,parent);ms=rep['measurements']
            for ay in selected[rep['reader']]:
                aid=f'37:{ay}';es=[next(e for e in m['rawEntries'] if e['ayahId']==aid) for m in ms];qs=[next(e for e in m['rawEntries'] if e['ayahId']==aid) for m in ms if m['model']=='quran']
                C.require(max(e['startMs'] for e in es)-min(e['startMs'] for e in es)<=500 and min(e['conf'] for e in qs)>=.45,'ambiguous target '+aid)
                start=min(e['startMs'] for e in qs);rows[aid]['startMs']=start;rows[f'37:{ay-1}']['endMs']=start
        # Validate retained ends after adjacent contexts have all updated their boundaries.
        for rep in reports:
            last=f"37:{selected[rep['reader']][-1]}"
            C.require(rows[last]['endMs']>=max(next(e['endMs'] for e in m['rawEntries'] if e['ayahId']==last) for m in rep['measurements']),'final context would clip speech '+last)
        changed_surahs=[37]
        limits.append('The earlier37:20 context forced speech into21; the new20..22 context agrees across models and controls that boundary. No confidence values raised.')
    else:
        reports,raw,p=evidence('rabbani-final-contexts','fc61d25ba3da41683613b1013ec7627abcd21222ed306eedba561515835838d1','d9b300de00d7bd88fb1d36e7baad4a75a21376cb4fbe770d94ee141ce164d6b5');proofs.append(p)
        C.require({r['reader'] for r in reports}=={'rabbani56_tail','rabbani96_5_10'},'wrong final contexts')
        for rep in reports:check_report(rep,parent)
        tail=next(r for r in reports if r['reader']=='rabbani56_tail');dec=tail['audio']['decoded']
        C.require(dec['decodedWithoutErrors'] and dec['windowEndSampleExclusive']==dec['frames']==9216017,'wrong PCM EOF')
        C.require(rows['56:96']['endMs']==576026,'unexpected prior EOF');rows['56:96']['endMs']=dec['frames']*1000//16000
        middle=next(r for r in reports if r['reader']=='rabbani96_5_10')
        ends=[next(e['endMs'] for e in m['rawEntries'] if e['ayahId']=='96:6') for m in middle['measurements'] if m['model']=='quran']
        C.require(ends==[28126,28126],'changed measured preceding end')
        # Free generic speech places the first hamza at28.232s; Quran's final preceding
        # character is28.092s.28.126 is the independently aligned end between them.
        # Do not move to the later Quran-only7 onset29.277, which could omit the hamza.
        for channel in ('native-1','native-2'):
            for model,token,frame in [('generic','أ',911),('quran','ٰ',904)]:
                parts=[r['payload'] for r in raw if r['prefix']=='SOURCE_CONTEXT_FREE_PART' and r['payload']['surah']==96 and r['payload']['channel']==channel and r['payload']['model']==model]
                chunk=next(r['rawChunk'] for r in parts if r['rawChunk']['chunk']==1)
                vocab=next(m['vocabulary'] for m in middle['models'] if m['name']==model)
                C.require(any(t==vocab[token] and start==frame for t,start,*_ in chunk['argmaxRuns']),'free boundary bracket changed')
        rows['96:6']['endMs']=28126;rows['96:7']['startMs']=28126
        limits.append('96:7 model starts disagree by1.25s. Boundary28126 is the native Quran end of6, after its final free character and before the independently detected first hamza of7; original LOW confidence retained. Fresh independent QA remains mandatory.')
        changed_surahs=[56,77,96,102]
    for rep in reports:
        s=rep['source']['surah'];model=copy.deepcopy(next(m['alignmentModel'] for m in rep['measurements'] if m['model']=='quran'));model['canonicalTextChanged']=False
        candidate.setdefault('engineBySurah',{})[str(s)]='ctc-quran-window-1';candidate.setdefault('alignmentModelBySurah',{})[str(s)]=model
    changes=[{'before':x,'after':y} for x,y in zip(parent['entries'],candidate['entries']) if x!=y]
    for c in changes:
        strip=lambda e:{k:v for k,v in e.items() if k not in ('startMs','endMs')}
        C.require(strip(c['before'])==strip(c['after']) and int(c['after']['ayahId'].split(':')[0]) in changed_surahs,'confidence/source/unrelated entry changed')
    proof=dict(qualityClaim=False,previousProof=copy.deepcopy(candidate['transform'].get('sameSourceRepair')),evidence=proofs,changes=changes,limits=limits+['All original quality gates and final-SHA fresh QA are required.'])
    tr=C.repaired_transform(parent,candidate,changed_surahs,parent_sha,key);tr.pop('sourceRepair',None)
    moved,added,removed=T.entry_change_counts(parent['entries'],candidate['entries']);C.require(moved==len(changes) and added==removed==0,'population changed')
    tr.update(op='ctc_quran_window:'+','.join(map(str,changed_surahs)),fromSha256=parent_sha,fromKey=key,entriesSha256=T.entries_sha(candidate['entries']),parentEntriesSha256=T.entries_sha(parent['entries']),movedEntries=moved,addedEntries=0,removedEntries=0,by='build_mukhtar_rabbani_final_repairs',reason='Repair rejected native-context boundaries and verified decoded EOF',sameSourceRepair=proof,unpublishedLocalCandidate=True);candidate['transform']=tr
    why=T.promote.index_gate(candidate,parent=parent,parent_sha=parent_sha);C.require(not why,str(why));fatal,warnings,_=R.structural(candidate,key,False);C.require(not fatal,str(fatal));C.require(set(map(str,changed_surahs))<=T.promote.census_surahs(candidate),'missing census')
    out=f'ops/source-repair/candidates/codex-{a.reader}-native-final-v2-20261006.jz';b=gzip.compress(json.dumps(candidate,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode(),mtime=0);p=ROOT/out;C.require(not p.exists() or p.read_bytes()==b,'existing candidate differs');p.write_bytes(b)
    result=dict(path=out,sha256=hashlib.sha256(b).hexdigest(),parentSha256=parent_sha,changedEntries=moved,op=tr['op'],warnings=warnings,proof=proof)
    (ROOT/f'ops/out/codex-{a.reader}-native-final-v2-20261006.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='proof'},ensure_ascii=False))

if __name__=='__main__':main()
