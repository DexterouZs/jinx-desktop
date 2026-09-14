import jinx_test_support
import copy,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch,Mock
import jinx as j
from long_memory import LongMemory
from task_understanding import Tasks
import browser_actions,routing

class FreshSessions(unittest.TestCase):
 def setUp(self):
  self.status=copy.deepcopy(j.status);self.history=j.history[:];self.agent=j.agent
  j.status.update(busy=False,ptt=False,conversation=False,suspended=False)
 def tearDown(self):
  j.status.clear();j.status.update(self.status);j.history[:]=self.history;j.agent=self.agent
  if j.conversation_gate.locked():j.conversation_gate.release()
 def test_new_click_resets_chat_not_saved_data(self):
  j.history[:]=[{'role':'user','content':'Old Blender topic'}]
  j.status.update(messages=j.history[:],last_heard='old speech',email_draft={'path':'saved.txt'})
  saved=copy.deepcopy(j.data);router=Mock()
  with patch.object(j,'mic_muted',return_value=False),patch.object(j.threading,'Thread'),patch.object(j,'task_router',router),patch.object(j.messages,'disarm') as disarm,patch.object(j.workspace,'clear'):
   j.start_conversation()
  self.assertEqual(j.history,[]);self.assertEqual(j.status['messages'],[])
  self.assertTrue(j.status['session_id']);self.assertEqual(j.status['last_heard'],'')
  self.assertNotIn('email_draft',j.status);self.assertIsNone(j.agent)
  self.assertEqual(j.data,saved);router.begin_session.assert_called_once();disarm.assert_called_once()
 def test_second_click_stops_without_resetting_current_chat(self):
  j.status.update(conversation=True,session_id='current')
  j.history[:]=[{'role':'user','content':'Current topic'}]
  with patch.object(j,'new_voice_session') as fresh,patch.object(j.threading,'Thread'):
   j.start_conversation()
  fresh.assert_not_called();self.assertEqual(j.status['session_id'],'current');self.assertEqual(len(j.history),1)
 def test_each_new_start_has_a_different_session(self):
  with patch.object(j,'mic_muted',return_value=False),patch.object(j.threading,'Thread'),patch.object(j.workspace,'clear'):
   j.start_conversation();first=j.status['session_id'];j.stop_turn();j.conversation_gate.release()
   j.history.append({'role':'user','content':'Previous session'})
   j.start_conversation()
  self.assertNotEqual(j.status['session_id'],first);self.assertEqual(j.history,[])
 def test_muted_or_busy_start_does_not_erase_chat(self):
  j.history[:]=[{'role':'user','content':'Keep this'}]
  with patch.object(j,'mic_muted',return_value=True),patch.object(j,'new_voice_session') as fresh:
   with self.assertRaises(ValueError):j.start_conversation()
   fresh.assert_not_called()
  self.assertEqual(len(j.history),1)
 def test_old_draft_is_preserved_but_not_implicit_new_task_context(self):
  draft={'state':'prepared','created_at':time.time()-1,'recipient':'Alex','text':'Hello'}
  messages=Mock(draft=draft);router=Tasks(Mock(),messages,Mock(),Mock())
  self.assertEqual(router.context()['recipient'],'Alex')
  router.pending={'kind':'music'};router.candidate={'uri':'old'};router.begin_session()
  self.assertIsNone(router.context());self.assertIsNone(router.candidate);self.assertEqual(messages.draft,draft)
 def test_facts_survive_without_implicitly_recalling_old_chats(self):
  with tempfile.TemporaryDirectory() as root:
   m=LongMemory(Path(root)/'memory.sqlite3',embed=lambda text:None)
   m.add('fact','David likes tea.',pinned=True,semantic=False)
   m.add('episode','Blender penguins old conversation',semantic=False)
   fresh=m.prompt_block('Blender penguins',semantic=False,include_episodes=False)
   self.assertIn('David likes tea',fresh);self.assertNotIn('old conversation',fresh)
   self.assertIn('old conversation',m.prompt_block('Blender penguins',semantic=False,include_episodes=True))
 def test_latest_nexus_phrases_resolve(self):
  for text in ('Jinx, can you open for me the Nexus Mod page from Nexus?', 'Open the web page from Nexus mode.'):
   self.assertEqual(browser_actions.parse(text)['url'],'https://www.nexusmods.com/',text)
 def test_calendar_needs_tools_and_false_claims_escalate(self):
  self.assertEqual(routing.model_for('Jinx, can you tell me what is my next appointment?')[0],routing.DEEP)
  self.assertTrue(routing.handoff_reason("Got it, David! I'll set the reminder for tomorrow at 13:00."))
  self.assertTrue(routing.handoff_reason("I can't set reminders or access your calendar directly, David—that's something I'll need to pass off to you via HANDOFF."))
 def test_recognised_clock_request_uses_actual_clock(self):
  self.assertIn('It is ',j.personal_request('Jinx, but time is it?')['reply'])

if __name__=='__main__':unittest.main()
