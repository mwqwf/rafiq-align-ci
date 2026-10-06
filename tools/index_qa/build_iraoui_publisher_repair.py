"""استعادة فصلت من المصدر الكامل المقيس؛ بناء محلي فقط والفحص الكامل إلزامي."""
import argparse,copy,gzip,hashlib,json,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_short_final_repairs as S
C,T,R,D,ROOT=S.C,S.T,S.R,S.D,S.ROOT
PARENT='e708c65694a2cea0bc1b0eace830fcb5988dfae50f07295b917cd4b200a50bf0'
KEY='timings/warsh/iraoui_warsh.jz'
SOURCE='f655b81ea9926ddd8c134ef04c197b550ffd954896c43229a2f01c6be1d1986b'
URL='https://archive.org/download/55555555555033alahzab_202004/041Fossilat.mp3'
FRAMES=20655125
REPORT='ops/out/codex-iraoui-new-archive-recovery-report-20261006.json'
REPORT_SHA='bbe33f06eeac3974674ca93ab641cbb455d807a5927fa501a3f78a67ddd8fb2a'
EXPECTED={'iraoui41_new_15_16','iraoui41_new_44','iraoui41_new_47_48','iraoui41_new_49_50','iraoui41_new_51_52','iraoui41_new_53_54','iraoui41_new_50_full','iraoui41_new_head_1_4'}

def context(spec):
    rep=S.checked(spec['reportPath'],spec['reportSha256']);parts=S.checked(spec['bundlePath'],spec['bundleSha256'],True);digests=set()
    for part in parts:
        raw=json.dumps(part['payload'],ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
        C.require(part['jobId']==spec['jobId'] and len(raw)==part['bytes'] and hashlib.sha256(raw).hexdigest()==part['sha256'],'تغير الدليل الخام');digests.add(part['sha256'])
    C.require(spec['reportSha256'] in digests,'تقرير بلا أصل خام')
    src,_=D.load_source(spec['id']);C.require(rep['reader']==spec['id'] and rep['source']==src,'تغير سياق المصدر')
    C.require(src['sha256']==SOURCE and src['url']==URL and src['surah']==41 and src['riwaya']=='warsh','اختلاط المصدر أو الرواية')
    C.require(rep['measurementComplete'] and not rep['errors'],'قياس ناقص')
    dec=rep['audio']['decoded'];C.require(dec['frames']==FRAMES and dec['nativeChannels']==2 and dec['decodedWithoutErrors'],'فك مصدر مختلف')
    matrix={(m,c) for m in ('generic','quran') for c in ('native-1','native-2')}
    for field in ['measurements','freeResults']:
        C.require(len(rep[field])==4 and {(x['model'],x['channel']) for x in rep[field]}==matrix,'مصفوفة قياس ناقصة')
    for f in rep['freeResults']:
        C.require(not f['canonicalTextInput'] and not f['forcedAlignment'] and f['sourceSha256']==SOURCE and f['rawChunks'],'تفريغ حر غير مستقل')
        C.require(all(x['rawPartSha256'] in digests for x in f['rawChunks']),'خام التفريغ ناقص')
    return rep

def refine(full,reports):
    C.require(set(reports)==EXPECTED,'سياقات المصدر غير مكتملة')
    a=copy.deepcopy(full)
    C.require(a['engine']=='ctc-quran-surah-1' and a['riwaya']=='warsh' and a['surah']==41 and not a['issues'],'محاذاة سورة أخرى أو مشكلات غير مراجعة')
    C.require(len(a['entries'])==54 and [x['ayahIdx'] for x in a['entries']]==list(range(54)),'السورة ليست كاملة مرتبة')
    # لا نرفع الثقة القديمة بالتصويت: نستخدم درجة المحاذاة القرآنية المقيسة نفسها
    # حيث أخفقت محاذاة السورة الكاملة، ونحفظ المصدرين قبل/بعد في الدليل.
    changes=[]
    for ident,ayahs in [('iraoui41_new_47_48',[47,48]),('iraoui41_new_49_50',[49]),('iraoui41_new_50_full',[50]),('iraoui41_new_51_52',[51,52]),('iraoui41_new_53_54',[53,54])]:
        ms=reports[ident]['measurements']
        for n in ayahs:
            es=[next(e for e in m['rawEntries'] if e['ayahId']==f'41:{n}') for m in ms];qs=[next(e for e in m['rawEntries'] if e['ayahId']==f'41:{n}') for m in ms if m['model']=='quran']
            C.require(min(e['conf'] for e in qs)>=.45,'محاذاة قرآنية ضعيفة في الخاتمة')
            C.require(max(e['startMs'] for e in es)-min(e['startMs'] for e in es)<=500,'خلاف بداية بين النماذج')
            original=copy.deepcopy(a['entries'][n-1]);a['entries'][n-1].update(startMs=min(e['startMs'] for e in qs),conf=min(e['conf'] for e in qs),snapped=False)
            changes.append({'ayah':n,'before':original,'afterMeasuredStartMs':a['entries'][n-1]['startMs'],'afterMeasuredConfidence':a['entries'][n-1]['conf'],'context':ident,'measurements':es})
    # المطالع والمواضع الضعيفة الأصلية تبقى بدرجاتها الصادقة، مع إثبات وجودها
    # في التفريغ الحر والسياقات الأصلية، ولا تمنح هذه الأداة شهادة قبول لها.
    for ident,ns in [('iraoui41_new_head_1_4',[1,2,3,4]),('iraoui41_new_15_16',[15,16]),('iraoui41_new_44',[44])]:
        for m in reports[ident]['measurements']:
            for n in ns:
                e=next(x for x in m['rawEntries'] if x['ayahId']==f'41:{n}')
                C.require(abs(e['startMs']-a['entries'][n-1]['startMs'])<=500,'خلاف بداية خارج الخاتمة')
    tail=reports['iraoui41_new_53_54']['audio']['decoded'];C.require(tail['windowEndSampleExclusive']==FRAMES,'آخر السورة لم يبلغ نهاية الملف')
    eof=FRAMES*1000//16000
    for i,e in enumerate(a['entries']):
        e['endMs']=a['entries'][i+1]['startMs'] if i<53 else eof
        C.require(0<=e['startMs']<e['endMs']<=eof,'ترتيب حدود غير صالح')
    a.update(totalMs=eof,sha256=SOURCE,fileRef=URL,audioSha256=SOURCE,sourceUrl=URL)
    return a,changes

def build(spec_path):
    specs=json.loads(Path(spec_path).read_text());C.require(len(specs)==len(EXPECTED) and {s['id'] for s in specs}==EXPECTED,'قائمة الأدلة ناقصة أو مكررة')
    reports={s['id']:context(s) for s in specs}
    rep=S.checked(REPORT,REPORT_SHA);C.require(rep['measurementComplete'] and not rep['errors'] and rep['source']['sha256']==SOURCE and rep['source']['url']==URL,'قياس كامل مختلف')
    metadata=S.checked('ops/out/codex-new-archive-metadata-37413567942.json','94c95c7b5f327dc9ee11e06a04de195ca45b99049148135dbab38b0d5b6da830');m=next(x for x in metadata['sources'] if x['id']=='iraoui86_surahs_s41')
    C.require(metadata['complete'] and m['ok'] and m['file']['sha256']==SOURCE and m['pcm']['samples']==FRAMES and m['pcm']['decodedWithoutErrors'] and m['pcm']['longSilenceCount']==0,'مصدر غير سليم')
    identity_path='ops/out/20261006_codex_1030_verify_archive_identity_iraoui.txt'
    identity_bytes=(ROOT/identity_path).read_bytes();identity_sha='f61d09bec2ee6f651fd381f71eb24952b42f84305b5d7389428f46afe90303b1'
    C.require(hashlib.sha256(identity_bytes).hexdigest()==identity_sha and 'رواية ورش' in identity_bytes.decode() and 'ايراوي' in identity_bytes.decode(),'تصريح الناشر تغير')
    a,changes=refine(rep['alignment'],reports)
    pp='ops/source-repair/parents/codex-warsh-iraoui_warsh-e708c656.jz';parent=S.checked(pp,PARENT,True)
    C.require(parent['reciterId']=='iraoui_warsh' and parent['riwaya']=='warsh' and len(parent['entries'])==6182 and not any(e['ayahId'].startswith('41:') for e in parent['entries']),'الأصل مختلف')
    source=C.source_registry.registered_source('warsh','iraoui_warsh',41)
    C.require(source['url']==URL and source['audio_sha256']==SOURCE,'المصدر الكامل غير مسجل')
    with tempfile.TemporaryDirectory() as td:
        td=Path(td);aligned=td/'aligned.json';aligned.write_text(json.dumps(a,ensure_ascii=False));out=td/'merged.jz';old=sys.argv
        sys.argv=[C.splice_surah.__file__,'--index',str(ROOT/pp),'--surah','41','--aligned',str(aligned),'--url',URL,'--registered-sources','--alt-source','--engine-tag',a['engine'],'--out',str(out)]
        try:C.splice_surah.main()
        finally:sys.argv=old
        C.require(Path(str(out)+'.taken').read_text()=='41','لم تدمج السورة كاملة');candidate=json.loads(gzip.decompress(out.read_bytes()))
    outside=lambda es:[e for e in es if not e['ayahId'].startswith('41:')]
    C.require(outside(parent['entries'])==outside(candidate['entries']),'تغير مدخل خارج فصلت')
    expected=list(parent['audioSha256']);expected[40]=SOURCE
    C.require(candidate['audioSha256']==expected,'تغير صوت سورة أخرى')
    C.require(candidate['sourceBySurah']['41']==URL and candidate['engineBySurah']['41']=='ctc-quran-surah-1','نسب السورة غير معلن')
    for field in set(parent)|set(candidate):
        if field.endswith('BySurah'):
            C.require({k:v for k,v in (parent.get(field) or {}).items() if k!='41'}=={k:v for k,v in (candidate.get(field) or {}).items() if k!='41'},'تغير نسب خارج فصلت')
    for field in ['riwaya','reciterId','engineVersion','refineVersion','ayahCount']:
        C.require(parent.get(field)==candidate.get(field),'تغير حقل الأصل '+field)
    C.require(len(candidate['entries'])==6236 and candidate['missing']['count']==0 and not candidate['missing']['ids'],'الغياب لا يطابق الاستعادة');candidate['missing']['byReason']={}
    if 'lowCount' in candidate:candidate['lowCount']=sum(e['confBand']=='LOW' for e in candidate['entries'])
    rows=[e for e in candidate['entries'] if e['ayahId'].startswith('41:')]
    C.require(all(e['startMs']==v['startMs'] and e['endMs']==v['endMs'] and e['conf']==v['conf'] for e,v in zip(rows,a['entries'])),'قياس تغير بعد الدمج')
    moved,added,removed=T.entry_change_counts(parent['entries'],candidate['entries']);C.require(moved==removed==0 and added==54,'تغير خارج الغياب الأصلي')
    proof={'qualityClaim':False,'reportPath':REPORT,'reportSha256':REPORT_SHA,'nativeContexts':specs,'measuredRefinements':changes,'audioSha256':SOURCE,'sourceUrl':URL,'decodedEofMs':a['totalMs'],'publisherIdentityUrl':m['identitySourceUrl'],'publisherIdentityEvidencePath':identity_path,'publisherIdentityEvidenceSha256':identity_sha,'limits':['نسبة القارئ والرواية من تصريح الناشر؛ لا ندعي تعرفاً بيومترياً.','الثقة في الآيتين15و44تبقى ضعيفة كما قيست؛ لا ترفع لتسهيل القبول.','المحاذاة الكاملة أخفقت47..54 واستبدلت بقياسات سياقية فعلية مع حفظ الأصل.','يلزم الفحص المستقل الكامل للبصمة المرفوعة قبل أي اعتماد.']}
    tr=C.repaired_transform(parent,candidate,[41],PARENT,KEY);tr.update(op='ctc_quran_surah_splice:41',fromSha256=PARENT,fromKey=KEY,entriesSha256=T.entries_sha(candidate['entries']),parentEntriesSha256=T.entries_sha(parent['entries']),movedEntries=moved,addedEntries=added,removedEntries=removed,by='build_iraoui_publisher_repair',reason='استعادة54آية من مصدر ناشر كامل مع قياس سياقي مستقل وتصريح المصدر',sourceRepair=proof,unpublishedLocalCandidate=True);candidate['transform']=tr
    why=T.promote.index_gate(candidate,parent=parent,parent_sha=PARENT);C.require(not why,str(why));fatal,warnings,_=R.structural(candidate,KEY,False);C.require(not fatal,str(fatal));C.require('41' in T.promote.census_surahs(candidate),'سورة المصدر الجديد غائبة عن الإحصاء')
    path='ops/source-repair/candidates/codex-iraoui41-publisher-20261006.jz';b=gzip.compress(json.dumps(candidate,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode(),mtime=0);p=ROOT/path;C.require(not p.exists() or p.read_bytes()==b,'مرشح سابق مختلف');p.write_bytes(b)
    result=dict(path=path,sha256=hashlib.sha256(b).hexdigest(),parentKey=KEY,parentSha256=PARENT,op=tr['op'],changedEntries=moved,addedEntries=added,proof=proof,warnings=warnings);(ROOT/'ops/out/codex-iraoui41-publisher-candidate-20261006.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');return result

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--spec',required=True);args=ap.parse_args();r=build(args.spec);print(json.dumps({k:v for k,v in r.items() if k!='proof'},ensure_ascii=False))
