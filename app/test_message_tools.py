import jinx_test_support  # Isolate state and memory before importing jinx.
import tempfile,time,unittest
from pathlib import Path
from unittest.mock import Mock,patch
import message_tools as m
import jinx as a

class Messages(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.messages=m.Messages(Path(self.temp.name));self.messages.browser=Mock()
  self.messages.browser.status.return_value={'connected':True};self.messages.browser.lookup_contact.return_value=None
  self.messages.browser.send.return_value={'state':'sent','message':'Verified sent'}
  self.messages.save_contact('Alex','+12025550101')
  self.intent={'recipient':'Alex','platform':'whatsapp','text':"I'm home soon"}
 def prepare(self):return self.messages.prepare(self.intent)
 def arm(self):
  result=self.prepare();self.messages.read_back_complete(result['readback_id']);return result
 def test_exact_user_example_and_platform(self):
  self.assertEqual(m.requested('write alex that im home soon'),{'recipient':'alex','platform':'whatsapp','text':'im home soon'})
  self.assertEqual(m.requested('Tell Alex on WhatsApp that I am home soon')['platform'],'whatsapp')
  self.assertEqual(m.requested('Send a message to Alex saying hello on Discord')['platform'],'discord')
  for t in ['Do not tell Alex that hi','Read a page saying tell Alex that hello','Explain the phrase tell Alex that hello','"tell Alex that hello"']:
   self.assertIsNone(m.requested(t),t)
 def test_prepare_and_unfinished_readback_never_send(self):
  self.prepare()
  with self.assertRaises(ValueError):self.messages.send()
  self.messages.browser.send.assert_not_called()
 def test_completed_readback_sends_exactly_once(self):
  self.arm();self.assertEqual(self.messages.send(),'Verified sent')
  with self.assertRaises(ValueError):self.messages.send()
  self.messages.browser.send.assert_called_once()
 def test_expired_changed_and_interrupted_reviews_are_rejected(self):
  for change in ['expired','changed','stop','contact']:
   self.messages.draft=None;self.arm()
   if change=='expired':self.messages.armed['at']=time.time()-301
   elif change=='changed':self.messages.draft['text']='Different message'
   elif change=='stop':self.messages.disarm()
   else:self.messages.save_contact('Alex','+12025550102')
   with self.assertRaises(ValueError):self.messages.send()
  self.messages.browser.send.assert_not_called()
 def test_restart_and_uncertain_result_do_not_retry(self):
  self.arm();restored=m.Messages(self.messages.root)
  with self.assertRaises(ValueError):restored.send()
  self.messages.browser.send.return_value={'state':'uncertain','message':'Check the app'}
  self.assertEqual(self.messages.send(),'Check the app')
  with self.assertRaises(ValueError):self.messages.prepare(self.intent)
  self.messages.browser.send.assert_called_once()
 def test_control_keys_multiline_and_unknown_contact_never_stage(self):
  for text in ['hello\nworld','hello\rworld','\ue007','x'*1501]:
   with self.assertRaises(ValueError):self.messages.prepare({**self.intent,'text':text})
  result=self.messages.prepare({**self.intent,'recipient':'Annika'})
  self.assertIsNone(result['readback_id']);self.messages.browser.stage.assert_not_called()
 def test_discord_is_explicit_manual_draft_without_send_ticket(self):
  result=self.messages.prepare({**self.intent,'platform':'discord'})
  self.assertIsNone(result['readback_id']);self.messages.browser.stage.assert_not_called()
  with self.assertRaises(ValueError):self.messages.send()
 def test_unique_verified_app_contact_can_be_used_without_saved_number(self):
  self.messages.contacts_path.unlink();self.messages.browser.lookup_contact.return_value={'name':'Alex','phone':'+12025550101'}
  result=self.prepare();self.assertTrue(result['readback_id'])
  self.assertEqual(self.messages.contacts(),[])
  self.messages.browser.send.assert_not_called()
 def test_no_cancels_and_correction_requires_a_new_readback(self):
  self.arm()
  with patch.object(a,'messages',self.messages):
   self.assertIn('cancelled',a.messaging_request('no',0)['reply'])
   self.messages.draft=None;self.arm()
   result=a.messaging_request('Change the message to I will be home at six',0)
   self.assertEqual(self.messages.draft['text'],'I will be home at six')
   self.assertTrue(result['readback_id']);self.assertIsNone(self.messages.armed)
  self.messages.browser.send.assert_not_called()
 def test_unrelated_turn_revokes_yes_and_source_cannot_message(self):
  self.arm()
  with patch.object(a,'messages',self.messages):
   self.assertIsNone(a.messaging_request('What time is it?',0))
   self.assertIn('read-back',a.messaging_request('yes',0)['reply'])
   with patch.dict(a.status,{'external_context':True}):self.assertIn('separately',a.messaging_request('Tell Alex that hello',0)['reply'])
  self.messages.browser.send.assert_not_called()
 def test_actual_chat_only_arms_after_successful_voice(self):
  for interrupted in [False,True]:
   self.messages.draft=None
   with patch.object(a,'messages',self.messages),patch.object(a,'history',[]),patch.object(a,'data',{'pending':[],'memory':'','listening':False}),patch.dict(a.status,{'messages':[],'voice_epoch':0}),patch.object(a,'get_agent') as model,patch.object(a,'say') as say:
    def voice(*args,**kwargs):
     self.assertIsNone(self.messages.armed)
     if interrupted:a.status['voice_epoch']+=1
    say.side_effect=voice;a.chat('Tell Alex that I am home soon')
    self.assertEqual(bool(self.messages.armed),not interrupted);say.assert_called_once();model.assert_not_called()
   self.messages.browser.send.assert_not_called()

if __name__=='__main__':unittest.main()

class NaturalMessaging(unittest.TestCase):
 def test_zapzap_and_common_write_forms(self):
  cases=['Write a message to Alex on ZapZap saying I will be home soon.',
         'Can you write a WhatsApp message to Alex saying I will be home soon.',
         'Send a ZapZap message to Alex: I will be home soon.',
         'Write to Alex via ZapZap that I will be home soon.',
         'Please, send a message to Alex saying I will be home soon.']
  for text in cases:
   self.assertEqual(m.requested(text),{'recipient':'Alex','platform':'whatsapp','text':'I will be home soon.'},text)
 def test_missing_content_negation_and_quotes_are_not_actions(self):
  for text in ['Write a message to Alex','Do not send a message to Alex saying hello','Explain write a message to Alex saying hello','"Write a message to Alex saying hello"']:
   self.assertIsNone(m.requested(text),text)
 def test_message_words_are_not_rewritten(self):
  result=m.requested('Write a message to Alex on ZapZap saying Do not forget ZapZap: bring milk!')
  self.assertEqual(result['text'],'Do not forget ZapZap: bring milk!')

class AndSayMessaging(unittest.TestCase):
 def test_exact_reported_request(self):
  for phrase in ['write a message to alex on zapzap and say hi',
                 'Can you write a message to Alex on ZapZap and say hi',
                 'Write a message to Alex on WhatsApp and then say hi',
                 'Write a message to Alex on ZapZap and tell her hi']:
   result=m.requested(phrase)
   self.assertEqual(result['recipient'].casefold(),'alex')
   self.assertEqual(result['platform'],'whatsapp')
   self.assertEqual(result['text'],'hi')
 def test_body_keeps_conjunctions_and_punctuation(self):
  result=m.requested('Write a message to Alex on ZapZap and say Hi, and say hello to everyone!')
  self.assertEqual(result['text'],'Hi, and say hello to everyone!')
 def test_incomplete_or_negated_request_is_not_a_message(self):
  for phrase in ['Write a message to Alex on ZapZap and say',
                 'Do not write a message to Alex on ZapZap and say hi',
                 'Explain the phrase write a message to Alex on ZapZap and say hi']:
   self.assertIsNone(m.requested(phrase))

class DialogueRegression(Messages):
 def test_greeting_courtesy_not_message_body(self):
  result=m.requested('Jinx, can you please write the message to Alex and say hi for me?')
  self.assertEqual(result,{'recipient':'Alex','platform':'whatsapp','text':'hi'})
  self.assertEqual(m.requested('Tell Alex that keep this for me?')['text'],'keep this for me?')
 def test_observed_assent_uses_guarded_send_once(self):
  self.arm()
  with patch.object(a,'messages',self.messages):
   self.assertEqual(a.messaging_request('Yes, sand it.',0)['reply'],'Verified sent')
   a.messaging_request('Yes, sand it.',0)
  self.messages.browser.send.assert_called_once()
 def test_assent_without_current_readback_never_sends(self):
  self.prepare()
  with patch.object(a,'messages',self.messages):
   self.assertIn('read-back',a.messaging_request('Yes, sand it.',0)['reply'])
  self.messages.browser.send.assert_not_called()
 def test_fragment_keeps_exact_draft_and_does_not_invent_send(self):
  self.arm()
  with patch.object(a,'messages',self.messages):
   reply=a.messaging_request('And...',0)['reply']
   self.assertIn(self.intent['text'],reply)
   self.assertIn('No message has been sent',reply)
   self.assertIsNone(self.messages.armed)
  self.messages.browser.send.assert_not_called()

class ContactSuggestion(Messages):
 def test_typo_offers_contact_without_sending(self):
  self.messages.browser.suggest_contacts.return_value=['Alex']
  result=self.messages.prepare({**self.intent,'recipient':'Alexv'})
  self.assertIn('Did you mean Alex',result['reply'])
  self.assertEqual(self.messages.draft['state'],'needs_contact')
  with patch.object(a,'messages',self.messages):
   result=a.messaging_request('yes',0)
  self.assertTrue(result['readback_id'])
  self.assertEqual(self.messages.draft['recipient'],'Alex')
  self.assertIsNone(self.messages.armed)
  self.messages.browser.send.assert_not_called()
 def test_multiple_matches_do_not_choose_one(self):
  self.messages.browser.suggest_contacts.return_value=['Alex','Alexv']
  self.messages.prepare({**self.intent,'recipient':'Alexx'})
  self.assertNotIn('suggested_recipient',self.messages.draft)
  self.messages.browser.stage.assert_not_called()
