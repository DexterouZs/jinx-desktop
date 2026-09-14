import jinx_test_support
import unittest
from unittest.mock import patch
import calendar_intents
import jinx as j
import jinx_skills

ACTUAL='Jings, can you actually delete my appointment for tomorrow?'

class CalendarLatency(unittest.TestCase):
 def test_observed_request_is_direct_delete_intent(self):
  self.assertEqual(calendar_intents.parse(ACTUAL)['operation'],'delete')

 def test_does_not_claim_read_create_timer_or_dictation(self):
  for text in ('Show my appointments tomorrow','Add an appointment tomorrow','Cancel my timer',
               'Write an email saying delete my appointment tomorrow',
               'Remember that I need to delete an appointment','Do not delete my appointment',
               'Explain the phrase delete my appointment'):
   self.assertIsNone(calendar_intents.requested(text),text)

 def test_actual_request_returns_without_models_or_calendar_access(self):
  with patch.object(j,'run_tiered_turn',side_effect=AssertionError('must not load 27B')), \
       patch.object(j,'understood_task',side_effect=AssertionError('must not plan unsupported task')), \
       patch.object(calendar_intents.deletion,'candidates',return_value=[]), \
       patch.object(j,'say'),patch.object(j.voice.breeze,'release'), \
       patch.dict(j.data,speak=False,episodic_memory=False),patch.object(j,'task_router',None):
   j.chat(ACTUAL,False)
   self.assertEqual(j.status['error'],'')
   self.assertEqual(j.status['active_model'],'Direct tools')
   self.assertIn('no matching appointment',j.status['last_draft'])
   self.assertEqual(j.status['tools_used'],['jinx_calendar'])

 def test_common_skills_are_compact_but_available(self):
  for text in (ACTUAL,'write an email','play music','open Nexus Mods','search the web'):
   self.assertLess(len(jinx_skills.brief_for_request(text)),1400,text)
  self.assertIn('jinx_calendar',jinx_skills.brief_for_request(ACTUAL))
  self.assertIn('Music:',jinx_skills.view({'name':'everyday'})['instructions'])

if __name__=='__main__':unittest.main()
