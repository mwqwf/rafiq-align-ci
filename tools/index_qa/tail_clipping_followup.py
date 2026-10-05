"""Five source-pinned tail diagnostics after free ASR found terminal clipping.

Target-only forced alignment is diagnostic. Zahrani also gets free ASR through
actual EOF because the previous window ended within a repeated final phrase.
"""
import argparse
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
from peshawa_tail_dual_probe import assess
S=B.S
PLAN='ops/source-repair/codex-tail-clipping-followup-plan-20261005.json'
PLAN_SHA='a6560d3ba1c6da054bf95acee4cbadcba407734cd3aa83c6e668e90dbfa085b4'
IDS={'derini_warsh-s11','derini_warsh-s23','derini_warsh-s83','zahrani-s6','f_khamery-s6'}


def load_plan():
    raw=(B.ROOT/PLAN).read_bytes()
    B.require(hashlib.sha256(raw).hexdigest()==PLAN_SHA,'plan changed')
    rows=json.loads(raw)['sources']
    B.require(len(rows)==5 and {s['id'] for s in rows}==IDS,'unexpected source set')
    for r in rows:
        p=(B.ROOT/r['candidatePath']).resolve()
        B.require(p.is_relative_to(B.ROOT/'ops/source-repair/candidates') and S.sha_file(p)==r['candidateSha256'],'candidate mismatch')
        idx=json.loads(gzip.decompress(p.read_bytes()))
        es=[e for e in idx['entries'] if e['ayahId'].startswith(str(r['surah'])+':')]
        B.require(idx['reciterId']==r['reciterId'] and idx['riwaya']==r['riwaya']
            and idx['audioSha256'][r['surah']-1]==r['sha256'] and es[-1]==r['target']
            and r['target']['fileRef']==r['url'],'source/target mismatch')
        start,end=r['requestedWindowSeconds']
        B.require(type(start)is int and type(end)is int and 0<=start<end<=7200 and end-start<=70,'window out of bounds')
        S.metadata.validate_url(r['url'])
    return rows


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--model-policy',choices=('cache-only','quran-pinned-ephemeral'),default='cache-only')
    args=ap.parse_args(argv)
    report={'schema':1,'kind':'five-tail-clipping-diagnostic','measurementComplete':False,
        'qualityClaim':False,'productionChanged':False,'replacesOfficialWitness':False,
        'planSha256':PLAN_SHA,'sources':[],'models':[],'freeResults':[],'measurements':[],'errors':[],
        'limits':['Target-only alignment may force text; interpret with preserved free ASR.',
                  'Native channels share model weights; not independent recordings.',
                  'No confidence scores or production timings are rewritten.'],
        'provenance':{'runId':os.environ.get('GITHUB_RUN_ID',''),'runSha':os.environ.get('GITHUB_SHA',''),
            'toolSha256':S.sha_file(__file__)}}
    try:
        rows=load_plan()
        B.require(os.environ.get('CTC_INT8')=='0' and os.environ.get('CTC_THREADS')=='2','fixed CPU runtime required')
        report['versions']=S.validate_versions()
        for key in ('HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE','HF_HUB_DISABLE_XET'):os.environ[key]='1'
        contract=P.load_contract();common=importlib.import_module('common')
        windows=[]
        with tempfile.TemporaryDirectory(prefix='rafiq-tail-followup-',dir=os.environ.get('RUNNER_TEMP')) as tmp:
            for r in rows:
                path=Path(tmp)/(r['id']+'.mp3')
                receipt=S.metadata.fetch(r['url'],path,limit=B.MAX_SOURCE_BYTES)
                B.require(receipt['sha256']==r['sha256'],'source hash mismatch')
                collector,proof=B.decode(path,r)
                B.require(abs(proof['decoded']['durationSeconds']-r['decodedDurationSeconds'])<1/16000,'decoded duration changed')
                begin,stop,_=common.surah_slice(common.load_index(),r['surah'])
                canonical=common.load_text(r['riwaya'])[begin:stop][-1]
                source=dict(r,windowSeconds=[collector.start/S.RATE,min(collector.frames,collector.end)/S.RATE])
                windows.append((source,collector.channels(),canonical))
                report['sources'].append({'id':r['id'],'download':receipt,'canonicalReference':canonical,**proof})
                path.unlink()
            with S.model_snapshots(args.model_policy) as (snapshots,inventory):
                report['modelAcquisition']=inventory
                # Only Zahrani needs new free evidence: the previous window clipped a repeat.
                source,channels,_=next(w for w in windows if w[0]['id']=='zahrani-s6')
                for spec in S.MODELS:
                    backend=S.FreeCTC(snapshots[spec['name']],spec)
                    report['models'].append({**spec,'vocabulary':backend.vocabulary,'files':S.model_files(snapshots[spec['name']],spec)})
                    for channel,raw in channels.items():
                        result=S.measure_window(backend,raw,source,channel,spec['name'],
                            checkpoint=lambda part:S.emit(part,'TAIL_CLIPPING_FREE_PART'))
                        report['freeResults'].append(result)
                    del backend;gc.collect()
                import huggingface_hub as hub
                import numpy as np
                specs=P.model_specs(contract)
                bound={(s['id'],s['revision']):snapshots[s['name']] for s in specs}
                backend=P.Backend(importlib.import_module('ci_spoken_census'))
                with P.offline_model_loads(hub,specs,bound):
                    for model_name in ('generic','quran'):
                        model=backend.configure(model_name)
                        for source,channels,canonical in windows:
                            reference=canonical if model_name=='generic' else backend.reference_text(canonical)
                            start=int(source['windowSeconds'][0]*1000)
                            for offset in (0,500):
                                for channel,raw in channels.items():
                                    wav=np.frombuffer(raw,dtype='<i2')[offset*16:].astype(np.float32)/32768.0
                                    entries=P.raw_result(list(backend.segment(wav,[reference])),[source['target']['ayahId']],start+offset,backend.conf)
                                    row={'id':source['id'],'sourceSha256':source['sha256'],'model':model_name,'channel':channel,
                                        'alignmentModel':model,'alignmentInput':[reference],
                                        'windowMs':[start+offset,source['windowSeconds'][1]*1000],
                                        'inputPcmSha256':hashlib.sha256(wav.tobytes()).hexdigest(),**entries}
                                    assess(row,source['target'],contract)
                                    report['measurements'].append(row)
                                    S.emit(row,'TAIL_CLIPPING_DUAL_PART')
                        backend.clear();gc.collect()
        load_plan()
        B.require(len(report['measurements'])==40 and len(report['freeResults'])==4,'incomplete measurement matrix')
        report['measurementComplete']=True
    except Exception as exc:
        report['errors'].append({'type':type(exc).__name__,'message':str(exc)[:240]})
    finally:
        S.emit(report,'TAIL_CLIPPING_REPORT')
    return 0 if report['measurementComplete'] else 1

if __name__=='__main__':raise SystemExit(main())
