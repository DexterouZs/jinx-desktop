import jinx_test_support  # Isolate state and memory before importing jinx.
import json,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import screen_view as v
import jinx as a

class ScreenView(unittest.TestCase):
 def test_only_explicit_screen_requests(self):
  for text in ['Look at my screen','Can you see my screen?','What do you see on my screen?','Please explain this page']:
   self.assertEqual(v.intent(text),'look',text)
  for text in ['Read this page aloud','Read the text on my screen']:
   self.assertEqual(v.intent(text),'read',text)
  for text in ["Don't read my screen",'Explain the phrase "look at my screen"','How can you see my screen?','Read my clipboard','Open Firefox','Explain this page without taking a screenshot','What does look at my screen mean?']:
   self.assertIsNone(v.intent(text),text)
 def test_disabled_screen_never_captures(self):
  with patch.dict(a.data,{'screen_enabled':False}),patch.object(v,'capture') as capture,self.assertRaises(ValueError):
   a.screen_request('Look at my screen',a.status['voice_epoch'],lambda x:None)
  capture.assert_not_called()
 def test_glow_requires_matching_render_ack_and_expires(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(v,'RUNTIME',Path(folder)):
   attention=v.Attention()
   try:
    identifier=attention.begin('test')
    with patch.object(v.time,'sleep'),self.assertRaises(ValueError):attention.ready(lambda:False)
    (Path(folder)/'ready.json').write_text(json.dumps({'id':identifier}))
    attention.ready(lambda:False)
    state=json.loads((Path(folder)/'state.json').read_text());self.assertTrue(state['active']);self.assertLess(state['expires']-time.time(),3.1)
   finally:attention.clear()
   self.assertFalse(json.loads((Path(folder)/'state.json').read_text())['active'])
 def test_locked_desktop_fails_before_spectacle(self):
  with patch.object(v,'run',return_value='true') as run,self.assertRaises(ValueError):v.capture(lambda:False)
  self.assertEqual(run.call_count,1)
 def test_capture_runtime_image_is_removed(self):
  paths=[]
  def run(args,*rest):
   if args[0]=='qdbus6':return 'false'
   if args[0]=='spectacle':
    p=Path(args[-1]);paths.append(p);v.Image.new('RGB',(640,400),'white').save(p);return ''
   return 'Sample text'
  with tempfile.TemporaryDirectory() as folder,patch.object(v,'RUNTIME',Path(folder)/'attention'),patch.object(v,'run',side_effect=run):
   shot=v.capture(lambda:False)
   self.assertEqual(shot['text'],'Sample text');self.assertTrue(shot['image']);self.assertFalse(paths[0].exists())
 def test_cancelled_command_terminates_promptly(self):
  started=time.monotonic()
  with self.assertRaises(v.Cancelled):v.run(['/usr/bin/sleep','30'],lambda:True)
  self.assertLess(time.monotonic()-started,1)
 def test_stop_clears_indicator(self):
  with patch.object(a.attention,'clear') as clear: a.stop_turn()
  clear.assert_called_once()
if __name__=='__main__':unittest.main()
