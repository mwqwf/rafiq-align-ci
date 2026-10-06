"""Read-only Quran-model recovery of three sources where generic CTC lost verses.

Original audio and canonical text remain unchanged. Full source alignment is a
candidate measurement, never an assertion that forced verses were heard.
"""
import argparse
import gc
import hashlib
import json
import importlib
import os
from pathlib import Path
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parent))
import final_verse_free_batch as B
import independent_window_pilot as P
S=B.S
SOURCES={'iraoui86_surahs_s41': {'surah': 41, 'riwaya': 'warsh', 'url': 'https://archive.org/download/55555555555033alahzab_202004/041Fossilat.mp3', 'sha256': 'f655b81ea9926ddd8c134ef04c197b550ffd954896c43229a2f01c6be1d1986b', 'requestedWindowSeconds': [0, 65]}, 'shamrani_new_archive_s79': {'surah': 79, 'riwaya': 'hafs', 'url': 'https://archive.org/download/x00xxxx2_20220807xxx/079%20%20%D8%B3%D9%88%D8%B1%D8%A9%20%D8%A7%D9%84%D9%86%D8%A7%D8%B2%D8%B9%D8%A7%D8%AA.mp3', 'sha256': 'da9ec6ff96d0159736ffadcb008b062041d264f66bc6b17b952b7a5206f88d45', 'requestedWindowSeconds': [25, 70]}}
SOURCES.update({
 'a_abdl37':{'surah':37,'riwaya':'hafs',
  'url':'https://server16.mp3quran.net/a_abdl/Rewayat-Hafs-A-n-Assem/037.mp3',
  'sha256':'3637f71ec241fe9e95f39ad6071db0403472c833e8e43c56eaaa7289d5ef3fb4','requestedWindowSeconds':[0,65]},
 'fakhfakh38_midad':{'surah':38,'riwaya':'qalun',
  'url':'https://fra1.digitaloceanspaces.com/media.midad.com/resources/ar/recitations/47022/457496/038.mp3',
  'sha256':'930f4e059219553bbcf0d7b7ec453e0aa0f72e9a555a9d61df4528220e2674ec','requestedWindowSeconds':[0,65]},
 'fakhfakh38_archive_2025':{'surah':38,'riwaya':'qalun',
  'url':'https://archive.org/download/al-hadi-al-fakhfakh/038.mp3',
  'sha256':'fded733764386de895b63df4b067f44accee12186785396a3f61928a0fa3c212','requestedWindowSeconds':[0,65]},
 'asiri7_archive_4917':{'surah': 7, 'riwaya': 'hafs',
  'url':'https://archive.org/download/002_20230924_202309/007%20-%20%D8%B3%D9%88%D8%B1%D8%A9%20%D8%A7%D9%84%D8%A3%D8%B9%D8%B1%D8%A7%D9%81.mp3',
  'sha256':'897ad7e2c99472111722247f362d135da0c25c449806260269a792a12f52d3f1','requestedWindowSeconds':[0,65]},
 'asiri7_archive_4917_audit':{'surah': 7, 'riwaya': 'hafs',
  'url':'https://archive.org/download/002_20230924_202309/007%20-%20%D8%B3%D9%88%D8%B1%D8%A9%20%D8%A7%D9%84%D8%A3%D8%B9%D8%B1%D8%A7%D9%81.mp3',
  'sha256':'897ad7e2c99472111722247f362d135da0c25c449806260269a792a12f52d3f1','requestedWindowSeconds':[0,65]},
 'asiri7_archive_4917_targeted':{'surah': 7, 'riwaya': 'hafs',
  'url':'https://archive.org/download/002_20230924_202309/007%20-%20%D8%B3%D9%88%D8%B1%D8%A9%20%D8%A7%D9%84%D8%A3%D8%B9%D8%B1%D8%A7%D9%81.mp3',
  'sha256':'897ad7e2c99472111722247f362d135da0c25c449806260269a792a12f52d3f1','requestedWindowSeconds':[0,65]},
 'asiri7_archive_4917_48_expanded':{'surah': 7, 'riwaya': 'hafs',
  'url':'https://archive.org/download/002_20230924_202309/007%20-%20%D8%B3%D9%88%D8%B1%D8%A9%20%D8%A7%D9%84%D8%A3%D8%B9%D8%B1%D8%A7%D9%81.mp3',
  'sha256':'897ad7e2c99472111722247f362d135da0c25c449806260269a792a12f52d3f1','requestedWindowSeconds':[0,65]},
 'tblawi7_nquran':{'surah': 7, 'riwaya': 'hafs', 'url': 'https://www.nquran.com/audiof/quran/mohd_muh_tablawee/007.mp3', 'sha256': '76b0d10dbb33d90cdbb98e71786653a497dbe73f7af704bf2297848ce1fbc547', 'requestedWindowSeconds': [0, 65]},
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
})
SOURCES['fakhfakh38_archive_2025_audit']={
    **SOURCES['fakhfakh38_archive_2025']}
ASIRI7_SOURCES=('asiri7_archive_4917','asiri7_archive_4917_audit',
                'asiri7_archive_4917_targeted','asiri7_archive_4917_48_expanded')
FAKHFAKH38_SOURCES=('fakhfakh38_archive_2025',
                    'fakhfakh38_archive_2025_audit')
ALIGNMENT_ENGINE='ctc-quran-surah-1'


def source_engine_blocked(source):
    """Return a recorded exact-source/engine failure; mirrors stay eligible."""
    rows=json.loads((B.ROOT/'tools/ci_fleet/blocked_realigns.json').read_text())
    return next((row for row in rows
                 if row['riwaya']==source['riwaya']
                 and int(row['surah'])==int(source['surah'])
                 and row['source']==source['url']
                 and row['engine']==ALIGNMENT_ENGINE),None)


def require_source_engine_eligible(source):
    """Fail closed for a recorded exact-source/engine failure."""
    blocked=source_engine_blocked(source)
    if blocked is not None:
        B.require(False,
                  f"exact source/engine already failed without a complete candidate: {blocked['run']}")


def fakhfakh_audit_windows(primary_alignment):
    """Independent numeric witnesses; boundary verses remain full-alignment witnesses."""
    primary=primary_alignment['entries']
    return [
      {'id':'opening-1-5','startAyahIdx':0,'endAyahIdxExclusive':5,
       'targetAyahIdxs':[1,2,3],'audioStartMs':0,
       'audioEndMs':min(primary_alignment['totalMs'],primary[4]['endMs']+45000)},
      {'id':'middle-40-48','startAyahIdx':39,'endAyahIdxExclusive':48,
       'targetAyahIdxs':[42,43,44],
       'audioStartMs':max(0,primary[39]['startMs']-60000),
       'audioEndMs':min(primary_alignment['totalMs'],primary[47]['endMs']+60000)},
      {'id':'ending-81-88','startAyahIdx':80,'endAyahIdxExclusive':88,
       'targetAyahIdxs':[83,84,85,86],
       'audioStartMs':max(0,primary[80]['startMs']-60000),
       'audioEndMs':primary_alignment['totalMs']},
    ]


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',choices=tuple(SOURCES),required=True)
    ap.add_argument('--model-policy',choices=('cache-only','quran-pinned-ephemeral'),default='cache-only')
    a=ap.parse_args(argv);source=SOURCES[a.source]
    require_source_engine_eligible(source)
    if a.source=='a_abdl37':
        import source_context_diagnostics as contexts
        pinned,_=contexts.load_source('penultimate_hafs_a_abdl_37')
        metadata=(B.ROOT/'ops/out/codex-a-abdl37-displaced-tail-report-20261006.json').read_bytes()
        B.require(hashlib.sha256(metadata).hexdigest()=='4a65021cd79e3051913c7e5b590231bf1bb300a8e22c66cad820d6c6483dbbf5','measured source report changed')
        measured=json.loads(metadata)
        B.require(measured['measurementComplete'] and not measured['errors'] and measured['audio']['decoded']['decodedWithoutErrors'],'source decode measurement incomplete')
        B.require(all(source[k]==pinned[k]==measured['source'][k] for k in ('surah','riwaya','url','sha256')),'pinned production source changed')
        B.require(measured['audio']['sourceUnchanged'] and measured['audio']['download']['sha256']==source['sha256'],'measured audio mismatch')
    if a.source=='fakhfakh38_midad':
        metadata=(B.ROOT/'ops/out/codex-fakhfakh38-midad-metadata-20261006.json').read_bytes()
        B.require(hashlib.sha256(metadata).hexdigest()=='138cc16e368b13740237538606ee4ff9e21c9199501b0e58baf5ab66e6e773ae','publisher metadata changed')
        measured=json.loads(metadata)['sources'][0]
        B.require(measured['ok'] and measured['pcm']['decodedWithoutErrors'] and measured['stereo']['decodedWithoutErrors'] and not measured['stereo']['phaseCancellationSuspected'],'unhealthy publisher source')
        B.require(source['sha256']==measured['file']['sha256'] and source['url']==measured['file']['finalUrl'] and source['surah']==measured['surah'] and source['riwaya']==measured['riwaya'],'publisher metadata source mismatch')
        B.require(measured['requestedUrl']=='https://midad.com/recitation/114900' and measured['resolutionMethod']=='publisher-contentUrl','publisher resolution changed')
    if a.source in FAKHFAKH38_SOURCES:
        metadata=(B.ROOT/'ops/source-repair/fakhfakh-qalun-38-archive-mirror-audit-20261006.json').read_bytes()
        B.require(hashlib.sha256(metadata).hexdigest()=='c1652760ce7c54ef19211e3f2cbbb725412b77425e3f03b5ca620a7938a9e3dc','Archive mirror audit changed')
        audit=json.loads(metadata)
        measured=audit['archive2025Mirror']
        publisher=audit['publisherSource']
        B.require(audit['readOnly'] and not audit['productionChanged'] and not audit['candidateBuilt'] and not audit['coverageCertified'],'invalid mirror audit disposition')
        B.require(audit['comparisons']['archive2025EqualsPublisherDecodedMono16k'] and audit['comparisons']['archive2025PublisherPcmBytesEqual'],'Archive mirror is not publisher PCM')
        B.require(source['sha256']==measured['container']['sha256'] and source['url']==measured['url'] and source['surah']==audit['scope']['surah'] and source['riwaya']==audit['scope']['riwaya'],'Archive mirror audit mismatch')
        B.require(measured['decodedMono16k']['sha256']==publisher['decodedMono16k']['sha256']=='590f6a633c83e8da4f2e998dc6ed3e33b6a0fbda0bdc4c2e6b32bea8ab14ffeb','Archive/Midad mono PCM changed')
    if a.source=='tblawi7_nquran':
        metadata=(B.ROOT/'ops/out/codex-tblawi-nquran-metadata-37406467384.json').read_bytes()
        B.require(hashlib.sha256(metadata).hexdigest()=='222a0abcea6e4ac6444eac886a4bcf00ca24a590f9cd3e6d883e04ee86002ed2','publisher metadata changed')
        measured=json.loads(metadata)['sources'][0]
        B.require(measured['ok'] and measured['pcm']['decodedWithoutErrors'] and measured['file']['sha256']==source['sha256'] and measured['file']['finalUrl']==source['url'],'unhealthy/mismatched source')
    if a.source in ('iraoui86_surahs_s41', 'shamrani_new_archive_s79'):
        metadata=(B.ROOT/'ops/out/codex-new-archive-metadata-37413567942.json').read_bytes()
        B.require(hashlib.sha256(metadata).hexdigest()=='94c95c7b5f327dc9ee11e06a04de195ca45b99049148135dbab38b0d5b6da830','new source metadata changed')
        measured=next(m for m in json.loads(metadata)['sources'] if m['id']==a.source)
        B.require(measured['ok'] and measured['pcm']['decodedWithoutErrors'] and measured['stereo']['decodedWithoutErrors'] and not measured['stereo']['phaseCancellationSuspected'],'unhealthy source')
        B.require(source['sha256']==measured['file']['sha256'] and source['url']==measured['requestedUrl'] and source['surah']==measured['surah'] and source['riwaya']==measured['riwaya'],'metadata source mismatch')
    if a.source in ASIRI7_SOURCES:
        metadata_path=B.ROOT/'ops/out/codex-asiri7-archive-4917-metadata-20261006.json'
        measured=json.loads(metadata_path.read_text())
        B.require(measured['measurementRuntime']=='local-session' and measured['identityVerifiedAgainstKnownPerformance'],'unverified reader performance')
        B.require(measured['decodedPcmMono16k']['decodedWithoutErrors'] and not measured['decodedPcmMono16k']['longSilences'],'unhealthy source candidate')
        B.require(source['sha256']==measured['file']['sha256'] and source['url']==measured['requestedUrl'] and source['surah']==measured['surah'] and source['riwaya']==measured['riwaya'],'metadata source mismatch')
    report={'schema':1,'kind':'known-source-quran-alignment-diagnostic','sourceId':a.source,
      'measurementComplete':False,'qualityClaim':False,'coverageCertified':False,'productionChanged':False,
      'source':source,'freeResults':[],'models':[],'errors':[],
      'textGenerationDisabled':a.source in ASIRI7_SOURCES,
      'independentRemeasurement':a.source in ('asiri7_archive_4917_audit',
                                              'fakhfakh38_archive_2025_audit'),
      'targetedLowConfidenceRemeasurement':a.source=='asiri7_archive_4917_targeted',
      'expandedAyah48Remeasurement':a.source=='asiri7_archive_4917_48_expanded',
      'limits':['Forced full alignment does not prove all verses present.','Original generic and free-ASR failures remain part of the evidence.','Candidate requires independent QA before registration or adoption.'],
      'provenance':{'runId':os.environ.get('GITHUB_RUN_ID',''),'runSha':os.environ.get('GITHUB_SHA',''),'toolSha256':S.sha_file(__file__)}}
    try:
        B.require(os.environ.get('CTC_INT8')=='0' and os.environ.get('CTC_THREADS')=='2','fixed float32 runtime required')
        report['versions']=S.validate_versions()
        for name in ('HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE','HF_HUB_DISABLE_XET'):os.environ[name]='1'
        with tempfile.TemporaryDirectory(prefix='rafiq-quran-recovery-',dir=os.environ.get('RUNNER_TEMP')) as tmp:
            path=Path(tmp)/(a.source+'.mp3')
            receipt=S.metadata.fetch(source['url'],path,limit=35032209 if a.source=='tblawi7_nquran' else 32*1024*1024)
            B.require(receipt['sha256']==source['sha256'],'source hash mismatch')
            collector,proof=B.decode(path,source)
            duration_limit=5000 if a.source in ASIRI7_SOURCES else (4400 if a.source=='tblawi7_nquran' else 1500)
            B.require(proof['decoded']['durationSeconds']<duration_limit,'unexpected source duration')
            if a.source=='tblawi7_nquran':
                B.require(receipt['bytes']==35032209 and proof['decoded']['frames']==70049542,'new publisher source differs from measured metadata')
            if a.source in ('iraoui86_surahs_s41', 'shamrani_new_archive_s79', 'fakhfakh38_midad'):
                B.require(receipt['bytes']==measured['file']['bytes'] and proof['decoded']['frames']==measured['pcm']['samples'],'source differs from exact measured frames')
            if a.source in FAKHFAKH38_SOURCES:
                B.require(receipt['bytes']==measured['container']['bytes'] and proof['decoded']['frames']==measured['decodedNativeStereo16k']['frames'] and proof['decoded']['fullNativePcmSha256']==measured['decodedNativeStereo16k']['sha256'],'Archive mirror differs from exact audited PCM')
            if a.source in ASIRI7_SOURCES:
                B.require(receipt['bytes']==measured['file']['bytes'] and proof['decoded']['frames']==measured['decodedPcmMono16k']['samples'],'source differs from exact session measurement')
            if a.source=='a_abdl37':
                B.require(receipt['bytes']==measured['audio']['download']['bytes'] and proof['decoded']['frames']==measured['audio']['decoded']['frames'],'source differs from exact native measurement')
            report['audio']={'download':receipt,**proof}
            contract=P.load_contract()
            with S.model_snapshots(a.model_policy) as (snapshots,inventory):
                report['modelAcquisition']=inventory
                if a.source in ('iraoui86_surahs_s41','shamrani_new_archive_s79','shamrani79','mrifai84','benkirane77','benkirane51','yousef107','tblawi7_nquran','fakhfakh38_midad','fakhfakh38_archive_2025','a_abdl37'):
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
                    numeric_windows=None
                    primary_fakhfakh=None
                    if a.source=='fakhfakh38_archive_2025_audit':
                        primary_path=B.ROOT/'ops/out/codex-fakhfakh38-archive-recovery-37544489570.json'
                        primary_bytes=primary_path.read_bytes()
                        B.require(hashlib.sha256(primary_bytes).hexdigest()=='6fcad5cb6bd1354aae5d754274a3461b1ddf5ae4e6396f6464ce0776fb370c08','primary Fakhfakh report changed')
                        primary_report=json.loads(primary_bytes)
                        B.require(primary_report['measurementComplete'] and
                                  not primary_report['errors'] and
                                  len(primary_report['alignment']['entries'])==88,
                                  'primary Fakhfakh measurement incomplete')
                        primary_fakhfakh=primary_report['alignment']
                        numeric_windows=fakhfakh_audit_windows(primary_fakhfakh)
                    if a.source in ('asiri7_archive_4917_targeted','asiri7_archive_4917_48_expanded'):
                        primary_path=B.ROOT/'ops/out/codex-asiri7-left-context-alignment-success-37433349375.json'
                        primary_bytes=primary_path.read_bytes()
                        B.require(hashlib.sha256(primary_bytes).hexdigest()=='9426b3718b5b6a955ae6926263beeb66424a2dcad534c8b95172bbafdcdc8bac','primary Asiri report changed')
                        primary=json.loads(primary_bytes)['alignment']['entries']
                        numeric_windows=[]
                        if a.source=='asiri7_archive_4917_targeted':
                            for ayah in (13,48,54,131,188):
                                target=ayah-1;start=target-2;end=target+3
                                numeric_windows.append({'id':f'ayah-{ayah}-neighbors','startAyahIdx':start,
                                  'endAyahIdxExclusive':end,'targetAyahIdxs':[target],
                                  'audioStartMs':max(0,primary[start]['startMs']-60000),
                                  'audioEndMs':min(primary[-1]['endMs']+2016,primary[end-1]['endMs']+60000)})
                        else:
                            for label,start,end in (('a',42,58),('b',39,63)):
                                numeric_windows.append({'id':f'ayah-48-expanded-{label}','startAyahIdx':start,
                                  'endAyahIdxExclusive':end,'targetAyahIdxs':[47,48,49],
                                  'audioStartMs':max(0,primary[start]['startMs']-120000),
                                  'audioEndMs':min(primary[-1]['endMs']+2016,primary[end-1]['endMs']+120000)})
                    chunk_args=({'chunk_verses':29,'chunk_overlap':5}
                                if a.source in ('asiri7_archive_4917_audit',
                                                'fakhfakh38_archive_2025_audit') else
                                {'chunk_verses':32,'chunk_overlap':4}
                                if a.source in ('asiri7_archive_4917','asiri7_archive_4917_targeted','asiri7_archive_4917_48_expanded') else {})
                    report['alignment']=C.run_surah(str(path),source['surah'],source['riwaya'],
                                                    quran_model=True,numeric_windows=numeric_windows,**chunk_args)
                    C._M.clear();gc.collect()
            B.require(S.sha_file(path)==source['sha256'],'source changed after inference')
            alignment=report['alignment']
            expected={37:182,38:88,41:54,79:46,28:88,45:37,22:78,84:25,77:50,51:60,107:7,7:206}[source['surah']]
            B.require(len(alignment['entries'])==expected,'incomplete result population')
            if a.source in ASIRI7_SOURCES or a.source=='fakhfakh38_archive_2025_audit':
                overlap=alignment.get('chunkedAlignment',{})
                B.require(len(overlap.get('groups',[]))>1,'chunked alignment evidence missing')
                B.require(overlap.get('overlapAyahs'),'independent overlap evidence missing')
                B.require(overlap['maxStartDisagreementSeconds']<=5.0 and
                          overlap['maxEndDisagreementSeconds']<=5.0,
                          'overlapping alignment groups disagree by more than five seconds')
            if a.source=='fakhfakh38_archive_2025_audit':
                windows=alignment.get('numericWindowAudit',[])
                B.require([w['id'] for w in windows]==
                          ['opening-1-5','middle-40-48','ending-81-88'],
                          'opening/middle/ending witnesses missing')
                comparisons=[]
                for window in windows:
                    for target in window['targetAyahIdxs']:
                        local=next(e for e in window['entries'] if e['ayahIdx']==target)
                        full=alignment['entries'][target]
                        primary=primary_fakhfakh['entries'][target]
                        B.require(local['startMs'] is not None and
                                  local['endMs'] is not None,
                                  'independent witness boundary missing')
                        comparisons.append({
                          'witness':window['id'],'ayah':target+1,
                          'windowVsAuditStartDeltaMs':abs(local['startMs']-full['startMs']),
                          'windowVsAuditEndDeltaMs':abs(local['endMs']-full['endMs']),
                          'primaryVsAuditStartDeltaMs':abs(primary['startMs']-full['startMs']),
                          'primaryVsAuditEndDeltaMs':abs(primary['endMs']-full['endMs']),
                          'windowConfidence':local['conf'],
                          'auditConfidence':full['conf'],
                        })
                report['openingMiddleEndingComparison']=comparisons
                boundary_comparisons=[]
                for label,target in (('opening-boundary',0),('ending-boundary',87)):
                    full=alignment['entries'][target]
                    primary=primary_fakhfakh['entries'][target]
                    B.require(full['startMs'] is not None and full['endMs'] is not None,
                              'independent boundary witness missing')
                    boundary_comparisons.append({
                      'witness':label,'ayah':target+1,
                      'primaryVsAuditStartDeltaMs':abs(primary['startMs']-full['startMs']),
                      'primaryVsAuditEndDeltaMs':abs(primary['endMs']-full['endMs']),
                      'auditConfidence':full['conf'],
                    })
                report['boundaryComparisons']=boundary_comparisons
                B.require(max(max(d['windowVsAuditStartDeltaMs'],
                                  d['windowVsAuditEndDeltaMs'],
                                  d['primaryVsAuditStartDeltaMs'],
                                  d['primaryVsAuditEndDeltaMs'])
                              for d in comparisons)<=5000,
                          'independent opening/middle/ending boundary differs by more than five seconds')
                B.require(max(max(d['primaryVsAuditStartDeltaMs'],
                                  d['primaryVsAuditEndDeltaMs'])
                              for d in boundary_comparisons)<=5000,
                          'independent first/last boundary differs by more than five seconds')
            if a.source=='asiri7_archive_4917_targeted':
                windows=alignment.get('numericWindowAudit',[])
                B.require(len(windows)==5,'targeted numeric window evidence missing')
                deltas=[]
                for window in windows:
                    target=window['targetAyahIdxs'][0]
                    local=next(e for e in window['entries'] if e['ayahIdx']==target)
                    full=alignment['entries'][target]
                    B.require(local['startMs'] is not None and local['endMs'] is not None,'targeted measurement missing')
                    deltas.append({'ayah':target+1,'startDeltaMs':abs(local['startMs']-full['startMs']),
                                   'endDeltaMs':abs(local['endMs']-full['endMs']),'confidence':local['conf']})
                report['targetedLowConfidenceComparison']=deltas
                B.require(max(max(d['startDeltaMs'],d['endDeltaMs']) for d in deltas)<=5000,
                          'targeted low-confidence boundary differs by more than five seconds')
            if a.source=='asiri7_archive_4917_48_expanded':
                windows=alignment.get('numericWindowAudit',[])
                B.require(len(windows)==2,'expanded ayah-48 evidence missing')
                comparisons=[]
                for target in (47,48,49):
                    locals=[next(e for e in w['entries'] if e['ayahIdx']==target) for w in windows]
                    full=alignment['entries'][target]
                    comparisons.append({'ayah':target+1,
                      'crossWindowStartDisagreementMs':abs(locals[0]['startMs']-locals[1]['startMs']),
                      'crossWindowEndDisagreementMs':abs(locals[0]['endMs']-locals[1]['endMs']),
                      'fullStartDeltaMs':max(abs(e['startMs']-full['startMs']) for e in locals),
                      'fullEndDeltaMs':max(abs(e['endMs']-full['endMs']) for e in locals),
                      'windowConfidences':[e['conf'] for e in locals]})
                report['expandedAyah48Comparison']=comparisons
                B.require(max(max(d['crossWindowStartDisagreementMs'],d['crossWindowEndDisagreementMs'])
                              for d in comparisons)<=5000,
                          'expanded ayah-48 windows disagree by more than five seconds')
            report['lowOrMissing']=[e['ayahIdx']+1 for e in alignment['entries'] if e['startMs'] is None or e['conf']<.45]
            report['measurementComplete']=True
    except Exception as exc:
        report['errors'].append({'type':type(exc).__name__,'message':str(exc)[:240]})
    finally:
        S.emit(report,'SOURCE_RECOVERY_QURAN_REPORT')
    return 0 if report['measurementComplete'] else 1

if __name__=='__main__':raise SystemExit(main())
