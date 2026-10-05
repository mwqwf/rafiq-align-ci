"""Read-only free ASR plus context alignment for six short entries and one long repeated-verse candidate."""
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
PLAN='ops/source-repair/codex-duration-defects-plan-20261005.json'
PLAN_SHA='487d01e7b7d0c6305d8d36414742569abf69282d93d6f96263ff7a4119c569e5'
IDS=('balilah','darweez','koshi_warsh','m_abdulkareem_warsh','noah_warsh','tblawi','nufais')


def load_source(ident):
    B.require(ident in IDS,'unplanned reader')
    raw=(B.ROOT/PLAN).read_bytes();B.require(hashlib.sha256(raw).hexdigest()==PLAN_SHA,'plan changed')
    rows=json.loads(raw)['sources'];B.require(len(rows)==7 and {r['id'] for r in rows}==set(IDS),'population changed')
    source=next(r for r in rows if r['id']==ident)
    if ident=='nufais':
        path=(B.ROOT/source['candidatePath']).resolve()
        B.require(path.parent==B.ROOT/'ops/source-repair/candidates' and path.suffix=='.jz','candidate outside allowed directory')
        b=path.read_bytes();B.require(hashlib.sha256(b).hexdigest()==source['parentSha256'],'candidate digest mismatch')
    else:
        path=(B.ROOT/source['parentExportPath']).resolve()
        B.require(path.parent==B.ROOT/'ops/out' and path.suffix=='.json','export outside allowed directory')
        e=json.loads(path.read_bytes());b=base64.b64decode(e['gzipBase64'],validate=True)
        B.require(len(b)==e['bytes'] and hashlib.sha256(b).hexdigest()==source['parentSha256']==e['sha256'],'parent digest mismatch')
    idx=json.loads(gzip.decompress(b));context=[x for x in idx['entries'] if x['ayahId'] in [r['ayahId'] for r in source['contextEntries']]]
    B.require(idx['reciterId']==ident and idx['riwaya']==source['riwaya'] and context==source['contextEntries']
        and idx['audioSha256'][source['surah']-1]==source['sha256'] and all(x['fileRef']==source['url'] for x in context),'source context mismatch')
    start,end=source['requestedWindowSeconds'];B.require(type(start)is int and type(end)is int and 0<=start<end<=7200 and end-start<=70,'invalid window')
    S.metadata.validate_url(source['url'])
    return source,idx


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--reader',choices=IDS,required=True)
    ap.add_argument('--model-policy',choices=('cache-only','quran-pinned-ephemeral'),default='cache-only');a=ap.parse_args(argv)
    rep={'schema':1,'kind':'seven-duration-defect-context-diagnostic','reader':a.reader,'planSha256':PLAN_SHA,
      'measurementComplete':False,'qualityClaim':False,'productionChanged':False,'freeResults':[],'measurements':[],'models':[],'errors':[],
      'limits':['Context alignment may force absent text; compare free ASR and both models.','Existing candidate window may omit displaced speech.','No quality report, timing, confidence or Quran text is rewritten.'],
      'provenance':{'runId':os.environ.get('GITHUB_RUN_ID',''),'runSha':os.environ.get('GITHUB_SHA',''),'toolSha256':S.sha_file(__file__)}}
    try:
        source,idx=load_source(a.reader);rep['source']=source
        B.require(os.environ.get('CTC_INT8')=='0' and os.environ.get('CTC_THREADS')=='2','fixed CPU runtime required');rep['versions']=S.validate_versions()
        for k in ('HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE','HF_HUB_DISABLE_XET'):os.environ[k]='1'
        contract=P.load_contract();common=importlib.import_module('common')
        begin,stop,_=common.surah_slice(common.load_index(),source['surah']);refs=common.load_text(source['riwaya'])[begin:stop]
        ids=[e['ayahId'] for e in source['contextEntries']];canonical=[refs[int(i.split(':')[1])-1] for i in ids];rep['canonicalContext']=canonical
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
                            checkpoint=lambda part:S.emit(part,'DURATION_DEFECT_FREE_PART')))
                    del backend;gc.collect()
                import huggingface_hub as hub
                import numpy as np
                specs=P.model_specs(contract);bound={(s['id'],s['revision']):snapshots[s['name']] for s in specs}
                backend=P.Backend(importlib.import_module('ci_spoken_census'))
                with P.offline_model_loads(hub,specs,bound):
                    for name in ('generic','quran'):
                        model=backend.configure(name);texts=list(canonical) if name=='generic' else [backend.reference_text(t) for t in canonical]
                        for channel,raw in channels.items():
                            wav=np.frombuffer(raw,dtype='<i2').astype(np.float32)/32768.0
                            measured=P.raw_result(list(backend.segment(wav,texts)),ids,int(window['windowSeconds'][0]*1000),backend.conf)
                            row={'model':name,'channel':channel,'alignmentModel':model,'alignmentInput':texts,
                              'windowSeconds':window['windowSeconds'],'inputPcmSha256':hashlib.sha256(wav.tobytes()).hexdigest(),**measured}
                            rep['measurements'].append(row);S.emit(row,'DURATION_DEFECT_CONTEXT_PART')
                        backend.clear();gc.collect()
            B.require(S.sha_file(path)==source['sha256'],'source changed after inference')
            B.require(len(rep['freeResults'])==len(rep['measurements'])==2*collector.count,'incomplete matrix')
        load_source(a.reader);rep['measurementComplete']=True
    except Exception as exc:
        rep['errors'].append({'type':type(exc).__name__,'message':str(exc)[:240]})
    finally:S.emit(rep,'DURATION_DEFECT_REPORT')
    return 0 if rep['measurementComplete'] else 1

if __name__=='__main__':raise SystemExit(main())
