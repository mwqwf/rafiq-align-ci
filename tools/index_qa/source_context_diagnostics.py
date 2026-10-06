"""Read-only targeted source context and unknown long-recording content diagnosis."""
import argparse
import base64
import gc
import gzip
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parent))
import final_verse_free_batch as B
import independent_window_pilot as P
S=B.S
PLAN='ops/source-repair/codex-source-context-plan-20261006.json'
PLAN_SHA='77b196bfdc28021386e78a5b85a0fb093474cc3205b2338a07987ae6fd1fd51a'
IDS=('saad28_context', 'saad45_tail', 'shamrani79_tail', 'tblawi_head', 'tblawi_tail', 'm_ab26_29', 'm_ab34_37', 'm_ab91_95', 'koshi20_22', 'koshi94_96', 'saad28_tail', 'saad22_41_45', 'saad22_68_71', 'saad22_tail', 'shamrani79_middle', 'shamrani79_midad_middle', 'mab_rs1_16_9', 'mab_rs1_11_22', 'mab_rs1_18_90', 'mab_rs1_23_52', 'mab_rs1_23_79', 'mab_rs1_69_47', 'mab_rs1_90_11', 'mab_rs1_90_19', 'mab_rs1_90_5', 'mab_rs1_78_33', 'mrifai84_tail', 'yousef107_tail', 'saad_reject_22_27', 'saad_reject_22_52', 'saad_reject_22_62', 'saad_reject_28_21', 'saad_reject_28_67', 'hazmi67_23_26', 'hazmi67_tail', 'hazmi77_tail', 'benkirane77_tail', 'benkirane51_middle', 'benkirane51_tail', 'rabbani_warsh_77_expanded', 'rabbani_warsh_96_expanded', 'hatem_54_expanded', 'hatem_82_expanded', 'm_abdulkareem_warsh_69_expanded', 'mab78_32_36', 'mab90_4_8', 'mab90_10_14', 'mukhtar37_19', 'mukhtar37_25', 'mukhtar37_84', 'mukhtar37_153', 'mukhtar37_163', 'mukhtar37_166', 'benkirane77_26_28', 'rabbani56_tail', 'rabbani96_5_10', 'mukhtar37_20_22', 'tblawi7_new_head', 'tblawi7_new_middle', 'tblawi7_new_tail', 'obk1_new_full', 'mab_v3_11_56', 'mab_v3_11_91', 'mab_v3_11_122', 'mab_v3_16_16', 'mab_v3_23_105', 'mab_v3_23_113_114', 'mab_v3_23_117', 'balilah69_tail_transition', 'mab_v4_11_93', 'mab_v4_23_107')

PINNED_PARENT_IDS={'rabbani_warsh_77_expanded': 'd9534de9ed7aed07154a5784f2cefc5b7fef16981061bf9e4c3f9bc22a44b2aa', 'rabbani_warsh_96_expanded': 'd9534de9ed7aed07154a5784f2cefc5b7fef16981061bf9e4c3f9bc22a44b2aa', 'hatem_54_expanded': '5d7e73699ae633807bd57ecb60ea235f503318fdacf8c13bd3b81132eb10f85e', 'hatem_82_expanded': '5d7e73699ae633807bd57ecb60ea235f503318fdacf8c13bd3b81132eb10f85e', 'm_abdulkareem_warsh_69_expanded': '746e762fc2722d0c6cc108d239aa0ad5ba1947e13189013201f4b3964201fee5', 'mab78_32_36': '746e762fc2722d0c6cc108d239aa0ad5ba1947e13189013201f4b3964201fee5', 'mab90_4_8': '746e762fc2722d0c6cc108d239aa0ad5ba1947e13189013201f4b3964201fee5', 'mab90_10_14': '746e762fc2722d0c6cc108d239aa0ad5ba1947e13189013201f4b3964201fee5', 'mukhtar37_19': 'a01f926802dc95b0ae76ea74ac5f9b5521b1b94d5a7977e3c0fdb6f7bd5d25d1', 'mukhtar37_25': 'a01f926802dc95b0ae76ea74ac5f9b5521b1b94d5a7977e3c0fdb6f7bd5d25d1', 'mukhtar37_84': 'a01f926802dc95b0ae76ea74ac5f9b5521b1b94d5a7977e3c0fdb6f7bd5d25d1', 'mukhtar37_153': 'a01f926802dc95b0ae76ea74ac5f9b5521b1b94d5a7977e3c0fdb6f7bd5d25d1', 'mukhtar37_163': 'a01f926802dc95b0ae76ea74ac5f9b5521b1b94d5a7977e3c0fdb6f7bd5d25d1', 'mukhtar37_166': 'a01f926802dc95b0ae76ea74ac5f9b5521b1b94d5a7977e3c0fdb6f7bd5d25d1', 'rabbani56_tail': 'd9534de9ed7aed07154a5784f2cefc5b7fef16981061bf9e4c3f9bc22a44b2aa', 'rabbani96_5_10': 'd9534de9ed7aed07154a5784f2cefc5b7fef16981061bf9e4c3f9bc22a44b2aa', 'mukhtar37_20_22': 'a01f926802dc95b0ae76ea74ac5f9b5521b1b94d5a7977e3c0fdb6f7bd5d25d1', 'mab_v3_11_56': '746e762fc2722d0c6cc108d239aa0ad5ba1947e13189013201f4b3964201fee5', 'mab_v3_11_91': '746e762fc2722d0c6cc108d239aa0ad5ba1947e13189013201f4b3964201fee5', 'mab_v3_11_122': '746e762fc2722d0c6cc108d239aa0ad5ba1947e13189013201f4b3964201fee5', 'mab_v3_16_16': '746e762fc2722d0c6cc108d239aa0ad5ba1947e13189013201f4b3964201fee5', 'mab_v3_23_105': '746e762fc2722d0c6cc108d239aa0ad5ba1947e13189013201f4b3964201fee5', 'mab_v3_23_113_114': '746e762fc2722d0c6cc108d239aa0ad5ba1947e13189013201f4b3964201fee5', 'mab_v3_23_117': '746e762fc2722d0c6cc108d239aa0ad5ba1947e13189013201f4b3964201fee5', 'balilah69_tail_transition': 'f1b40abe72f4f85bd41cc87166f2cf8785960c1e267f09816b99532851812207', 'mab_v4_11_93': '746e762fc2722d0c6cc108d239aa0ad5ba1947e13189013201f4b3964201fee5', 'mab_v4_23_107': '746e762fc2722d0c6cc108d239aa0ad5ba1947e13189013201f4b3964201fee5'}

def load_source(ident):
    B.require(ident in IDS, 'unplanned diagnostic')
    raw=(B.ROOT/PLAN).read_bytes();B.require(hashlib.sha256(raw).hexdigest()==PLAN_SHA,'plan changed')
    rows=json.loads(raw)['sources'];B.require(len(rows)==71 and {r['id'] for r in rows}==set(IDS),'population changed')
    source=next(r for r in rows if r['id']==ident)
    path=(B.ROOT/source['evidencePath']).resolve()
    B.require(path.parent==B.ROOT/'ops/out' and path.suffix=='.json','evidence path')
    b=path.read_bytes();B.require(hashlib.sha256(b).hexdigest()==source['evidenceSha256'],'evidence changed')
    evidence=json.loads(b)
    if source['evidenceKind']=='alignment':
        B.require(evidence['measurementComplete'] and not evidence['errors'],'incomplete source evidence')
        measured=evidence['source']
        B.require(all(source[k]==measured[k] for k in ('url','sha256','surah','riwaya')),'source mismatch')
        B.require(source['contextAyahs'] and all(type(a)is int and 1<=a<=len(evidence['alignment']['entries']) for a in source['contextAyahs']),'invalid context')
        B.require(source['maxSourceSeconds']==7200,'ordinary source limit changed')
    elif source['evidenceKind']=='tblawi-publisher-metadata':
        B.require(ident in ('tblawi7_new_head','tblawi7_new_middle','tblawi7_new_tail'),'unexpected new publisher diagnostic')
        measured=evidence['sources'][0]
        B.require(evidence['complete'] and measured['id']=='tblawi7_nquran' and measured['ok'] and measured['pcm']['decodedWithoutErrors'] and measured['stereo']['decodedWithoutErrors'],'unhealthy publisher source')
        B.require(source['url']==measured['file']['finalUrl'] and source['sha256']==measured['file']['sha256']=='76b0d10dbb33d90cdbb98e71786653a497dbe73f7af704bf2297848ce1fbc547' and source['surah']==measured['surah']==7 and source['riwaya']==measured['riwaya']=='hafs','publisher source mismatch')
        B.require(measured['identitySourceUrl']=='https://www.nquran.com/ar/view/10716' and source['maxSourceSeconds']==7200,'publisher identity/limit changed')
    elif source['evidenceKind']=='obk-publisher-metadata':
        B.require(ident=='obk1_new_full','unexpected Shatri diagnostic')
        measured=evidence['sources'][0]
        B.require(evidence['complete'] and measured['id']=='obk1_nquran' and measured['ok'] and measured['pcm']['decodedWithoutErrors'] and measured['stereo']['decodedWithoutErrors'],'unhealthy Shatri source')
        B.require(source['url']==measured['file']['finalUrl']=='https://www.nquran.com/audiof/quran/Sh_%20shatri/001.mp3' and source['sha256']==measured['file']['sha256']=='a9a743e67cbae4e241744847e18fbac55c77090e5cbc8a4144dba78a412a5924','Shatri source mismatch')
        B.require(source['surah']==measured['surah']==1 and source['riwaya']==measured['riwaya']=='hafs' and measured['identitySourceUrl']=='https://www.nquran.com/ar/view/3870','Shatri publisher identity mismatch')
        B.require(source['contextAyahs']==list(range(1,8)) and source['requestedWindowSeconds']==[0,63] and source['maxSourceSeconds']==7200,'Shatri complete context changed')
    elif source['evidenceKind']=='pinned-parent':
        B.require(ident in PINNED_PARENT_IDS,'unexpected parent diagnostic')
        expected=PINNED_PARENT_IDS[ident]
        B.require(evidence['parentSha256']==expected,'wrong diagnostic parent')
        pb=(B.ROOT/evidence['parentPath']).read_bytes()
        B.require(hashlib.sha256(pb).hexdigest()==expected,'parent bytes changed')
        parent=json.loads(gzip.decompress(pb));surah=source['surah']
        B.require(parent['riwaya']==source['riwaya']==evidence['riwaya'] and parent['reciterId']==evidence['reciterId'],'parent identity changed')
        rows=[e for e in parent['entries'] if e['ayahId'] in {f'{surah}:{a}' for a in source['contextAyahs']}]
        B.require(rows==evidence['entries'] and len(rows)==len(source['contextAyahs']),'parent context changed')
        B.require({e['fileRef'] for e in rows}=={source['url']} and parent['audioSha256'][surah-1]==source['sha256']==evidence['sourceSha256'],'parent audio mismatch')
        B.require(source['maxSourceSeconds']==7200,'source limit changed')
    elif source['evidenceKind']=='raw-heard':
        B.require(ident in ('hazmi67_23_26','hazmi67_tail','hazmi77_tail'),'unexpected raw heard source')
        B.require(evidence['engine']=='ctc-heardmap-1' and evidence['surah']==source['surah'] and evidence['riwaya']==source['riwaya']=='hafs','wrong raw alignment')
        B.require(evidence['fileRef']==source['url'] and evidence['sha256']==source['sha256'] and not evidence['issues'],'wrong or incomplete heard source')
        # Heard-only reports intentionally have no timing entries. They authorize diagnostics, never a splice.
        count={67:30,77:50}[source['surah']]
        B.require(evidence['entries']==[] and set(evidence['heardMap'])=={str(i) for i in range(1,count+1)},'incomplete heard-only map')
        B.require(all(isinstance(v,dict) and len(v.get('anchorMs',[]))==2 for v in evidence['heardMap'].values()),'invalid heard-only anchors')
        rb=(B.ROOT/'ops/out/codex-hazmi-heard-37400472678.json').read_bytes()
        B.require(hashlib.sha256(rb).hexdigest()=='4e76f3bd15e1a31954e2bb872e26ea5c08522911db4f0f97262c4ed634292b5a','rejection changed')
        rejection=json.loads(rb)
        B.require(rejection['measurementComplete'] and not rejection['measurementErrors'] and rejection['ok'] is False,'incomplete original rejection')
        B.require(source['maxSourceSeconds']==7200,'source limit changed')
    elif source['evidenceKind']=='qa-disagreement':
        B.require(evidence['sha256']=='fbf2b7997b428c6b45e858f11aecf681337dfbd5f2e69f57a65c43e275bb939c' and not evidence['fatal'],'wrong QA report')
        targets={r['aid'] for r in evidence['sample']['rows'] if r['kind']=='جسيم'}
        B.require(len(targets)==10 and source['targetId'] in targets,'not a measured severe disagreement')
        pb=(B.ROOT/source['parentPath']).read_bytes()
        B.require(hashlib.sha256(pb).hexdigest()==source['parentSha256']=='746e762fc2722d0c6cc108d239aa0ad5ba1947e13189013201f4b3964201fee5','wrong parent')
        parent=json.loads(gzip.decompress(pb));byid={e['ayahId']:e for e in parent['entries']}
        B.require(parent['reciterId']=='m_abdulkareem_warsh' and parent['riwaya']==source['riwaya']=='warsh','wrong reader')
        s,a=map(int,source['targetId'].split(':'))
        B.require(source['surah']==s and source['contextAyahs']==list(range(a-1,a+2)),'wrong context')
        es=[byid[f'{s}:{n}'] for n in source['contextAyahs']]
        B.require(es==source['parentEntries'] and {e['fileRef'] for e in es}=={source['url']} and parent['audioSha256'][s-1]==source['sha256'],'wrong source or changed entries')
        B.require(source['maxSourceSeconds']==7200,'source limit changed')
    elif source['evidenceKind']=='metadata-source':
        measured=next(r for r in evidence['sources'] if r['id']=='shamrani_79_midad')
        B.require(ident=='shamrani79_midad_middle' and measured['ok'] and measured['pcm']['decodedWithoutErrors'],'unhealthy alternate source')
        B.require(source['sha256']==measured['file']['sha256'] and source['url']==measured['file']['finalUrl'] and source['surah']==measured['surah']==79 and source['riwaya']==measured['riwaya']=='hafs','alternate identity mismatch')
        B.require(source['maxSourceSeconds']==7200 and source['contextAyahs']==list(range(8,22)),'alternate scope changed')
    elif source['evidenceKind']=='heard-rejection':
        B.require(evidence['measurementComplete'] and not evidence['measurementErrors'] and evidence['ok'] is False,'rejected complete witness required')
        B.require(evidence['sha256']=='e3279a0914c45bc72ef6c24ed02ff3196ce3e3664936c352bc85ce60bcd31323' and source['surah']==21 and source['riwaya']=='warsh','wrong rejection')
        measured=evidence['maps']['21']
        B.require(source['sha256']==measured['sha256'] and source['url']==measured['fileRef'] and source['maxSourceSeconds']==7200,'rejected source mismatch')
        B.require(all(type(a)is int and 1<=a<=112 for a in source['contextAyahs']),'invalid rejected context')
    elif source['evidenceKind']=='koshi-rejection':
        B.require(evidence['measurementComplete'] and not evidence['measurementErrors'] and evidence['ok'] is False,'rejected complete witness required')
        B.require(evidence['sha256']=='db629f87eb79a0aca87c547ebc5856f08174e263be41591a4a984e4a616fa9d1' and source['surah']==11 and source['riwaya']=='warsh','wrong rejection')
        measured=evidence['maps']['11']
        B.require(source['sha256']==measured['sha256'] and source['url']==measured['fileRef'] and source['maxSourceSeconds']==7200,'rejected source mismatch')
        B.require(all(type(a)is int and 1<=a<=123 for a in source['contextAyahs']),'invalid rejected context')
    else:
        measured=evidence['sources'][0]
        B.require(ident in ('tblawi_head','tblawi_tail') and measured['ok'] and measured['pcm']['decodedWithoutErrors'],'invalid long-source exception')
        B.require(source['url']==measured['requestedUrl'] and source['sha256']==measured['file']['sha256']=='ec1ccc7f0f052e500eb173757d0ead4503071db2fbe9ce501c20fb156b0ca361','long source changed')
        B.require(source['maxSourceSeconds']==11000 and not source['contextAyahs'],'bounded free-only exception required')
    # Local read-only instance only: the measured ~3h source is explicitly pinned.
    # No strict decode checks are skipped and the shared helper file is unchanged.
    B.MAX_SOURCE_SECONDS=source['maxSourceSeconds']
    start,end=source['requestedWindowSeconds']
    B.require(type(start)is int and type(end)is int and 0<=start<end<=B.MAX_SOURCE_SECONDS and end-start<=70,'invalid window')
    S.metadata.validate_url(source['url'])
    return source,None


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--reader',choices=IDS,required=True)
    ap.add_argument('--model-policy',choices=('cache-only','quran-pinned-ephemeral'),default='cache-only');a=ap.parse_args(argv)
    rep={'schema':1,'kind':'source-context-and-content-diagnostic','reader':a.reader,'planSha256':PLAN_SHA,
      'measurementComplete':False,'qualityClaim':False,'productionChanged':False,'freeResults':[],'measurements':[],'models':[],'errors':[],
      'limits':['Context alignment may force absent text; compare free ASR and both models.','Existing candidate window may omit displaced speech.','No quality report, timing, confidence or Quran text is rewritten.'],
      'provenance':{'runId':os.environ.get('GITHUB_RUN_ID',''),'runSha':os.environ.get('GITHUB_SHA',''),'toolSha256':S.sha_file(__file__)}}
    try:
        source,idx=load_source(a.reader);rep['source']=source
        B.require(os.environ.get('CTC_INT8')=='0' and os.environ.get('CTC_THREADS')=='2','fixed CPU runtime required');rep['versions']=S.validate_versions()
        for k in ('HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE','HF_HUB_DISABLE_XET'):os.environ[k]='1'
        contract=P.load_contract();common=importlib.import_module('common')
        begin,stop,_=common.surah_slice(common.load_index(),source['surah']);refs=common.load_text(source['riwaya'])[begin:stop]
        ids=[f"{source['surah']}:{n}" for n in source['contextAyahs']];canonical=[refs[int(i.split(':')[1])-1] for i in ids];rep['canonicalContext']=canonical
        assets=B.ROOT/'core/quran/src/main/assets/quran';rep['referenceSha256']={n:S.sha_file(assets/n) for n in ('index.jz',f"text_{source['riwaya']}.jz")}
        with tempfile.TemporaryDirectory(prefix='rafiq-short-defect-',dir=os.environ.get('RUNNER_TEMP')) as tmp:
            path=Path(tmp)/'source.mp3';receipt=S.metadata.fetch(source['url'],path,limit=B.MAX_SOURCE_BYTES)
            B.require(receipt['sha256']==source['sha256'],'source changed');collector,proof=B.decode(path,source)
            rep['audio']={'download':receipt,**proof};channels=collector.channels();window=dict(source,windowSeconds=[collector.start/S.RATE,min(collector.frames,collector.end)/S.RATE])
            with S.model_snapshots(a.model_policy) as (snapshots,inventory):
                rep['modelAcquisition']=inventory
                for spec in S.MODELS:
                    backend=S.FreeCTC(snapshots[spec['name']],spec)
                    rep['models'].append({**spec,'vocabulary':backend.vocabulary,'files':S.model_files(snapshots[spec['name']],spec)})
                    for channel,raw in channels.items():
                        rep['freeResults'].append(S.measure_window(backend,raw,window,channel,spec['name'],
                            checkpoint=lambda part:S.emit(part,'SOURCE_CONTEXT_FREE_PART')))
                    del backend;gc.collect()
                import huggingface_hub as hub
                import numpy as np
                specs=P.model_specs(contract);bound={(s['id'],s['revision']):snapshots[s['name']] for s in specs}
                backend=P.Backend(importlib.import_module('ci_spoken_census'))
                with P.offline_model_loads(hub,specs,bound):
                    for name in (('generic','quran') if ids else ()):
                        model=backend.configure(name);texts=list(canonical) if name=='generic' else [backend.reference_text(t) for t in canonical]
                        for channel,raw in channels.items():
                            wav=np.frombuffer(raw,dtype='<i2').astype(np.float32)/32768.0
                            measured=P.raw_result(list(backend.segment(wav,texts)),ids,int(window['windowSeconds'][0]*1000),backend.conf)
                            row={'model':name,'channel':channel,'alignmentModel':model,'alignmentInput':texts,
                              'windowSeconds':window['windowSeconds'],'inputPcmSha256':hashlib.sha256(wav.tobytes()).hexdigest(),**measured}
                            rep['measurements'].append(row);S.emit(row,'SOURCE_CONTEXT_CONTEXT_PART')
                        backend.clear();gc.collect()
            B.require(S.sha_file(path)==source['sha256'],'source changed after inference')
            B.require(len(rep['freeResults'])==2*collector.count and len(rep['measurements'])==(2*collector.count if ids else 0),'incomplete matrix')
        load_source(a.reader);rep['measurementComplete']=True
    except Exception as exc:
        rep['errors'].append({'type':type(exc).__name__,'message':str(exc)[:240]})
    finally:S.emit(rep,'SOURCE_CONTEXT_REPORT')
    return 0 if rep['measurementComplete'] else 1

if __name__=='__main__':raise SystemExit(main())
