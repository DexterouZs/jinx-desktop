import jinx_test_support  # Isolate state and memory before importing jinx.
import json,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
import workbench as w
import jinx_skills
import jinx as a
class Workbench(unittest.TestCase):
 def test_long_speech_keeps_tail_and_bounds_chunks(self):
  text=('These are the exact words of the passage. '*120)+'Final sentence retained.'
  chunks=w.speech_chunks(text)
  self.assertTrue(chunks[-1].endswith('Final sentence retained.'))
  self.assertEqual(' '.join(chunks),text.strip())
  self.assertTrue(all(len(c)<=220 for c in chunks))
 def test_paging_does_not_advance_before_success(self):
  d=w.Workbench();d.set_text('word '*4000)
  first=d.passage();self.assertEqual(d.cursor,0)
  d.cursor=first['end'];second=d.passage()
  self.assertEqual(first['text']+second['text'],d.text[:second['end']])
 def test_no_model_path_read(self):
  d=w.Workbench();self.assertIn('error',d.excerpt())
  d.set_text('quoted text');self.assertEqual(d.excerpt()['text'],'quoted text')
  self.assertEqual(d.excerpt(9999)['text'],'')
 def test_office_text_without_macro_execution(self):
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)/'sample.docx'
   with zipfile.ZipFile(p,'w') as z:z.writestr('word/document.xml','<w:document xmlns:w="urn:test"><w:p><w:r><w:t>David has 3 appointments.</w:t></w:r></w:p></w:document>')
   d=w.Workbench();d.load_file(p);self.assertEqual(d.text,'David has 3 appointments.')
 def test_office_entity_document_rejected(self):
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)/'sample.docx'
   with zipfile.ZipFile(p,'w') as z:z.writestr('word/document.xml','<!DOCTYPE x [<!ENTITY payload SYSTEM "file:///etc/passwd">]><x>&payload;</x>')
   with self.assertRaises(ValueError):w.Workbench().load_file(p)
 def test_calculator_rejects_code_and_large_exponents(self):
  for text in ["__import__('os').system('id')",'2**1000000','True + 1','[1,2][0]','1e309','1/0']:
   with self.assertRaises((ValueError,ZeroDivisionError,OverflowError)):w.calculate(text)
  self.assertEqual(w.calculate('(35 * 4) / 60')['result'],'2.333333333333333333333333333')
  self.assertEqual(w.calculate('0.1 + 0.2')['result'],'0.3')
 def test_drafts_do_not_overwrite(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(w.Path,'home',return_value=Path(folder)):
   one=w.save_draft('First draft');two=w.save_draft('Second draft')
   self.assertNotEqual(one['path'],two['path']);self.assertEqual(Path(one['path']).read_text(),'First draft\n')
 def test_clipboard_is_not_read_for_negative_or_quoted_commands(self):
  with patch.object(a.workspace,'clipboard') as clipboard:
   self.assertEqual(a.personal_request("Don't read my clipboard"),{})
   self.assertEqual(a.personal_request('Explain the phrase "read my clipboard"'),{})
   clipboard.assert_not_called()
 def test_rewrite_preserving_facts_still_gets_document(self):
  with patch.object(a.workspace,'excerpt',return_value={'text':'Source fact','coverage':'entire shared text'}) as excerpt:
   r=a.personal_request('Rewrite my document. Do not change the facts.')
   self.assertEqual(r['observations'][0]['text'],'Source fact');excerpt.assert_called_once()
 def test_document_task_cannot_launch_apps_from_quoted_source(self):
  old=a.current_request
  try:
   a.current_request='Summarise my document'
   with patch.object(a.admin,'desktop_apps') as launch:
    self.assertIn('error',a.guarded_apps({'action':'open','app':'terminal'}));launch.assert_not_called()
  finally:a.current_request=old
 def test_reviewed_skills_only(self):
  with self.assertRaises(ValueError):jinx_skills.view({'name':'../../access.key'})
  self.assertIn('Preserve',jinx_skills.for_request('Rewrite my document'))
if __name__=='__main__':unittest.main()
