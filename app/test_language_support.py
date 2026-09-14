import jinx_test_support
import unittest
from unittest.mock import patch
import language_support as lang
import jinx as j
import launch_tools

class Bilingual(unittest.TestCase):
 def test_switching_language_and_product_names(self):
  for text,want in [('Hallo Jinx, wie geht es dir?','de'),('Starte Crimson Desert','de'),('Erzähl mir einen Witz','de'),('Kannst du Spotify öffnen?','de'),('Could you open Spotify please?','en'),('What is a penguin?','en'),('Die Antwort lautet zweiundvierzig.','de')]:
   self.assertEqual(lang.detect(text),want,text)
  self.assertEqual(lang.detect('okay','de'),'de')
  self.assertEqual(lang.reply_language('Please answer in German'),'de')
  self.assertEqual(lang.reply_language('Antworte auf Englisch'),'en')
 def test_voice_selection_preserves_english_choice(self):
  with patch.dict(j.status,response_language='en'):
   self.assertEqual(j.pick_voice('Hallo David, ich bin da.','breeze_tts2'),'breeze_tts2')
   self.assertEqual(j.pick_voice('Hello David. How can I help?','breeze_tts2'),'breeze_tts2')
   self.assertEqual(j.pick_voice('Here is the answer.','kokoro_emma'),'kokoro_emma')
 def test_routine_translation_preserves_title_and_quoted_payload(self):
  self.assertEqual(lang.localise('Starting Crimson Desert Enhanced','de'),'Ich starte Crimson Desert Enhanced.')
  message='Message to Alex: I will be late. Send it?'
  self.assertEqual(lang.localise(message,'de'),message)
  self.assertEqual(lang.localise('Starting Steam','en'),'Starting Steam')
 def test_german_greeting_and_launch_do_not_call_model(self):
  from test_action_routing import ENTRIES
  with patch.dict(j.data,speak=False,episodic_memory=False,language_mode='auto'),patch.dict(j.status,response_language='en'),patch.object(launch_tools,'catalog',return_value=ENTRIES),patch.object(launch_tools,'launch',return_value={'status':'launch_requested'}),patch.object(j,'run_tiered_turn') as model:
   j.chat('Starte Crimson Desert',spoken=False)
   self.assertEqual(j.status['messages'][-1]['content'],'Ich starte Crimson Desert Enhanced.')
   self.assertEqual(j.status['response_language'],'de')
   j.chat('Hallo Jinx',spoken=False)
   self.assertEqual(j.status['messages'][-1]['content'],'Hallo David, ich bin da.')
   model.assert_not_called()
 def test_german_input_gets_english_reply_without_voice_switch(self):
  with patch.dict(j.data,speak=False,episodic_memory=False,language_mode='en',voice='breeze_tts2'),patch.object(j,'run_tiered_turn') as model:
   j.chat('Hallo Jinx',spoken=False)
   self.assertEqual(j.status['response_language'],'en')
   self.assertEqual(j.status['messages'][-1]['content'],"Hi David, I'm here.")
   self.assertEqual(j.pick_voice(j.status['messages'][-1]['content'],j.data['voice']),'breeze_tts2')
   model.assert_not_called()
 def test_only_unquoted_opening_greetings_are_normalised(self):
  self.assertEqual(lang.english_greeting('Guten Morgen, David! How can I help?'),'Good morning, David! How can I help?')
  self.assertEqual(lang.english_greeting('“Guten Morgen” means good morning.'),'“Guten Morgen” means good morning.')
  self.assertEqual(lang.english_greeting('Your message: Guten Morgen!'),'Your message: Guten Morgen!')
 def test_cpu_fallback_is_multilingual_and_does_not_translate(self):
  import numpy as np
  with patch.dict(j.data,speech_engine='cpu'),patch.dict(j.status,suspended=False),patch.object(j,'cmd',return_value='Öffne bitte Spotify') as run:
   self.assertEqual(j.transcribe([np.zeros(16000,dtype='int16')]),'Öffne bitte Spotify')
   argv=run.call_args.args[0]
   self.assertIn('auto',argv);self.assertTrue(any(a.endswith('ggml-base.bin') for a in argv));self.assertNotIn('--translate',argv)
 def test_german_modal_game_request_keeps_direct_launch(self):
  self.assertEqual(launch_tools.parse('Jinx, kannst du bitte das Spiel Crimson Desert starten?'),'Crimson Desert')
  self.assertIsNone(launch_tools.parse('Kannst du bitte nicht Steam öffnen?'))
 def test_german_approval_still_requires_a_fresh_unchanged_offer(self):
  from voice_approval import Approval
  approval=Approval();item={'id':'synthetic','kind':'remember','fields':{'text':'A test'}}
  self.assertIsNone(approval.consume('ja',[item]))
  approval.arm([item]);self.assertEqual(approval.consume('ja bitte',[item])['decision'],'yes')
  approval.arm([item]);self.assertEqual(approval.consume('nein',[item])['decision'],'no')
 def test_german_review_keeps_message_url_numbers_and_wording(self):
  body='Treffen um 16:00, nicht 17:00. https://example.org/a?b=2'
  frame=f'To Alex on WhatsApp: “{body}”. Say yes or send to send this exact message, or cancel.'
  result=lang.localise_review(frame,'de')
  self.assertIn('“'+body+'”',result);self.assertIn('genau diese Nachricht',result)

if __name__=='__main__':unittest.main()
