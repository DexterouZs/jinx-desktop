import jinx_test_support  # Isolate state and memory before importing jinx.
import copy,threading,unittest,tempfile,json,hashlib,wave
from pathlib import Path
from unittest.mock import Mock,patch
import jinx as a
import quick_speech
from voices import Voices
from jinx_voice import VoiceCancelled

class Recovery(unittest.TestCase):
 def setUp(self):self.saved=copy.deepcopy(a.status);self.data=copy.deepcopy(a.data)
 def tearDown(self):a.status.clear();a.status.update(self.saved);a.data.clear();a.data.update(self.data)
 def test_greeting_routes_without_model_and_not_quoted_commands(self):
  for text in ['Hi Jinx','Hi, Jinx!','Hello Jinx.','Hey Jinks.','Hi Jynxer.','Good morning Jinx']:
   self.assertEqual(a.personal_request(text),{'reply':quick_speech.GREETING})
  for text in ['Edgings.','Hi James.','Hi Jinx, open Discord','Explain the phrase "Hi Jinx"','Write Alex on WhatsApp: Hi Jinx']:
   self.assertFalse(quick_speech.greeting(text))
 def test_stopping_voice_does_not_cancel_idle_agent(self):
  a.status.update(busy=True,voice_epoch=0)
  with patch.object(a,'agent') as idle,patch.object(a,'active_agent',None):
   a.stop_turn();idle.interrupt.assert_not_called()
 def test_new_turn_clears_previous_interrupt(self):
  a.status['voice_epoch']=10;current=Mock()
  current.run_conversation.return_value={'final_response':'A real answer.'}
  with patch.object(a,'get_agent',return_value=current):
   r=a.run_agent_turn('Request','System',10,lambda _:None)
  current.clear_interrupt.assert_called_once();self.assertEqual(r['final_response'],'A real answer.');self.assertIsNone(a.active_agent)
 def test_stop_during_model_initialisation_is_not_cleared(self):
  a.status['voice_epoch']=2;current=Mock()
  def get():a.stop_turn();return current
  with patch.object(a,'get_agent',side_effect=get):r=a.run_agent_turn('Request','System',2,lambda _:None)
  self.assertTrue(r['interrupted']);current.clear_interrupt.assert_not_called();current.run_conversation.assert_not_called()
 def test_active_request_stops_and_next_turn_can_run(self):
  class Agent:
   cancelled=True;stops=0
   def clear_interrupt(self):self.cancelled=False
   def interrupt(self,**kw):self.cancelled=True;self.stops+=1
   def run_conversation(self,*args,**kw):
    if self.stops==0:a.stop_turn();return {'interrupted':self.cancelled}
    return {'final_response':'Recovered' if not self.cancelled else ''}
  current=Agent();a.status.update(busy=True,voice_epoch=3)
  with patch.object(a,'get_agent',return_value=current):
   self.assertTrue(a.run_agent_turn('One','System',3,lambda _:None)['interrupted'])
   self.assertEqual(a.run_agent_turn('Two','System',a.status['voice_epoch'],lambda _:None)['final_response'],'Recovered')
  self.assertEqual(current.stops,1);self.assertIsNone(a.active_agent)

class FixedGreeting(unittest.TestCase):
 def make(self,d):
  root=Path(d);folder=root/'voice-jinx/quick-replies';folder.mkdir(parents=True)
  hashes={}
  for name in ['reference-short.wav','runtime.json']:
   (root/'voice-jinx'/name).write_bytes(b'fixture');hashes[name]=hashlib.sha256(b'fixture').hexdigest()
  path=folder/'greeting.wav'
  with wave.open(str(path),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(bytes(4800))
  payload=path.read_bytes();(folder/'manifest.json').write_text(json.dumps({'source_sha256':hashes,'replies':[{'text':quick_speech.GREETING,'voice':'jinx_local','speed':.9,'file':path.name,'sha256':hashlib.sha256(payload).hexdigest()}]}))
  return root,path,payload
 def test_fixed_greeting_needs_no_model_or_voice_worker(self):
  with tempfile.TemporaryDirectory() as d:
   root,path,payload=self.make(d)
   with patch.object(quick_speech,'ROOT',root):
    v=Voices();v.jinx=Mock();out=root/'out.wav';result=v.synthesise(quick_speech.GREETING,out,'jinx_local',.9)
    self.assertTrue(result['fixed_reply']);self.assertEqual(out.read_bytes(),payload);v.jinx.synthesise.assert_not_called()
    with self.assertRaises(VoiceCancelled):v.synthesise(quick_speech.GREETING,out,'jinx_local',.9,cancelled=lambda:True)
 def test_cache_cannot_substitute_voice_pace_text_or_modified_audio(self):
  with tempfile.TemporaryDirectory() as d:
   root,path,payload=self.make(d)
   with patch.object(quick_speech,'ROOT',root):
    self.assertIsNone(quick_speech.load(quick_speech.GREETING,'jinx_local',1))
    self.assertIsNone(quick_speech.load(quick_speech.GREETING,'kokoro_emma',.9))
    self.assertIsNone(quick_speech.load('Your message is sent.','jinx_local',.9))
    path.write_bytes(payload+b'changed');self.assertIsNone(quick_speech.load(quick_speech.GREETING,'jinx_local',.9))

if __name__=='__main__':unittest.main()
