import tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from messaging_browser import WhatsAppBrowser

class BrowserBoundary(unittest.TestCase):
 def setUp(self):
  self.b=WhatsAppBrowser(Path('/unused'))
  self.b.driver=Mock();self.b.driver.window_handles=['one'];self.b.driver.current_url='https://web.whatsapp.com/'
  self.editor=Mock();self.editor.text='Hello';self.header=Mock();label=Mock();label.get_attribute.return_value='Alex';self.header.find_elements.return_value=[label]
  self.b.staged={'id':'review','editor':self.editor,'header':self.header,'identity':'Alex','text':'Hello'}
  self.draft={'id':'review','phone':'+12025550101','recipient':'Alex','text':'Hello'}
 def test_changed_tab_or_origin_never_reaches_send(self):
  for url in ['https://example.org/','https://web.whatsapp.com.evil.example/','http://web.whatsapp.com/']:
   self.b.driver.current_url=url
   with self.assertRaises(ValueError):self.b.send(self.draft)
  self.b.driver.find_elements.assert_not_called()
 def test_phone_name_alone_is_insufficient(self):
  self.b.driver.find_elements.return_value=[]
  with patch.object(self.b,'_header',return_value=self.header),self.assertRaises(ValueError):self.b._verify_number(self.draft['phone'])
 def test_different_phone_id_refuses_recipient(self):
  element=Mock();element.get_attribute.return_value='false_491111111111@c.us_sample'
  self.b.driver.find_elements.return_value=[element]
  with self.assertRaises(ValueError):self.b._verify_number(self.draft['phone'])
 def test_modified_composer_cannot_send(self):
  self.editor.text='Edited after approval'
  with patch.object(self.b,'_editor',return_value=self.editor),patch.object(self.b,'_header',return_value=self.header),patch.object(self.b,'_verify_number',return_value=True),self.assertRaises(ValueError):self.b.send(self.draft)
  self.b.driver.find_elements.assert_not_called()
 def test_send_exception_consumes_ticket_without_retry(self):
  button=Mock();button.is_displayed.return_value=True;button.click_reviewed.side_effect=RuntimeError('Transport disconnected')
  self.b.driver.find_elements.side_effect=[[],[button]]
  with patch.object(self.b,'_editor',return_value=self.editor),patch.object(self.b,'_header',return_value=self.header),patch.object(self.b,'_verify_number',return_value=True):
   self.assertEqual(self.b.send(self.draft)['state'],'uncertain')
   with self.assertRaises(ValueError):self.b.send(self.draft)
  button.click_reviewed.assert_called_once()

if __name__=='__main__':unittest.main()

class ComposerOwnership(unittest.TestCase):
 def test_restart_preserves_ownership_but_not_manual_edits(self):
  import json,time
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory)
   b=WhatsAppBrowser(root/'profile')
   (root/'composer-owned.json').write_text(json.dumps({'phone':'+12025550101','text':'Original','at':time.time()}))
   editor=Mock();editor.text='Original'
   self.assertTrue(b.owns_composer(editor,'+12025550101',None))
   self.assertFalse(b.owns_composer(editor,'+12025550100',None))
   editor.text='My manual edit'
   self.assertFalse(b.owns_composer(editor,'+12025550101',None))
 def test_missing_ownership_never_adopts_arbitrary_draft(self):
  with tempfile.TemporaryDirectory() as directory:
   b=WhatsAppBrowser(Path(directory)/'profile');editor=Mock();editor.text='Unsent'
   self.assertFalse(b.owns_composer(editor,'+12025550101',None))
