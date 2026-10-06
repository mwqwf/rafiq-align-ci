"""Read-only, unprompted Whisper diagnostics for three unresolved Quran passages.

Different ASR architecture, pinned public model, unmixed native channels.
No timing, reference text, quality report, or production object is modified.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import wave
sys.path.insert(0,str(Path(__file__).resolve().parent))
import final_verse_free_batch as B
S=B.S
CPP='eacbd8234c6654cdbf2c377f72b2106875479bdc'
MODEL={'url':'https://github.com/mwqwf/rafiq-align-ci/releases/download/model-whisper-base-ar-quran-q51/ggml-q5_1.bin',
       'bytes':59707625,'sha256':'acc1f03c8b1468b674b4fab50e0b2312cff982ba0001cd16fe36ca23862b6536',
       'hfRepo':'tarteel-ai/whisper-base-ar-quran','hfRevision':'5c3c53fdf9272c4f6ee0bee09a1e5a4a615ee25c',
       'license':'Apache-2.0','quantization':'q5_1'}
INPUTS=(
 ('saad28','4f4fd390701f225c2e38346be154cba1f0bf97136abcb468572128afe308613d',[620,690]),
 ('saad45','ddf348363400297ca608363339554c6f01b2ded143a2c808b4e30899a45faf13',[345,382]),
 ('shamrani79','6e90bee9778e63a7b4c31518e23d8bf08db9a4b0b3a791a4992e5c5d6202d0a4',[28,70]),
)


def sources():
    out=[]
    for ident,sha,window in INPUTS:
        p=B.ROOT/f'ops/out/codex-source-quran-{ident}-37389920485.json'
        B.require(S.sha_file(p)==sha,'source report changed')
        report=json.loads(p.read_bytes());source=report['source'].copy()
        B.require(report['measurementComplete'] and not report['errors'],'unverified source report')
        source.update(id=ident,requestedWindowSeconds=window)
        source.pop('windowSeconds',None)
        B.require(0<=window[0]<window[1] and window[1]-window[0]<=70,'invalid diagnostic window')
        S.metadata.validate_url(source['url']);out.append(source)
    return out


def main():
    report={'schema':1,'kind':'whisper-unprompted-source-recovery-diagnostic','qualityClaim':False,
      'measurementComplete':False,'productionChanged':False,'canonicalTextRead':False,'forcedAlignment':False,
      'model':MODEL,'whisperCppCommit':CPP,'sources':[],'results':[],'errors':[],
      'limits':['Autoregressive ASR can hallucinate; text presence or absence is not certified.',
                'Quantized base model is diagnostic, not a timing witness.',
                'Native channel agreement is not independent model confirmation.'],
      'provenance':{'runId':os.environ.get('GITHUB_RUN_ID',''),'runSha':os.environ.get('GITHUB_SHA',''),
                    'toolSha256':S.sha_file(__file__)}}
    try:
        planned=sources();code=B.ROOT/'wsrc';cli=code/'build/bin/whisper-cli'
        commit=subprocess.run(['git','-C',str(code),'rev-parse','HEAD'],capture_output=True,text=True,check=True).stdout.strip()
        B.require(commit==CPP and cli.is_file(),'Whisper executable source revision mismatch')
        report['binarySha256']=S.sha_file(cli)
        report['cliVersion']=subprocess.run([str(cli),'--version'],capture_output=True,text=True,check=True,timeout=10).stdout.strip()
        with tempfile.TemporaryDirectory(prefix='rafiq-whisper-recovery-',dir=os.environ.get('RUNNER_TEMP')) as tmp:
            tmp=Path(tmp);model=tmp/'model.bin';receipt=S.metadata.fetch(MODEL['url'],model,limit=MODEL['bytes'])
            B.require(receipt['bytes']==MODEL['bytes'] and receipt['sha256']==MODEL['sha256'],'public model bytes mismatch')
            report['modelDownload']=receipt
            for source in planned:
                try:
                    audio=tmp/'source.mp3';download=S.metadata.fetch(source['url'],audio,limit=B.MAX_SOURCE_BYTES)
                    B.require(download['sha256']==source['sha256'],'audio source changed')
                    collector,proof=B.decode(audio,source);report['sources'].append({'id':source['id'],'download':download,**proof})
                    for channel,pcm in collector.channels().items():
                        wav=tmp/f"{source['id']}-{channel}.wav"
                        with wave.open(str(wav),'wb') as f:
                            f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(pcm)
                        prefix=tmp/f"{source['id']}-{channel}"
                        argv=[str(cli),'-m',str(model),'-f',str(wav),'-l','ar','-t','2','-ng',
                              '-mc','0','-bs','1','-bo','1','-tp','0','-tpi','0','-nf','-ojf','-of',str(prefix)]
                        process=subprocess.run(argv,capture_output=True,timeout=720)
                        B.require(process.returncode==0,'Whisper inference failed')
                        raw=prefix.with_suffix('.json').read_bytes();B.require(0<len(raw)<=2_000_000,'invalid JSON output size')
                        payload=json.loads(raw);B.require(isinstance(payload.get('transcription'),list),'missing transcription')
                        result={'sourceId':source['id'],'sourceSha256':source['sha256'],'channel':channel,
                          'windowSeconds':[collector.start/S.RATE,min(collector.frames,collector.end)/S.RATE],
                          'inputPcmSha256':hashlib.sha256(pcm).hexdigest(),'inputSampleCount':len(pcm)//2,
                          'modelSha256':MODEL['sha256'],'canonicalPrompt':None,'temperature':0,'maxTextContext':0,
                          'rawOutputSha256':hashlib.sha256(raw).hexdigest(),'rawOutput':payload,
                          'rawOutputBase64':base64.b64encode(raw).decode('ascii')}
                        S.emit(result,'WHISPER_RECOVERY_PART');report['results'].append({k:v for k,v in result.items() if k not in ('rawOutput','rawOutputBase64')})
                    audio.unlink();B.require(S.sha_file(model)==MODEL['sha256'],'model changed during inference')
                except Exception as exc:report['errors'].append({'sourceId':source['id'],'type':type(exc).__name__})
            sources();report['measurementComplete']=not report['errors'] and len(report['sources'])==len(planned)
    except Exception as exc:report['errors'].append({'type':type(exc).__name__})
    finally:S.emit(report,'WHISPER_RECOVERY_REPORT')
    return 0 if report['measurementComplete'] else 1


if __name__=='__main__':raise SystemExit(main())
