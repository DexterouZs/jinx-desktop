import jinx_test_support
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
import browser_actions as browser
import email_drafts as email
import jinx as j
import routing

class EverydayActions(unittest.TestCase):
 def setUp(self):
  p=patch.object(browser,'raise_browser');p.start();self.addCleanup(p.stop)
 def test_actual_nexus_failures_and_polite_variants(self):
  for text in ('Hi Jinx, can you open for me the Nexus Mod website?',
               'Open a website for me, the NexusMort website.',
               'Please open me the nexus mmod website',
               'Take me to Nexus Mods','Open nexusmods.com'):
   self.assertEqual(browser.parse(text)['url'].rstrip('/'),'https://www.nexusmods.com' if 'nexusmods.com' not in text else 'https://nexusmods.com',text)
 def test_websites_are_not_apps_or_read_operations(self):
  with patch.object(browser.subprocess,'run',return_value=Mock(returncode=0)) as run,patch.object(j.launch_tools,'requested') as app,patch.object(j,'understood_task') as planner,patch.object(j,'read_web') as read,patch.dict(j.data,speak=False,episodic_memory=False,web_enabled=True):
   j.chat('Hi Jinx, can you open for me the Nexus Mod website?',False)
   self.assertEqual(run.call_args.args[0],['/usr/bin/xdg-open','https://www.nexusmods.com/'])
   app.assert_not_called();planner.assert_not_called();read.assert_not_called()
   self.assertEqual(j.status['messages'][-1]['content'],'Opening Nexus Mods.')
 def test_youtube_shows_real_results_and_encodes_query(self):
  for text in ('Show me videos about Blender lighting on YouTube','Find YouTube videos about Blender lighting','Search YouTube for Blender lighting','Show me a video about Blender lighting'):
   p=browser.parse(text);self.assertEqual(p['url'],'https://www.youtube.com/results?search_query=Blender+lighting')
  self.assertIsNone(browser.parse('Play music on Spotify'))
 def test_unknown_site_searches_and_never_invents_domain(self):
  p=browser.parse('Open the Flibberty website');self.assertEqual(p['kind'],'site_search');self.assertIn('Flibberty+official+website',p['url'])
 def test_no_side_effect_for_quotes_negation_or_disabled_web(self):
  for text in ('Do not open Nexus Mods','She said open Nexus Mods','"Open Nexus Mods"','Open Nexus Mods and then send a message'):
   self.assertIsNone(browser.parse(text),text)
  with patch.object(browser.subprocess,'run') as run:
   self.assertIn('switched off',browser.requested('Open Nexus Mods',False)['reply']);run.assert_not_called()
 def test_navigation_validates_schemes_and_reports_failure(self):
  for value in ('javascript:alert(1)','file:///etc/passwd','https://name:password@example.org','https://example.org/\nrun'):
   with self.assertRaises(ValueError):browser.url(value)
  with patch.object(browser.subprocess,'run',return_value=Mock(returncode=1)):
   self.assertEqual(browser.requested('Open Nexus Mods')['status'],'failed')
 def test_exact_email_dictation_saves_real_draft_preserving_words(self):
  with tempfile.TemporaryDirectory() as root,patch.object(email,'DRAFTS',Path(root)),patch.dict(j.data,speak=False,episodic_memory=False),patch.object(j,'run_tiered_turn') as model:
   j.chat('Write an email to Alex saying I cannot come at 16:00. Can we do 17:00?',False)
   rows=list(Path(root).glob('*.txt'));self.assertEqual(len(rows),1)
   draft=rows[0].read_text();self.assertIn('To: Alex',draft);self.assertIn('I cannot come at 16:00. Can we do 17:00?',draft)
   self.assertIn('Nothing has been sent',j.status['messages'][-1]['content']);model.assert_not_called()
   self.assertNotIn('To:',next(Path(root).glob('*.eml')).read_text())
 def test_email_headers_cannot_inject_or_invent_recipient(self):
  with tempfile.TemporaryDirectory() as root,patch.object(email,'DRAFTS',Path(root)):
   with self.assertRaises(ValueError):email.save({'to':'a@example.org\nBcc: b@example.org','body':'Hi'})
   with patch.object(j,'current_request','Write an email to Alex saying Hi'),patch.dict(j.status,external_context=False):
    result=j.save_email({'to':'invented@example.org','subject':'Hello','body':'Changed'})
   self.assertIn('To: Alex',result['draft']);self.assertTrue(result['draft'].endswith('Hi\n'))
 def test_creative_email_hands_off_with_concrete_save_instruction(self):
  p=email.intent('Write a polite email to my landlord asking to repair the heater.')
  self.assertEqual(p['to'],'my landlord');self.assertFalse(p['body'])
  with patch.object(j,'current_request','Write a polite email to my landlord asking to repair the heater.'):
   result=j.email_request(j.current_request)
  self.assertIn('jinx_email_draft',json.dumps(result))
 def test_small_model_draft_uses_supplied_recipient_and_saves(self):
  with tempfile.TemporaryDirectory() as root,patch.object(email,'DRAFTS',Path(root)),patch.dict(j.data,ai_mode='local_fast',speak=False,episodic_memory=False),patch.object(email,'compose',return_value={'subject':'Meeting','body':'Hi Alex, can we meet on Wednesday at 16:00?'}),patch.object(j,'run_tiered_turn') as deep:
   j.chat('Write a short polite email to Alex asking to meet on Wednesday at 16:00.',False)
   self.assertEqual(len(list(Path(root).glob('*.eml'))),1);deep.assert_not_called()
   self.assertIn('To: Alex',j.status['messages'][-1]['content'])
 def test_source_context_cannot_open_browser_or_write_email(self):
  with patch.dict(j.status,external_context=True),patch.object(j,'current_request','Open Nexus Mods'):
   with self.assertRaises(ValueError):j.browser_tool({})
   with self.assertRaises(ValueError):j.save_email({'body':'Hi'})
 def test_trailing_handoff_does_not_become_final_refusal(self):
  self.assertTrue(routing.handoff_reason("Good morning! I can't switch your lights directly. HANDOFF"))

if __name__=='__main__':unittest.main()
