"""بناء خواتيم متصلة مقيسة من سياقات أصلية متداخلة؛ الفحص النهائي إلزامي."""
import argparse,copy,gzip,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_short_final_repairs as S
C,T,R,D,ROOT=S.C,S.T,S.R,S.D,S.ROOT

def build(spec):
    parent=S.checked(spec['parentPath'],spec['parentSha256'],True);candidate=copy.deepcopy(parent)
    key=f"timings/{parent['riwaya']}/{parent['reciterId']}.jz"
    C.require(key==spec['parentKey'],'هوية الأصل مختلفة')
    starts={};eofs={};models={};proofs=[]
    C.require(bool(spec['contexts']),'سياقات غائبة')
    for ctx in spec['contexts']:
        rep=S.checked(ctx['reportPath'],ctx['reportSha256']);parts=S.checked(ctx['bundlePath'],ctx['bundleSha256'],True);digests=set()
        for part in parts:
            b=json.dumps(part['payload'],ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
            C.require(len(b)==part['bytes'] and hashlib.sha256(b).hexdigest()==part['sha256'] and part['jobId']==ctx['jobId'],'تغير الدليل الخام');digests.add(part['sha256'])
        C.require(ctx['reportSha256'] in digests,'تقرير بلا أصل خام')
        source,_=D.load_source(ctx['id']);C.require(rep['reader']==ctx['id'] and rep['source']==source,'مصدر القياس مختلف')
        pp=S.checked(source['evidencePath'],source['evidenceSha256']);C.require(source['evidenceKind']=='pinned-parent' and pp['parentSha256']==spec['parentSha256'],'أصل السياق مختلف')
        s=source['surah'];C.require(source['sha256']==parent['audioSha256'][s-1] and source['riwaya']==parent['riwaya'],'هوية الصوت مختلفة')
        C.require(rep['measurementComplete'] and not rep['errors'],'قياس ناقص');ms=rep['measurements'];free=rep['freeResults'];dec=rep['audio']['decoded'];n=dec['nativeChannels']
        C.require(type(n)is int and n in (1,2) and dec['decodedWithoutErrors'],'قنوات أو فك غير صالح')
        matrix={(m,f'native-{c}') for m in ('generic','quran') for c in range(1,n+1)}
        C.require(len(ms)==len(free)==len(matrix) and {(m['model'],m['channel']) for m in ms}=={(m['model'],m['channel']) for m in free}==matrix,'مصفوفة ناقصة')
        for f in free:
            C.require(not f['canonicalTextInput'] and not f['forcedAlignment'] and f['sourceSha256']==source['sha256'],'تفريغ غير مستقل')
            C.require(all(x['rawPartSha256'] in digests for x in f['rawChunks']),'خام التفريغ ناقص')
        ayahs=ctx.get('targetAyahs',source['contextAyahs']);C.require(ayahs and set(ayahs)<=set(source['contextAyahs']),'توقيت بلا سياق')
        for a in ayahs:
            aid=f'{s}:{a}';es=[next(e for e in m['rawEntries'] if e['ayahId']==aid) for m in ms]
            C.require(min(e['conf'] for e in es)>=.45,'ثقة دون الحد الأصلي '+aid)
            C.require(max(e['startMs'] for e in es)-min(e['startMs'] for e in es)<=500,'خلاف بين النماذج '+aid)
            C.require(all(e['startMs']<e['endMs'] for e in es),'مدة غير صالحة')
            qs=[next(e for e in m['rawEntries'] if e['ayahId']==aid) for m in ms if m['model']=='quran'];start=min(e['startMs'] for e in qs)
            if aid in starts:C.require(abs(starts[aid]-start)<=500,'خلاف السياقات المتداخلة '+aid)
            starts[aid]=min(starts.get(aid,start),start)
        if C.splice_surah.COUNTS[s-1] in ayahs and dec['windowEndSampleExclusive']==dec['frames']:
            eof=dec['frames']*1000//16000
            C.require(s not in eofs or eofs[s]==eof,'نهايتان مختلفتان');eofs[s]=eof
            C.require(all(m['rawEntries'][-1]['endMs']<=eof for m in ms),'قص نهاية الكلام')
        models[s]=copy.deepcopy(next(m['alignmentModel'] for m in ms if m['model']=='quran'));models[s]['canonicalTextChanged']=False
        proofs.append({**ctx,'sourceSha256':source['sha256'],'targetAyahs':ayahs,'provenance':rep['provenance']})
    surahs=sorted(models);rows={e['ayahId']:e for e in candidate['entries']};allowed=set()
    for s in surahs:
        ayahs=sorted(int(k.split(':')[1]) for k in starts if k.startswith(f'{s}:'));last=C.splice_surah.COUNTS[s-1]
        C.require(ayahs==list(range(ayahs[0],last+1)) and ayahs[0]>1 and s in eofs,'الخاتمة غير متصلة أو لم تبلغ نهاية الملف')
        allowed.update(f'{s}:{a}' for a in range(ayahs[0]-1,last+1))
        for a in ayahs:
            aid=f'{s}:{a}';start=starts[aid];rows[aid]['startMs']=start;rows[f'{s}:{a-1}']['endMs']=start
        rows[f'{s}:{last}']['endMs']=eofs[s]
        candidate.setdefault('engineBySurah',{})[str(s)]='ctc-quran-window-1';candidate.setdefault('alignmentModelBySurah',{})[str(s)]=models[s]
    changes=[{'before':x,'after':y} for x,y in zip(parent['entries'],candidate['entries']) if x!=y];C.require(bool(changes),'لا تغيير')
    for c in changes:
        strip=lambda e:{k:v for k,v in e.items() if k not in ('startMs','endMs')}
        C.require(c['after']['ayahId'] in allowed and strip(c['before'])==strip(c['after']),'تغيير خارج النطاق أو تغيير الثقة')
    proof={'qualityClaim':False,'contexts':proofs,'changes':changes,'decodedEofMs':eofs,'limits':['الحد الأصلي لثقة المحاذاة0.45؛ لا تغيير لأي حارس أو ثقة منشورة.','الخواتيم المقيسة فقط؛ يلزم الفحص الأصلي الكامل للبصمة المرفوعة.']}
    tr=C.repaired_transform(parent,candidate,surahs,spec['parentSha256'],key);moved,added,removed=T.entry_change_counts(parent['entries'],candidate['entries']);C.require(added==removed==0,'تغير العدد')
    tr.update(op='ctc_quran_window:'+','.join(map(str,surahs)),fromSha256=spec['parentSha256'],fromKey=key,entriesSha256=T.entries_sha(candidate['entries']),parentEntriesSha256=T.entries_sha(parent['entries']),movedEntries=moved,addedEntries=0,removedEntries=0,by='build_expanded_tail_repairs',reason='إصلاح خاتمة متصلة بقياس النموذجين على القنوات الأصلية',sameSourceRepair=proof,unpublishedLocalCandidate=True);candidate['transform']=tr
    why=T.promote.index_gate(candidate,parent=parent,parent_sha=spec['parentSha256']);C.require(not why,str(why));fatal,warnings,_=R.structural(candidate,key,False);C.require(not fatal,str(fatal));C.require(set(map(str,surahs))<=T.promote.census_surahs(candidate),'فحص السور ناقص')
    path=f"ops/source-repair/candidates/codex-expanded-tail-{parent['riwaya']}-{parent['reciterId']}-20261006.jz";b=gzip.compress(json.dumps(candidate,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode(),mtime=0);p=ROOT/path;C.require(not p.exists() or p.read_bytes()==b,'مرشح سابق مختلف');p.write_bytes(b)
    result=dict(path=path,sha256=hashlib.sha256(b).hexdigest(),parentKey=key,parentSha256=spec['parentSha256'],op=tr['op'],changedEntries=moved,warnings=warnings,proof=proof)
    (ROOT/f"ops/out/codex-expanded-tail-{parent['riwaya']}-{parent['reciterId']}-candidate-20261006.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--spec',required=True);a=ap.parse_args();r=build(json.loads(Path(a.spec).read_text()));print(json.dumps({k:v for k,v in r.items() if k!='proof'},ensure_ascii=False))
if __name__=='__main__':main()
