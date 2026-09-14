import unittest
import routing as r

class ModelRouting(unittest.TestCase):
 def test_everyday_conversation_uses_the_fast_model(self):
  for text in ['Hello','What time is it','Are the lights on','Thanks Jinx',
               'Set a timer for ten minutes','How are you']:
   self.assertEqual(r.model_for(text)[0],r.FAST,text)

 def test_authoring_and_reasoning_use_the_deep_model(self):
  for text in ['Write me an email to the landlord','Explain why the fan is loud',
               'Debug this python function','Summarise this article',
               'Compare CachyOS and Arch','Troubleshoot my wifi']:
   self.assertEqual(r.model_for(text)[0],r.DEEP,text)

 def test_terminal_requests_reach_tools_even_with_social_prefix(self):
  words=['terminal','command','run','execute','script','check whether',"why isn't",
         'why is not','not working','fix','restart','kill','process','service','log',
         'install','update','disk','cpu','gpu','memory usage','network','wifi','ping',
         'port','file','folder','directory',"why doesn't Spotify work",
         'show running processes','list files','read logs']
  for word in words:
   for prefix in ['', 'hey Jinx, ', 'thanks, now ']:
    text=prefix+word+' example'
    self.assertEqual(r.model_for(text)[0],r.DEEP,text)
  for text in ['hello','thanks','how are you','good morning','I like brunch','what an opportunity']:
   self.assertEqual(r.model_for(text)[0],r.FAST,text)

 def test_vision_always_uses_the_projector_model(self):
  # Only the 27B carries a vision projector, so this must never be the 4B.
  self.assertEqual(r.model_for('anything at all',vision=True)[0],r.DEEP)
  self.assertEqual(r.model_for('Look at my screen')[0],r.DEEP)
  self.assertEqual(r.model_for('Read this page aloud')[0],r.DEEP)

 def test_long_requests_and_long_conversations_escalate(self):
  self.assertEqual(r.model_for('x '*200)[0],r.DEEP)
  self.assertEqual(r.model_for('Are the lights on',history_turns=9)[0],r.FAST)
  self.assertEqual(r.model_for('Are the lights on',shared_document=True)[0],r.FAST)
  self.assertEqual(r.model_for('Explain this document',shared_document=True)[0],r.DEEP)

 def test_empty_request_does_not_load_the_large_model(self):
  self.assertEqual(r.model_for('')[0],r.FAST)
  self.assertEqual(r.model_for(None)[0],r.FAST)

class VoiceRouting(unittest.TestCase):
 def test_confirmations_use_the_quick_voice(self):
  for text in ['Timer set for ten minutes.','Kitchen lamp on','Done.',
               'Paused.','Volume set to 40%']:
   self.assertEqual(r.voice_for(text)[0],r.QUICK,text)

 def test_conversation_keeps_the_cloned_voice(self):
  for text in ['I had a look, and the fan profile is set to balanced, so it should stay quiet.',
               'Well, that depends: are you asking about the battery or the charger?',
               'Your kernel is 7.2.3, which is current, and nothing has failed today.']:
   self.assertEqual(r.voice_for(text)[0],r.CLONED,text)

 def test_empty_reply_falls_back_to_the_saved_voice(self):
  self.assertEqual(r.voice_for('')[0],r.CLONED)

 def test_length_boundary_is_respected(self):
  self.assertEqual(r.voice_for('a'*20)[0],r.QUICK)
  self.assertEqual(r.voice_for('a'*21)[0],r.CLONED)

 def test_ordinary_short_sentences_keep_the_cloned_voice(self):
  # Jinx answers everyday questions in one or two sentences; those are
  # conversation, not acknowledgements, and must not all become Piper.
  for text in ['A longer conversational reply that goes on a while.',
               'It has been on since about four.',
               'Nothing has failed today, happily.']:
   self.assertEqual(r.voice_for(text)[0],r.CLONED,text)

 def test_device_replies_are_recognised(self):
  self.assertTrue(r.is_device_reply('Kitchen lamp on'))
  self.assertTrue(r.is_device_reply('Desk lamp set to 40%'))
  self.assertFalse(r.is_device_reply('The weather looks fine today'))



class FastPersona(unittest.TestCase):
 def test_fast_persona_is_short_enough_to_be_cheap(self):
  # Roughly 5 characters per token on this tokeniser; keep well under 200.
  self.assertLess(len(r.FAST_PERSONA)/5,200)

 def test_handoff_is_detected_tolerantly(self):
  for reply in ['HANDOFF','handoff','HANDOFF.',' Handoff '," HANDOFF\n"]:
   self.assertTrue(r.needs_handoff(reply),repr(reply))

 def test_ordinary_replies_are_not_handoffs(self):
  for reply in ['The kitchen lamp is on.','','I can hand off to the big model if you like.']:
   self.assertFalse(r.needs_handoff(reply),repr(reply))

 def test_persona_selection_matches_the_model(self):
  self.assertEqual(r.persona_for(r.FAST,'FULL'),r.FAST_PERSONA)
  self.assertEqual(r.persona_for(r.DEEP,'FULL'),'FULL')



class Escalation(unittest.TestCase):
 def test_control_token_escalates_even_with_stray_punctuation(self):
  for reply in ['HANDOFF','handoff.','  HANDOFF  ','HANDOFF!']:
   self.assertTrue(r.handoff_reason(reply),repr(reply))

 def test_real_answers_are_kept(self):
  for reply in ['The kitchen lamp is on.','Just gone half four.',
                'I can hand off to the bigger model whenever you want me to, David.']:
   self.assertEqual(r.handoff_reason(reply),'',repr(reply))

 def test_failure_modes_escalate_rather_than_answering_badly(self):
  self.assertTrue(r.handoff_reason(''))
  self.assertTrue(r.handoff_reason('   '))
  self.assertTrue(r.handoff_reason(None))
  self.assertTrue(r.handoff_reason('anything',error=TimeoutError('timed out')))
  self.assertTrue(r.handoff_reason('a long truncated ramble',done_reason='length'))

 def test_a_turn_can_escalate_only_once(self):
  self.assertEqual(r.MAX_ESCALATIONS,1)

 def test_idle_models_both_expire(self):
  self.assertEqual(r.KEEP_ALIVE_FAST,'60s')
  self.assertNotEqual(r.KEEP_ALIVE_DEEP,-1)

 def test_keep_alive_values_are_shapes_ollama_accepts(self):
  # A string keep_alive is parsed as a Go duration: "-1" is a 400, "4m" is not.
  for value in (r.KEEP_ALIVE_FAST,r.KEEP_ALIVE_DEEP):
   if isinstance(value,str):
    self.assertRegex(value,r'^\d+(ns|us|ms|s|m|h)$',f'{value!r} needs a duration unit')
   else:
    self.assertIsInstance(value,int)



class LiveInformationRouting(unittest.TestCase):
 def test_requests_needing_live_data_reach_the_agent_tier(self):
  # Only the 27B agent can call jinx_web_search; the 4B would answer from
  # stale weights and sound confident about it.
  for text in ['search for the Proton 11 release notes','look up the train times',
               "what's the weather tomorrow",'find out who won the match',
               'what is the latest CachyOS news','google the price of a Z13']:
   self.assertEqual(r.model_for(text)[0],r.DEEP,text)

 def test_everyday_chat_is_not_dragged_into_the_slow_tier(self):
  for text in ['hello','what do you make of Wednesdays','thanks','are you there']:
   self.assertEqual(r.model_for(text)[0],r.FAST,text)

if __name__=='__main__':unittest.main()
