"""Read-only pinned Quran measurements with normalization of one target only."""
import argparse, hashlib, json, os, sys, time
from pathlib import Path
import ci_kalbani_generic as G
ROOT=G.ROOT
sys.path.insert(0,str(ROOT/'tools/alignment_v3'))
import quran_ctc_model as Q
from alignment_input_variants import METHODS, alignment_variant

def target_inputs(refs, lo, hi, target, method):
    if not 1<=lo<=target<=hi<=len(refs) or method not in METHODS[1:]:
        raise ValueError('Explicit bounded target and known normalization required')
    return [Q.reference_text(alignment_variant(refs[i-1],method if i==target else 'canonical'))
            for i in range(lo,hi+1)]

def validated_full_plan(plan, evidence, surah):
    if (plan.get('reciterId')!='a_klb' or plan.get('riwaya')!='hafs'
            or plan.get('canonicalTextChanged') is not False or plan.get('productionChanged') is not False
            or plan.get('fullSurahOriginals') is not True or surah not in (5,9,10,11)
            or evidence.get('reciterId')!='a_klb' or evidence.get('riwaya')!='hafs'):
        raise ValueError('Only explicitly verified original 1435 source population is eligible')
    req=[x for x in plan['surahs'] if x['surah']==surah]
    sources=[x for x in evidence['sources'] if x['surah']==surah]
    if len(req)!=1 or len(sources)!=1:raise ValueError('Missing or duplicate original source')
    request,source=req[0],sources[0]
    if (request['sourceSha256']!=source['sha256'] or request['sourceUrl']!=source['url']
            or source['item']!='14352014_201801GGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGY'
            or source['metadataFile']['source']!='original' or not source['metadataFile']['name'].endswith('.mp3')
            or source['sourceBytesChanged'] or source['locallyTranscoded'] or not source['accepted']
            or source['decoderErrors'] or source['decodeRc']!=0):
        raise ValueError('Unverified or changed original publisher source')
    return source

def full_measurement(plan_bytes, plan, surah):
    evidence=json.loads((ROOT/'ops/source-repair/kalbani-1435-remaining-source-evidence-20261002.json').read_text())
    source=validated_full_plan(plan,evidence,surah)
    G.R.LOCAL_CACHE=ROOT/'scratch/kalbani-quran-original-native';G.R.MIRROR.update(riwaya=None,reciter=None);G.R._mirror_url=lambda url:None
    native=Path(G.R._local_audio(source['url']));data=native.read_bytes()
    if (hashlib.sha256(data).hexdigest()!=source['sha256'] or len(data)!=int(source['metadataFile']['size'])
            or hashlib.md5(data).hexdigest()!=source['metadataFile']['md5']):raise ValueError('Whole publisher SHA/MD5/size changed')
    duration=G.R._file_duration_ms(native);pcm=G.R._full_decode_pcm(native)
    if abs(duration-source['nativeDurationMs'])>2:raise ValueError('Original physical frame duration changed')
    model=Q.configure();result=G.W.C.run_surah(str(native),surah,'hafs',quran_model=True)
    result.update(sha256=source['sha256'],audioSha256=source['sha256'],sourceUrl=source['url'],fileRef=source['url'],sourceUnmodified=True,
                  canonicalTextChanged=False,nativeDecodedMs=len(pcm)//16,runtime={'precision':'float32','threads':2},
                  provenance={'source':'ci','run_id':os.environ['GITHUB_RUN_ID'],'run_sha':os.environ['GITHUB_SHA'],
                  'tool':'tools/index_qa/ci_kalbani_quran_inputs.py','tool_sha':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'plan_sha':hashlib.sha256(plan_bytes).hexdigest()})
    print('KALBANI_FULL_QURAN_RESULT='+json.dumps(result,ensure_ascii=False),flush=True)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--plan',required=True);ap.add_argument('--surah',type=int,required=True);a=ap.parse_args()
    path=ROOT/a.plan
    if (path.parent!=ROOT/'ops/source-repair' or not path.name.startswith('kalbani-float-quran-input-plan-')
            or path.suffix!='.json' or os.environ.get('CTC_INT8')!='0' or os.environ.get('CTC_THREADS')!='2'
            or not os.environ.get('GITHUB_RUN_ID') or not os.environ.get('GITHUB_SHA')):
        raise ValueError('Immutable read-only CI float32 plan required')
    plan_bytes=path.read_bytes();plan=json.loads(plan_bytes)
    if plan.get('fullSurahOriginals') is True:
        full_measurement(plan_bytes,plan,a.surah);return
    evidence=json.loads((ROOT/'ops/source-repair/kalbani-clean-vorbis-source-evidence-20261001.json').read_text())
    request,source=G.validated_plan(json.loads(plan_bytes),evidence['sources'],a.surah)
    G.R.LOCAL_CACHE=ROOT/'scratch/kalbani-quran-input-native';G.R.MIRROR.update(riwaya=None,reciter=None);G.R._mirror_url=lambda url:None
    native=Path(G.R._local_audio(source['url']))
    if hashlib.sha256(native.read_bytes()).hexdigest()!=source['sha256']:raise ValueError('Whole original publisher SHA changed')
    pcm=G.native_pcm(native,source['nativeDurationMs']);model=Q.configure();begin,end,_=G.surah_slice(G.load_index(),a.surah);refs=G.load_text('hafs')[begin:end]
    provenance={'source':'ci','run_id':os.environ['GITHUB_RUN_ID'],'run_sha':os.environ['GITHUB_SHA'],
                'tool':'tools/index_qa/ci_kalbani_quran_inputs.py','tool_sha':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'plan_sha':hashlib.sha256(plan_bytes).hexdigest()}
    count=0
    for win in request['windows']:
        lo,hi=win['range'];ws,we=win['windowMs'];target=win['target'];clip=pcm[ws*16:we*16]
        if len(clip)!=(we-ws)*16:raise ValueError('Incomplete native context')
        # Validate every input before inference; all other verses keep their canonical input.
        variants=[(m,target_inputs(refs,lo,hi,target,m)) for m in METHODS[1:]]
        lead=[Q.reference_text('بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ')] if lo==1 and a.surah not in [1,9] else []
        emissions=G.W.C._emissions(clip)
        for method,inputs in variants:
            fullraw=G.W.C._segment(emissions,len(clip),lead+inputs);raw=fullraw[len(lead):]
            rows=[{'ayahIdx':i+lo-1,'startMs':ws+int(st*1000),'endMs':ws+int(en*1000),'conf':min(G.W.C._conf(score),.74),'snapped':False} for i,(st,en,score) in enumerate(raw)]
            for i in range(len(rows)-1):rows[i]['endMs']=rows[i+1]['startMs']
            measured={'reciterId':'a_klb','surah':a.surah,'riwaya':'hafs','target':target,'range':[lo,hi],'windowMs':[ws,we],
                'sourceSha256':source['sha256'],'alignmentModel':model,'alignmentInput':lead+inputs,'entries':rows,
                'leadMeasurements':[{'startMs':ws+int(st*1000),'endMs':ws+int(en*1000),'conf':G.W.C._conf(sc)} for st,en,sc in fullraw[:len(lead)]],
                'inputNormalization':method,'normalizationAyahs':[target],'canonicalTextChanged':False,'runtime':{'precision':'float32','threads':2},
                'actualMeasurementTs':time.time(),'provenance':provenance,'selected':None}
            print('KALBANI_QURAN_INPUT_WINDOW='+json.dumps(measured,ensure_ascii=False),flush=True);count+=1
    print('KALBANI_QURAN_INPUT_COMPLETE='+json.dumps({'surah':a.surah,'windows':len(request['windows']),'measurements':count,'sourceSha256':source['sha256'],'nativeDurationMs':len(pcm)//16,'provenance':provenance}),flush=True)
if __name__=='__main__':main()
