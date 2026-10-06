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
PLAN_SHA='c645c28d8d224d051af40f69f876d42e2cfb8006229798272a674e6c5db624d9'
IDS=('saad28_context','saad45_tail','shamrani79_tail','tblawi_head','tblawi_tail','m_ab26_29','m_ab34_37','m_ab91_95')


def load_source(ident):
    B.require(ident in IDS, 'unplanned diagnostic')
    raw=(B.ROOT/PLAN).read_bytes();B.require(hashlib.sha256(raw).hexdigest()==PLAN_SHA,'plan changed')
    rows=json.loads(raw)['sources'];B.require(len(rows)==8 and {r['id'] for r in rows}==set(IDS),'population changed')
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
    elif source['evidenceKind']=='heard-rejection':
        B.require(evidence['measurementComplete'] and not evidence['measurementErrors'] and evidence['ok'] is False,'rejected complete witness required')
        B.require(evidence['sha256']=='e3279a0914c45bc72ef6c24ed02ff3196ce3e3664936c352bc85ce60bcd31323' and source['surah']==21 and source['riwaya']=='warsh','wrong rejection')
        measured=evidence['maps']['21']
        B.require(source['sha256']==measured['sha256'] and source['url']==measured['fileRef'] and source['maxSourceSeconds']==7200,'rejected source mismatch')
        B.require(all(type(a)is int and 1<=a<=112 for a in source['contextAyahs']),'invalid rejected context')
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
