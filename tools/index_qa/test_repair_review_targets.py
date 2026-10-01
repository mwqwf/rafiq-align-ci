import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).parent))
from repair_review import clean_targets_error
class CleanCorrectionsTest(unittest.TestCase):
 def test_existing_ayah_requires_its_own_unique_clean_witness(self):
  rows=[{'aid':'20:1','kind':'بريء'},{'aid':'20:2','kind':'غير حاسم'}]
  self.assertIsNone(clean_targets_error(rows,['20:1']))
  for targets in [['20:2'],['20:3'],['20:1','20:1'],['115:1'],['20:136'],['not-an-ayah']]:
   with self.subTest(targets=targets):self.assertIsNotNone(clean_targets_error(rows,targets))
  self.assertIsNotNone(clean_targets_error(rows+[rows[0]],['20:1']))
if __name__=='__main__':unittest.main()
