"""Read-only Quran-model recovery of three sources where generic CTC lost verses.

Original audio and canonical text remain unchanged. Full source alignment is a
candidate measurement, never an assertion that forced verses were heard.
"""
import argparse
import gc
import importlib
import os
from pathlib import Path
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parent))
import final_verse_free_batch as B
import independent_window_pilot as P
S=B.S
SOURCES={
 'benkirane77':{"surah":77,"riwaya":"warsh","url":"https://server16.mp3quran.net/A-Benkirane/Rewayat-Warsh-A-n-Nafi/077.mp3","sha256":"b6c7c2949373d2285eea057fa2b63e987a66793dff0e491064dabcfebcbd81b4","requestedWindowSeconds":[0,65]},
 'benkirane51':{"surah":51,"riwaya":"warsh","url":"https://server16.mp3quran.net/A-Benkirane/Rewayat-Warsh-A-n-Nafi/051.mp3","sha256":"7edb05c3b0f7ebe2f37d5af3c9949727cef50772cbc4857b5745c7a92fab7dbf","requestedWindowSeconds":[0,65]},
 'yousef107':{"surah":107,"riwaya":"hafs","url":"https://server9.mp3quran.net/yousef/107.mp3","sha256":"cbbaf0650b648b3572b02c58e042a7599d88e09dca0b149f2cf07cce1ea481eb","requestedWindowSeconds":[0,36]},
 'mrifai84':{'surah':84,'riwaya':'hafs','url':'https://server11.mp3quran.net/mrifai/084.mp3',
  'sha256':'9f5d858255f19262e9d3fb817b160f72c06ec6db86c6aa3c3519388dbc367e86','requestedWindowSeconds':[0,65]},
 'saad22':{'surah':22,'riwaya':'hafs','url':'https://media.way2quran.com/saad-almqren/hafs-an-asim/22.mp3',
  'sha256':'2198db4e1e4e3d0c18a84441b92e4e11315cb49bd23e0be87e5b04e44c96c0c5','requestedWindowSeconds':[0,25]},
 'shamrani79':{'surah':79,'riwaya':'hafs','url':'https://media.way2quran.com/saleh-alshamrani/hafs-an-asim/079.mp3',
  'sha256':'ef9cfec33cb9fe061f35283fd2bb6f329e43ac444386e890cac5c9ba0962e533','requestedWindowSeconds':[28,70]},
 'saad28':{**S.SOURCES[1],'riwaya':'hafs','requestedWindowSeconds':[620,690]},
 'saad45':{**S.SOURCES[0],'riwaya':'hafs','requestedWindowSeconds':[0,25]},
}


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',choices=tuple(SOURCES),required=True)
    ap.add_argument('--model-policy',choices=('cache-only','quran-pinned-ephemeral'),default='cache-only')
    a=ap.parse_args(argv);source=SOURCES[a.source]
    report={'schema':1,'kind':'known-source-quran-alignment-diagnostic','sourceId':a.source,
      'measurementComplete':False,'qualityClaim':False,'coverageCertified':False,'productionChanged':False,
      'source':source,'freeResults':[],'models':[],'errors':[],
      'limits':['Forced full alignment does not prove all verses present.','Original generic and free-ASR failures remain part of the evidence.','Candidate requires independent QA before registration or adoption.'],
      'provenance':{'runId':os.environ.get('GITHUB_RUN_ID',''),'runSha':os.environ.get('GITHUB_SHA',''),'toolSha256':S.sha_file(__file__)}}
    try:
        B.require(os.environ.get('CTC_INT8')=='0' and os.environ.get('CTC_THREADS')=='2','fixed float32 runtime required')
        report['versions']=S.validate_versions()
        for name in ('HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE','HF_HUB_DISABLE_XET'):os.environ[name]='1'
        with tempfile.TemporaryDirectory(prefix='rafiq-quran-recovery-',dir=os.environ.get('RUNNER_TEMP')) as tmp:
            path=Path(tmp)/(a.source+'.mp3')
            receipt=S.metadata.fetch(source['url'],path,limit=32*1024*1024)
            B.require(receipt['sha256']==source['sha256'],'source hash mismatch')
            collector,proof=B.decode(path,source)
            B.require(proof['decoded']['durationSeconds']<1500,'unexpected source duration')
            report['audio']={'download':receipt,**proof}
            contract=P.load_contract()
            with S.model_snapshots(a.model_policy) as (snapshots,inventory):
                report['modelAcquisition']=inventory
                if a.source in ('shamrani79','mrifai84','benkirane77','benkirane51','yousef107'):
                    window=dict(source,windowSeconds=[collector.start/S.RATE,min(collector.frames,collector.end)/S.RATE])
                    for spec in S.MODELS:
                        backend=S.FreeCTC(snapshots[spec['name']],spec)
                        report['models'].append({**spec,'vocabulary':backend.vocabulary,'files':S.model_files(snapshots[spec['name']],spec)})
                        for channel,raw in collector.channels().items():
                            result=S.measure_window(backend,raw,window,channel,spec['name'],
                                checkpoint=lambda part:S.emit(part,'SOURCE_RECOVERY_FREE_PART'))
                            report['freeResults'].append(result)
                        del backend;gc.collect()
                import huggingface_hub as hub
                specs=P.model_specs(contract)
                bound={(s['id'],s['revision']):snapshots[s['name']] for s in specs}
                with P.offline_model_loads(hub,specs,bound):
                    C=importlib.import_module('ctc_seg')
                    report['alignment']=C.run_surah(str(path),source['surah'],source['riwaya'],quran_model=True)
                    C._M.clear();gc.collect()
            B.require(S.sha_file(path)==source['sha256'],'source changed after inference')
            alignment=report['alignment']
            expected={79:46,28:88,45:37,22:78,84:25,77:50,51:60,107:7}[source['surah']]
            B.require(len(alignment['entries'])==expected,'incomplete result population')
            report['lowOrMissing']=[e['ayahIdx']+1 for e in alignment['entries'] if e['startMs'] is None or e['conf']<.45]
            report['measurementComplete']=True
    except Exception as exc:
        report['errors'].append({'type':type(exc).__name__,'message':str(exc)[:240]})
    finally:
        S.emit(report,'SOURCE_RECOVERY_QURAN_REPORT')
    return 0 if report['measurementComplete'] else 1

if __name__=='__main__':raise SystemExit(main())
