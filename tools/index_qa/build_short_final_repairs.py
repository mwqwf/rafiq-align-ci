"""إصلاح آخر آيتين فقط من سياق أصلي متحقق؛ لا ترقية ولا رفع ولا تغيير للثقة."""
import argparse,copy,gzip,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_registered_candidate as C
import stage_transform as T
import run as R
import source_context_diagnostics as D
ROOT=Path(__file__).resolve().parents[2]

def checked(path,sha,z=False):
    b=(ROOT/path).read_bytes();C.require(hashlib.sha256(b).hexdigest()==sha,'تغير الدليل '+path)
    return json.loads(gzip.decompress(b) if z else b)

def build(spec):
    rep=checked(spec['reportPath'],spec['reportSha256'])
    bundle=checked(spec['bundlePath'],spec['bundleSha256'],True)
    digests=set()
    for part in bundle:
        raw=json.dumps(part['payload'],ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
        C.require(len(raw)==part['bytes'] and hashlib.sha256(raw).hexdigest()==part['sha256'],'تغير جزء خام')
        C.require(part['jobId']==spec['jobId'],'اختلط مصدر القياس');digests.add(part['sha256'])
    C.require(spec['reportSha256'] in digests,'تقرير بلا أصل خام')
    C.require(spec['id']==rep['reader'] and spec['id'].startswith('short_final_'),'قياس خارج الدفعة')
    source,_=D.load_source(spec['id']);C.require(rep['source']==source,'خطة القياس مختلفة')
    parent_proof=checked(source['evidencePath'],source['evidenceSha256'])
    parent_sha=parent_proof['parentSha256'];key=parent_proof['parentKey']
    parent=checked(parent_proof['parentPath'],parent_sha,True);candidate=copy.deepcopy(parent)
    C.require(rep['measurementComplete'] and not rep['errors'],'قياس ناقص')
    s=source['surah'];last=C.splice_surah.COUNTS[s-1]
    C.require(source['contextAyahs']==[last-2,last-1,last],'ليس سياق آخر ثلاث آيات')
    C.require(source['sha256']==parent['audioSha256'][s-1] and source['riwaya']==parent['riwaya'],'تغير المصدر')
    rows={e['ayahId']:e for e in candidate['entries']};ms=rep['measurements'];free=rep['freeResults']
    native_channels=rep['audio']['decoded']['nativeChannels']
    C.require(type(native_channels) is int and native_channels in (1,2),'عدد القنوات الأصلية غير مدعوم')
    matrix={(m,f'native-{c}') for m in ('generic','quran') for c in range(1,native_channels+1)}
    C.require(len(ms)==2*native_channels and {(m['model'],m['channel']) for m in ms}==matrix,'مصفوفة محاذاة ناقصة')
    C.require(len(free)==2*native_channels and {(m['model'],m['channel']) for m in free}==matrix,'تفريغ حر ناقص')
    for f in free:
        C.require(not f['canonicalTextInput'] and not f['forcedAlignment'] and f['sourceSha256']==source['sha256'],'تفريغ غير مستقل')
        C.require(all(c['rawPartSha256'] in digests for c in f['rawChunks']),'التفريغ الخام ناقص')
    for ay in source['contextAyahs']:
        aid=f'{s}:{ay}';es=[next(e for e in m['rawEntries'] if e['ayahId']==aid) for m in ms]
        C.require(min(e['conf'] for e in es)>=(.6 if ay>=last-1 else .45),'ثقة ضعيفة '+aid)
        C.require(max(e['startMs'] for e in es)-min(e['startMs'] for e in es)<=500,'خلاف بداية '+aid)
        C.require(all(e['endMs']>e['startMs'] for e in es),'مدة غير صالحة '+aid)
        if ay==last-2:
            C.require(max(abs(e['startMs']-rows[aid]['startMs']) for e in es)<=500,'بداية السابقة تحتاج إصلاحاً منفصلاً')
            continue
        qs=[next(e for e in m['rawEntries'] if e['ayahId']==aid) for m in ms if m['model']=='quran']
        start=min(e['startMs'] for e in qs);rows[aid]['startMs']=start;rows[f'{s}:{ay-1}']['endMs']=start
    dec=rep['audio']['decoded'];C.require(dec['decodedWithoutErrors'] and dec['windowEndSampleExclusive']==dec['frames'],'لم يقس الملف حتى نهايته')
    eof=dec['frames']*1000//16000;rows[f'{s}:{last}']['endMs']=eof
    C.require(all(next(e for e in m['rawEntries'] if e['ayahId']==f'{s}:{last}')['endMs']<=eof for m in ms),'النهاية تقص الكلام')
    changes=[{'before':x,'after':y} for x,y in zip(parent['entries'],candidate['entries']) if x!=y]
    C.require(bool(changes),'لا تغيير مقيس')
    for c in changes:
        C.require(c['after']['ayahId'] in {f'{s}:{a}' for a in source['contextAyahs']},'تغيير خارج السياق')
        strip=lambda e:{k:v for k,v in e.items() if k not in ('startMs','endMs')}
        C.require(strip(c['before'])==strip(c['after']),'تغير الثقة أو حقل آخر')
    candidate.setdefault('engineBySurah',{})[str(s)]='ctc-quran-window-1'
    model=copy.deepcopy(next(m['alignmentModel'] for m in ms if m['model']=='quran'));model['canonicalTextChanged']=False
    candidate.setdefault('alignmentModelBySurah',{})[str(s)]=model
    proof={**spec,'qualityClaim':False,'sourceSha256':source['sha256'],'decodedEofMs':eof,'changes':changes,'provenance':rep['provenance'],'limits':['توقيت آخر آيتين ونهاية السابقة فقط؛ الثقة الأصلية محفوظة.','التفريغ الحر روجع قبل البناء؛ يلزم فحص أصلي كامل على البصمة المرفوعة.']}
    tr=C.repaired_transform(parent,candidate,[s],parent_sha,key);moved,added,removed=T.entry_change_counts(parent['entries'],candidate['entries']);C.require(added==removed==0,'تغير عدد الآيات')
    tr.update(op=f'ctc_quran_window:{s}',fromSha256=parent_sha,fromKey=key,entriesSha256=T.entries_sha(candidate['entries']),parentEntriesSha256=T.entries_sha(parent['entries']),movedEntries=moved,addedEntries=0,removedEntries=0,by='build_short_final_repairs',reason='إصلاح خاتمة مقيسة من المصدر الأصلي بكلا النموذجين',sameSourceRepair=proof,unpublishedLocalCandidate=True);candidate['transform']=tr
    why=T.promote.index_gate(candidate,parent=parent,parent_sha=parent_sha);C.require(not why,str(why));fatal,warnings,_=R.structural(candidate,key,False);C.require(not fatal,str(fatal));C.require(str(s) in T.promote.census_surahs(candidate),'سورة غائبة عن الفحص')
    path=f"ops/source-repair/candidates/codex-{spec['id']}-20261006.jz";b=gzip.compress(json.dumps(candidate,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode(),mtime=0);p=ROOT/path;C.require(not p.exists() or p.read_bytes()==b,'مرشح موجود مختلف');p.write_bytes(b)
    result=dict(path=path,sha256=hashlib.sha256(b).hexdigest(),parentKey=key,parentSha256=parent_sha,op=tr['op'],changedEntries=moved,warnings=warnings,proof=proof)
    (ROOT/f"ops/out/codex-{spec['id']}-candidate-20261006.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--spec',required=True);a=ap.parse_args();result=build(json.loads(Path(a.spec).read_text()));print(json.dumps({k:v for k,v in result.items() if k!='proof'},ensure_ascii=False))
if __name__=='__main__':main()
