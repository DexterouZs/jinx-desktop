import unittest,tempfile
from pathlib import Path
from unittest.mock import patch
import obsidian_tools as o
class TasksTests(unittest.TestCase):
 def test_only_real_unfinished_checkboxes_and_due_filter(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'Tasks.md').write_text('- [ ] Today 📅 2030-01-01\n- [x] Done\n- [ ] Future 📅 2030-02-01\n```markdown\n- [ ] Example\n```\n- [ ] Undated\n')
   with patch.object(o,'VAULT',p):r=o.read({'date':'2030-01-01','days':1})
   self.assertEqual([t['text'] for t in r['tasks']],['Today 📅 2030-01-01','Undated'])
 def test_external_symlink_not_read(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);v=root/'vault';v.mkdir();(root/'secret.md').write_text('- [ ] Outside');(v/'link.md').symlink_to(root/'secret.md')
   with patch.object(o,'VAULT',v):self.assertEqual(o.read({})['tasks'],[])
if __name__=='__main__':unittest.main()
