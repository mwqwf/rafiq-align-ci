"""Build bounded same-source timing repairs from independently measured contexts."""
import argparse,copy,gzip,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_registered_candidate as C
import stage_transform as T
import run as R
ROOT=Path(__file__).resolve().parents[2]

def checked(path,sha,z=False):
    b=(ROOT/path).read_bytes();C.require(hashlib.sha256(b).hexdigest()==sha,'changed evidence '+path)
    return json.loads(gzip.decompress(b) if z else b)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--reader',choices=['mab','balilah'],required=True);a=ap.parse_args()
    if a.reader=='mab':
        parent_sha='746e762fc2722d0c6cc108d239aa0ad5ba1947e13189013201f4b3964201fee5'
        parent=checked('ops/source-repair/parents/codex-warsh-m_abdulkareem_warsh-746e762f.jz',parent_sha,True)
        candidate=checked('ops/source-repair/candidates/codex-mab-context-v3-20261006.jz','d3cdb23274e4a914565d31be7f3bd2aaee5ef751f540d5f93801fa7875e3b945',True)
        rp='ops/out/codex-mab-v4-contexts-20261006.json';rh='2eb8d7e6b43ed14879a7f642cca61acd194e59a281ba786fca6d1fc1ee736cd3'
        bp='ops/out/codex-mab-v4-contexts-complete-20261006.json.gz';bh='df49990b5d68b2a4c1883b9d2714d40551f806d60ec338fb33810575f5f11149'
        reports=checked(rp,rh);C.require(len(reports)==7,'context population')
        targets={r['reader']:[int(e['ayahId'].split(':')[1]) for e in r['measurements'][0]['rawEntries']] for r in reports}
        surahs={11,16,18,21,23,69,78,90};name='mab-context-v4'
    else:
        parent_sha='f1b40abe72f4f85bd41cc87166f2cf8785960c1e267f09816b99532851812207'
        parent=checked('ops/source-repair/parents/codex-hafs-balilah-f1b40abe.jz',parent_sha,True);candidate=copy.deepcopy(parent)
        rp='ops/out/codex-balilah-tail-contexts-20261006.json';rh='ce3747055da0bedf13f12ba353f24e3088d3b1189bc4ba3b8c20035031d508d3'
        bp='ops/out/codex-balilah-tail-contexts-complete-20261006.json.gz';bh='1581d26cc9f58bdcc7bfe6bf5362d6f7662189b10c36387cf38b5963931bc444'
        reports=checked(rp,rh)
        old=checked('ops/out/codex-duration-context-37392377734-reports.json','7fbc87cb7170153cfc0aa54c699c4e04ed168611faf3411b4f800e197410dc6d')
        reports += [next(r for r in old if r['reader']=='balilah')]
        targets={'balilah69_tail_transition':[43,44,45,46],'balilah':list(range(47,53))};surahs={69};name='balilah-tail-only'
    checked(bp,bh,True)
    rows={e['ayahId']:e for e in candidate['entries']};selected=[];eofs={}
    for rep in reports:
        src=rep['source'];s=src['surah'];ms=rep['measurements']
        C.require(rep['measurementComplete'] and not rep['errors'] and src['sha256']==parent['audioSha256'][s-1] and src['riwaya']==parent['riwaya'],'source or measurement mismatch')
        C.require({(m['model'],m['channel']) for m in ms}=={(m,c) for m in ('generic','quran') for c in ('native-1','native-2')},'missing matrix')
        C.require(len(rep['freeResults'])==4 and all(not m['canonicalTextInput'] and not m['forcedAlignment'] for m in rep['freeResults']),'missing unforced evidence')
        ayahs=targets[rep['reader']]
        for ay in ayahs:
            aid=f'{s}:{ay}';es=[next(e for e in m['rawEntries'] if e['ayahId']==aid) for m in ms]
            qs=[next(e for e in m['rawEntries'] if e['ayahId']==aid) for m in ms if m['model']=='quran']
            # Balilah generic's final-tail starts differ by <=650ms; retain
            # the two agreeing Quran measurements and let original heard QA judge.
            bound=700 if a.reader=='balilah' else 500
            C.require(max(e['startMs'] for e in es)-min(e['startMs'] for e in es)<=bound and min(e['conf'] for e in qs)>=.45,'ambiguous target '+aid)
            start=min(e['startMs'] for e in qs);rows[aid]['startMs']=start;rows[f'{s}:{ay-1}']['endMs']=start
        dec=rep['audio']['decoded'];last=f'{s}:{ayahs[-1]}'
        if ayahs[-1]==C.splice_surah.COUNTS[s-1] and dec['windowEndSampleExclusive']==dec['frames']:
            C.require(dec['decodedWithoutErrors'],'decode errors');eofs[s]=dec['frames']*1000//16000;rows[last]['endMs']=eofs[s]
        if a.reader=='mab':
            C.require(rows[last]['endMs']>=max(next(e['endMs'] for e in m['rawEntries'] if e['ayahId']==last) for m in ms),'retained end clips speech '+last)
        model=copy.deepcopy(next(m['alignmentModel'] for m in ms if m['model']=='quran'));model['canonicalTextChanged']=False
        candidate.setdefault('engineBySurah',{})[str(s)]='ctc-quran-window-1';candidate.setdefault('alignmentModelBySurah',{})[str(s)]=model
        selected.append(dict(reader=rep['reader'],ayahs=ayahs,sourceSha256=src['sha256'],provenance=rep['provenance']))
    changes=[dict(before=x,after=y) for x,y in zip(parent['entries'],candidate['entries']) if x!=y]
    for c in changes:
        strip=lambda e:{k:v for k,v in e.items() if k not in ('startMs','endMs')}
        C.require(strip(c['before'])==strip(c['after']) and int(c['after']['ayahId'].split(':')[0]) in surahs,'confidence or unrelated field changed')
        if a.reader=='balilah':C.require(42<=int(c['after']['ayahId'].split(':')[1])<=52,'outside measured tail')
    key=f"timings/{parent['riwaya']}/{parent['reciterId']}.jz"
    proof=dict(qualityClaim=False,reportPath=rp,reportSha256=rh,rawBundlePath=bp,rawBundleSha256=bh,selectedContexts=selected,decodedEofMs=eofs,changes=changes,inheritedProof=copy.deepcopy(candidate.get('transform',{}).get('sameSourceRepair')),limits=['Original confidence, riwaya, canonical text, source bytes unchanged.','Fresh complete exact-SHA original QA required.','Balilah69:26 remains unresolved; this repair only addresses42end and43..52.'] if a.reader=='balilah' else ['All original v3 rejection evidence retained. New native contexts measure actual boundary corrections; no unchanged resampling.','Original confidence unchanged; fresh exact-SHA original QA required.'])
    tr=C.repaired_transform(parent,candidate,sorted(surahs),parent_sha,key);moved,added,removed=T.entry_change_counts(parent['entries'],candidate['entries']);C.require(added==removed==0,'coverage changed')
    tr.update(op='ctc_quran_window:'+','.join(map(str,sorted(surahs))),fromSha256=parent_sha,fromKey=key,entriesSha256=T.entries_sha(candidate['entries']),parentEntriesSha256=T.entries_sha(parent['entries']),movedEntries=moved,addedEntries=0,removedEntries=0,by='build_measured_late_repairs',reason='Native source context repair of measured late boundaries',sameSourceRepair=proof,unpublishedLocalCandidate=True);candidate['transform']=tr
    why=T.promote.index_gate(candidate,parent=parent,parent_sha=parent_sha);C.require(not why,str(why));fatal,warnings,_=R.structural(candidate,key,False);C.require(not fatal,str(fatal));C.require(set(map(str,surahs))<=T.promote.census_surahs(candidate),'missing census')
    path=f'ops/source-repair/candidates/codex-{name}-20261006.jz';b=gzip.compress(json.dumps(candidate,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode(),mtime=0);p=ROOT/path;C.require(not p.exists() or p.read_bytes()==b,'output differs');p.write_bytes(b)
    result=dict(path=path,sha256=hashlib.sha256(b).hexdigest(),parentKey=key,parentSha256=parent_sha,op=tr['op'],changedEntries=moved,warnings=warnings)
    (ROOT/f'ops/out/codex-{name}-candidate-20261006.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
