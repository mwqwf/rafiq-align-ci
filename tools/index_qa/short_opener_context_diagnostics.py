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
PLAN='ops/source-repair/codex-short-openers-plan-20261006.json'
PLAN_SHA='ba9154ba55374b24ce9327f36258d4a237f2b86a1e73aa3b0b7762d1205f6c0c'
IDS=('a_alhazmi_77', 'a_alqrafi_108', 'a_alqrafi_113', 'arkani_77', 'hatem_54', 'mrifai_84', 'mukhtar_haj_37', 'obk_1', 'yousef_107', 'shaykhna_qalun_27', 'benkirane_warsh_77', 'benkirane_warsh_51', 'rabbani_warsh_56', 'rabbani_warsh_102')

def load_source(ident):
    import math
    B.require(ident in IDS,'unplanned opener')
    raw=(B.ROOT/PLAN).read_bytes();B.require(hashlib.sha256(raw).hexdigest()==PLAN_SHA,'opener plan changed')
    rows=json.loads(raw)['targets'];B.require(len(rows)==14 and {r['id'] for r in rows}==set(IDS),'opener population changed')
    selected=next(r for r in rows if r['id']==ident)
    with tempfile.TemporaryDirectory(prefix='opener-parent-',dir=os.environ.get('RUNNER_TEMP')) as td:
        path=Path(td)/'parent.jz'
        receipt=S.metadata.fetch('https://pub-2c2e1dcd92e84a2898820dd38d3e09e6.r2.dev/'+selected['parentKey'],path,limit=1024*1024)
        B.require(receipt['sha256']==selected['parentSha256'],'production parent changed; replan required')
        idx=json.loads(gzip.decompress(path.read_bytes()))
    B.require(idx['reciterId']==selected['reciterId'] and idx['riwaya']==selected['riwaya'] and len(idx['audioSha256'])==114,'parent identity')
    s=selected['surah'];entries=[e for e in idx['entries'] if e['ayahId'].startswith(str(s)+':')]
    B.require([e['ayahId'] for e in entries[:3]]==[f'{s}:{a}' for a in (1,2,3)],'missing opener context')
    B.require(entries[0]['endMs']-entries[0]['startMs']==selected['target']['ms'],'reported short opener changed')
    refs={e['fileRef'] for e in entries};B.require(len(refs)==1,'mixed source')
    stop=math.ceil(entries[2]['endMs']/1000)+3
    B.require(0<stop<=70,'opener context exceeds bounded window')
    source=dict(selected,url=next(iter(refs)),sha256=idx['audioSha256'][s-1],requestedWindowSeconds=[0,stop],contextAyahs=[1,2,3],parentEntries=entries[:4],maxSourceSeconds=7200)
    S.metadata.validate_url(source['url'])
    return source,idx


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--reader',choices=IDS,required=True)
    ap.add_argument('--model-policy',choices=('cache-only','quran-pinned-ephemeral'),default='cache-only');a=ap.parse_args(argv)
    rep={'schema':1,'kind':'short-opener-context-diagnostic','reader':a.reader,'planSha256':PLAN_SHA,
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
                            checkpoint=lambda part:S.emit(part,'OPENER_CONTEXT_FREE_PART')))
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
                            rep['measurements'].append(row);S.emit(row,'OPENER_CONTEXT_CONTEXT_PART')
                        backend.clear();gc.collect()
            B.require(S.sha_file(path)==source['sha256'],'source changed after inference')
            B.require(len(rep['freeResults'])==2*collector.count and len(rep['measurements'])==(2*collector.count if ids else 0),'incomplete matrix')
        rep['measurementComplete']=True
    except Exception as exc:
        rep['errors'].append({'type':type(exc).__name__,'message':str(exc)[:240]})
    finally:S.emit(rep,'OPENER_CONTEXT_REPORT')
    return 0 if rep['measurementComplete'] else 1

if __name__=='__main__':raise SystemExit(main())
