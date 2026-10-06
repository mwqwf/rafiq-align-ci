"""تدقيق قارئ فقط لمنشأ مرساة الحاقة؛ لا تعديل حكم أو توقيت أو ملف صوت."""
import hashlib,importlib,json,os,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import source_context_diagnostics as D
B,P,S=D.B,D.P,D.S

def main():
 rep={'schema':1,'kind':'heard-anchor-provenance-diagnostic','measurementComplete':False,'qualityClaim':False,'productionChanged':False,'errors':[], 'provenance':{'runId':os.environ.get('GITHUB_RUN_ID'),'runSha':os.environ.get('GITHUB_SHA'),'toolSha256':S.sha_file(__file__)}}
 try:
  src,_=D.load_source('balilah69_disputed25_27');rep['source']=src
  B.require(src['sha256']=='9fa2851995b76495854440c097a1e3f1834ea40d58b3bb09e982b13fa09ea6f5','مصدر مختلف')
  B.require(os.environ.get('CTC_INT8')=='0' and os.environ.get('CTC_THREADS')=='2','نسخة الاستدلال مختلفة')
  B.require(os.environ.get('SAAD_CACHE_EXACT_HIT')=='true','ذاكرة النموذج غير مثبتة');rep['versions']=S.validate_versions()
  import huggingface_hub as hub
  inv=[];cache=Path(os.environ['HF_HOME']).resolve();generic=S.MODELS[0];P.require_cached_models(hub,[generic],cache,inv);snap=cache/inv[0]['snapshot'];rep['modelAcquisition']={'cacheOnly':True,'inventory':inv,'files':S.model_files(snap,generic)}
  with tempfile.TemporaryDirectory(prefix='heard-anchor-readonly-',dir=os.environ.get('RUNNER_TEMP')) as td:
   path=Path(td)/'source.mp3';receipt=S.metadata.fetch(src['url'],path,limit=B.MAX_SOURCE_BYTES);B.require(receipt['sha256']==src['sha256'],'تغير صوت المصدر');rep['download']=receipt
   M=importlib.import_module('ctc_heard_map');rep['heardToolSha256']=S.sha_file(M.__file__);original=M.global_anchors;captured=[]
   def capture(heard,times,canonical,frame_ms=20):
    result=original(heard,times,canonical,frame_ms)
    captured.append({'heardSkeleton':heard,'heardCharacterTimesMs':list(times),'canonicalSkeletons':canonical,'opcodes':M._opcodes(heard,''.join(canonical)),'frameMs':frame_ms,'unalteredAnchors':result})
    return result
   try:
    M.global_anchors=capture
    with P.offline_model_loads(hub,[generic],{(generic['id'],generic['revision']):snap}):
     raw,report=M.run(path,69,'hafs',probe=True)
   finally:M.global_anchors=original
   B.require(len(captured)==1 and S.sha_file(path)==src['sha256'],'قياس غير كامل أو تغير المصدر')
   rep.update(measurementComplete=True,rawProbe=raw,anchorInputs=captured[0],textReport=report)
 except Exception as e:rep['errors'].append({'type':type(e).__name__,'message':str(e)})
 S.emit(rep,'HEARD_ANCHOR_PROVENANCE_REPORT')
 return 0 if rep['measurementComplete'] else 1
if __name__=='__main__':raise SystemExit(main())
