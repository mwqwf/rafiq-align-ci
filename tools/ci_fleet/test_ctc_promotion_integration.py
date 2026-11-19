"""Offline integration: full driver body -> full promote.main AST -> receipt -> certify decision.
All cloud, filesystem credentials, subprocess and promotion guards are explicit test doubles.
This validates orchestration, not the internals of quality gates or real S3 behavior.
"""
import argparse,ast,builtins,contextlib,datetime,gzip,hashlib,io,json,pathlib,re,sys,time,types,unittest
from unittest.mock import patch
P=pathlib.Path(__file__).resolve().parents[2];ROOT=P
class Integration(unittest.TestCase):
 def simulate(self,modes):
  events=[];bodies={};reports={};targets={};states={};keys=[]
  for i,mode in enumerate(modes):
   rid='reader'+str(i);body=gzip.compress(json.dumps({'engineVersion':'ctc-seg-1','entries':[{'ayahId':'1:1'}]}).encode(),mtime=0);sha=hashlib.sha256(body).hexdigest();key=f'timings-staging/hafs/{rid}.{sha[:8]}.jz';keys.append(key);bodies[key]=body;target=f'timings/hafs/{rid}.jz';targets[key]=target
   reports[key]={'key':key,'sha256':sha,'riwaya':'hafs','reciterId':rid,'ts':2000000000,'verdict':'مقبول'}
   for salt in ['k1','k2','k3','k4']:states['state/'+key.replace('/','_')+'.audio-'+salt+'.json']=json.dumps({'verdict':'مقبول'}).encode()
   states['state/'+key.replace('/','_')+'.openers.json']=b'{}'
  class Client:
   def get_paginator(self,name):
    class Pag:
     def paginate(self,**kw):
      prefix=kw['Prefix'];items=states if prefix.startswith('state/') else keys
      return [{'Contents':[{'Key':k,'LastModified':datetime.datetime(2026,11,17,tzinfo=datetime.timezone.utc)} for k in items]}]
    return Pag()
   def get_object(self,**kw):
    k=kw['Key'];return {'Body':io.BytesIO(b'' if k=='timings/frozen.txt' else states[k] if k in states else bodies[k])}
   def copy_object(self,**kw):events.append(('copy',kw['Key']));bodies[kw['Key']]=bodies[kw['CopySource']['Key']]
   def head_object(self,**kw):return {'ContentLength':len(bodies.get(kw['Key'],b'')),'LastModified':datetime.datetime(2020,1,1,tzinfo=datetime.timezone.utc),'ETag':'test'}
   def put_object(self,**kw):raise AssertionError('unexpected driver write')
  cl=Client();main_ast=next(n for n in ast.parse((ROOT/'tools/index_qa/promote.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='main')
  def promote(key):
   mode=modes[keys.index(key)];report=reports[key];target=targets[key];body=bodies[key]
   def freeze(*args):
    events.append(('freeze',target))
    if mode=='freezefail':raise RuntimeError('simulated freeze failure')
    return 'test freeze'
   def logged(done):
    events.append(('log',target))
    if mode=='logfail':raise RuntimeError('simulated log failure')
   def pub(k):return (0 if mode=='manifestfail' else 100) if k=='timings/manifest.json' else (0 if mode=='sizefail' else len(body))
   ns=dict(argparse=argparse,json=json,gzip=gzip,Path=pathlib.Path,time=time,re=re,ROOT=ROOT,LOG=ROOT/'log.md',REPORTS_CACHE=[('test',report)],READ_FAILED=1 if mode=='readfail' else 0,
    s3=lambda:(cl,'fake'),load_frozen=lambda *a:({target:'different'} if mode=='frozen' else {},'',None),held=lambda:{},load_drop_approvals=lambda:{},ci_map=lambda x:{},openers_map=lambda x:{},pooled_map_of=lambda x:{},sampled_candidates=lambda x:x,
    gate=lambda *a:(target,'frozen' if mode=='refused' else None),has_audio_sample=lambda x:False,object_sha=lambda *a:('changed' if mode=='changed' else report['sha256'],len(body),body),truncation=lambda *a:([],'ok'),_op_mixes_engines=lambda x:False,
    census_gate=lambda *a:'census reject' if mode=='census' else None,heard_gate_check=lambda *a:'heard reject' if mode=='heard' else None,index_gate=lambda *a,**k:None,catalog_gate=lambda *a:None,catalog=lambda *a:{},coded_drop_gate=lambda *a:None,shrink_refusal=lambda *a,**k:None,
    public_size=pub,write_manifest=lambda *a:('timings/manifest.json',100,1,1,True),approved_drop=lambda *a:False,freeze=freeze,log_promotion=logged)
   exec(compile(ast.Module(body=[main_ast],type_ignores=[]),'promote-main','exec'),ns)
   stream=io.StringIO();rc=0
   with patch.object(sys,'argv',['promote.py','--only',key]+([] if mode=='dryrun' else ['--yes'])),contextlib.redirect_stdout(stream):
    try:ns['main']()
    except (RuntimeError,SystemExit) as e:rc=1;print(e)
   return types.SimpleNamespace(returncode=rc,stdout=stream.getvalue(),stderr='')
  def run(args,**kw):
   if args[0]=='gh':return types.SimpleNamespace(returncode=0,stdout='[]')
   if args[1]=='tools/index_qa/promote.py':return promote(args[3])
   if args[1]=='tools/index_qa/certify_catalog.py':events.append(('certify',));return types.SimpleNamespace(returncode=0)
   raise AssertionError(args)
  modules={}
  for name,attrs in {'boto3':{'client':lambda *a,**k:cl},'promote':{'held':lambda:{}},'qa_dispatch_guard':{'has_current_manual_sample':lambda *a:False,'manual_qa_reason':lambda *a:None},'gate_launch_guard':{'launch_skip_reason':lambda *a:None}}.items():
   mod=types.ModuleType(name);mod.__dict__.update(attrs);modules[name]=mod
  oldopen=builtins.open
  def safeopen(file,*a,**k):
   if str(file).endswith('secure/r2_credentials.json'):return io.StringIO(json.dumps(dict(endpoint='fake',accessKeyId='fake',secretAccessKey='fake',bucket='fake')))
   return oldopen(file,*a,**k)
  output=io.StringIO();oldpath=list(sys.path)
  try:
   with patch.dict(sys.modules,modules),patch('subprocess.run',run),patch('builtins.open',safeopen),contextlib.redirect_stdout(output):
    exec(compile((ROOT/'tools/ci_fleet/ctc_driver.py').read_text(),'driver','exec'),{'__file__':str(ROOT/'tools/ci_fleet/ctc_driver.py'),'__name__':'__main__'})
  finally:sys.path[:]=oldpath
  return events,output.getvalue()
 def test_two_refusals(self):
  ev,out=self.simulate(['refused','refused']);self.assertEqual(ev,[]);self.assertIn('رُقّي في هذه الدورة: 0',out)
 def test_success(self):
  ev,out=self.simulate(['success']);self.assertEqual([x[0] for x in ev],['copy','freeze','log','certify']);self.assertIn('رُقّي في هذه الدورة: 1',out)
 def test_manifest_mismatch(self):
  ev,out=self.simulate(['manifestfail']);self.assertEqual([x[0] for x in ev],['copy','freeze','log']);self.assertIn('رُقّي في هذه الدورة: 0',out)
 def test_size_mismatch(self):
  ev,out=self.simulate(['sizefail']);self.assertEqual([x[0] for x in ev],['copy']);self.assertIn('رُقّي في هذه الدورة: 0',out)
 def test_freeze_failure(self):
  ev,out=self.simulate(['freezefail']);self.assertEqual([x[0] for x in ev],['copy','freeze']);self.assertIn('رُقّي في هذه الدورة: 0',out)
 def test_log_failure(self):
  ev,out=self.simulate(['logfail']);self.assertNotIn(('certify',),ev);self.assertIn('رُقّي في هذه الدورة: 0',out)
 def test_additional_guards(self):
  for mode in ['readfail','frozen','changed','census','heard','dryrun']:
   with self.subTest(mode=mode):
    ev,out=self.simulate([mode]);self.assertEqual(ev,[]);self.assertIn('رُقّي في هذه الدورة: 0',out)
 def test_mixed(self):
  ev,out=self.simulate(['refused','success','manifestfail']);self.assertEqual(ev.count(('certify',)),1);self.assertIn('رُقّي في هذه الدورة: 1',out)
if __name__=='__main__':unittest.main(verbosity=2)
