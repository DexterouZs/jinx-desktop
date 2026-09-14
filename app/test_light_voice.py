import jinx_test_support  # Isolate state and memory before importing jinx.
import tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
import home_tools as h
import jinx as j
from voices import Voices

TEXT='Alright, can you make the bedroom light to a softer tone and not so bright anymore like 5%?'

class LightVoice(unittest.TestCase):
 def home(self):
  home=Mock();entity={'entity_id':'light.bedroom_light','domain':'light','name':'Bedroom Light'}
  home.resolve.return_value={'entity':entity}
  home.execute.return_value={'verified':True,'entity':entity}
  home.call.return_value={'verified':True,'entity':entity}
  return home
 def test_combined_request_controls_and_verifies_both_values(self):
  home=self.home();r=h.light_tool({'name':'bedroom light','colour':'warm white','brightness':5},TEXT,home)
  self.assertIn('done',r)
  home.execute.assert_called_once_with('light.bedroom_light','set_colour','warm white')
  home.call.assert_called_once_with('light.bedroom_light',True,5)
 def test_latest_plural_request_controls_only_configured_group(self):
  home=self.home()
  rows=[{'entity_id':eid,'domain':'light','name':name,'state':'on','attributes':{'supported_color_modes':['hs']}} for eid,name in [('light.one','Bedroom Main Light'),('light.two','Bedroom Light')]]
  home.states.return_value=rows
  home.resolve.side_effect=lambda name,domains:{'entity':next(r for r in rows if r['entity_id']==name)}
  with patch.object(h,'catalog',return_value={'groups':['bedroom lights'],'aliases':{'bedroom lights':['light.one','light.two']}}):
   result=h.light_tool({'name':'bedroom lights','colour':'warm white','brightness':5},'I want you to give my bedroom lights a softer light and put it down to 5%.',home)
  self.assertIn('done',result)
  self.assertEqual(home.call.call_count,2);self.assertEqual(home.execute.call_count,2)
 def test_model_cannot_change_requested_percentage(self):
  home=self.home();r=h.light_tool({'name':'bedroom light','colour':'warm white','brightness':100},TEXT,home)
  self.assertIn('error',r);home.execute.assert_not_called();home.call.assert_not_called()
 def test_model_cannot_invent_colour(self):
  home=self.home();r=h.light_tool({'name':'bedroom light','colour':'red','brightness':5},TEXT,home)
  self.assertIn('error',r);home.execute.assert_not_called();home.call.assert_not_called()
 def test_readonly_request_never_writes(self):
  home=self.home()
  for text in ['Check the bedroom light at 5%','Do not set the bedroom light to 5%','If I set the bedroom light to 5% what happens?']:
   self.assertIn('error',h.light_tool({'name':'bedroom light','brightness':5},text,home))
  home.call.assert_not_called()
 def test_device_must_match_current_user_request(self):
  home=self.home();r=h.light_tool({'name':'bedroom light','brightness':5},'Set the kitchen light to 5%',home)
  self.assertIn('error',r);home.call.assert_not_called()
 def test_source_context_cannot_authorise_light_changes(self):
  with patch.dict(j.status,{'external_context':True}),patch.object(h,'light_tool') as tool:
   self.assertIn('error',j.guarded_light({'name':'bedroom light','brightness':5}));tool.assert_not_called()
 def test_unconfirmed_first_action_does_not_claim_combined_success(self):
  home=self.home();home.execute.return_value={'verified':False}
  r=h.light_tool({'name':'bedroom light','colour':'warm white','brightness':5},TEXT,home)
  self.assertIn('unconfirmed',r);home.call.assert_not_called()
 def test_voice_never_changes_for_short_confirmations(self):
  for voice in ['jinx_local','kokoro_emma','kokoro_isabella','piper_alba']:
   for text in ['Done.','Bedroom Light on','Bedroom Light set to 5%','A longer ordinary reply.']:
    self.assertEqual(j.pick_voice(text,voice),voice)
 def test_clone_failure_does_not_speak_alba(self):
  voice=Voices()
  with tempfile.TemporaryDirectory() as folder,patch.object(voice.jinx,'synthesise',side_effect=RuntimeError('test')),patch('quick_speech.load',return_value=None):
   with self.assertRaisesRegex(RuntimeError,'instead of switching voices'):
    voice.synthesise('A test sentence.',Path(folder)/'voice.wav','jinx_local')
   self.assertIsNone(voice.piper)

if __name__=='__main__':unittest.main()
