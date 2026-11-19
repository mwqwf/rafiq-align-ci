import ast,json,pathlib,unittest
P=pathlib.Path(__file__).resolve().parents[2]
src=(P/'tools/ci_fleet/ctc_driver.py').read_text();tree=ast.parse(src)
nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='verified_promotion']
ns={'json':json};exec(compile(ast.Module(body=nodes,type_ignores=[]),'driver-function','exec'),ns)
verify=ns['verified_promotion']; key='timings-staging/hafs/qurashi.311a8d1c.jz';sha='1'*64
row={'src':key,'dst':'timings/hafs/qurashi.jz','sha256':sha}
def receipt(rows):return 'PROMOTION_RESULT_V1='+json.dumps({'verified':rows})
class ReceiptTest(unittest.TestCase):
 def test_success(self):self.assertTrue(verify(0,receipt([row]),key,sha))
 def test_zero_exit_noop(self):self.assertFalse(verify(0,'لا ترقية — ولا شيء كُتب.',key,sha))
 def test_empty(self):self.assertFalse(verify(0,receipt([]),key,sha))
 def test_nonzero(self):self.assertFalse(verify(1,receipt([row]),key,sha))
 def test_wrong_sha(self):self.assertFalse(verify(0,receipt([dict(row,sha256='2'*64)]),key,sha))
 def test_wrong_target(self):self.assertFalse(verify(0,receipt([dict(row,dst='timings/hafs/swlim.jz')]),key,sha))
 def test_wrong_source(self):self.assertFalse(verify(0,receipt([dict(row,src='other')]),key,sha))
 def test_duplicate(self):self.assertFalse(verify(0,receipt([row])+'\n'+receipt([row]),key,sha))
 def test_malformed(self):
  for x in ['{}','null','[]','bad','{"verified":null}']:
   self.assertFalse(verify(0,'PROMOTION_RESULT_V1='+x,key,sha))
 def test_refusal_log_no_false_receipt(self):self.assertFalse(verify(0,'لا ترقية — ولا شيء كُتب.\nلا ترقية — ولا شيء كُتب.\nرُقّي في هذه الدورة: 2',key,sha))
 def test_driver_uses_verified_result(self):
  self.assertIn('if promote_verified(k, actual_sha):\n                promoted += 1',src)
  self.assertNotIn('if sh(sys.executable, "tools/index_qa/promote.py"',src)
 def test_emitter_follows_completion_and_size_guard(self):
  s=(P/'tools/index_qa/promote.py').read_text();ast.parse(s)
  self.assertIn('if mpub == mlen:\n            verified_promotions.append',s)
  self.assertLess(s.index('line = freeze('),s.index('verified_promotions.append'))
  self.assertLess(s.index('log_promotion(done)'),s.index('print("PROMOTION_RESULT_V1="'))
if __name__=='__main__':unittest.main(verbosity=2)
