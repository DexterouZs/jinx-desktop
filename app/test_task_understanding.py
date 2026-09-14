import unittest,time
from unittest.mock import Mock
from task_understanding import Tasks,validate,FIELDS

def plan(kind,**kw):return {**dict.fromkeys(FIELDS,''),'kind':kind,**kw}
class TasksTest(unittest.TestCase):
 def setUp(self):
  self.messages=Mock(draft=None)
  self.messages.prepare.return_value={'reply':'Review exact message','readback_id':'review'}
  self.music=Mock();self.music.intent.return_value=None;self.music.perform.return_value={'reply':'Verified playing'}
  self.admin=Mock();self.admin.app_catalog.return_value={'spotify':{'name':'Spotify'}}
  self.interpret=Mock();self.now=0
  self.tasks=Tasks(self.interpret,self.messages,self.music,self.admin,lambda:self.now)
  self.tasks.search=Mock()
 def request(self,text,p):
  self.interpret.return_value=p
  return self.tasks.requested(text,'auto',lambda:False)
 def test_multi_turn_missing_body_then_correction(self):
  r=self.request('Could you message Alex?',plan('message',recipient='Alex'))
  self.assertIn('What should I say',r['reply']);self.messages.prepare.assert_not_called()
  r=self.request('Tell her I will be late',plan('message',recipient='Alex',text='I will be late'))
  self.assertEqual(self.interpret.call_args.args[1],{'kind':'message','recipient':'Alex','text':''})
  self.assertTrue(r['message_review']);self.messages.send.assert_not_called()
  self.messages.draft={'recipient':'Alex','text':'I will be late','state':'prepared','created_at':time.time()}
  r=self.request('Actually say I will be home at six',plan('message',recipient='Alex',text='I will be home at six'))
  self.assertEqual(self.messages.prepare.call_args.args[0]['text'],'I will be home at six')
  self.messages.send.assert_not_called()
 def test_confirmations_never_use_model_or_send_tool(self):
  for text in ['Yes, send it.','yes','cancel']:
   self.assertIsNone(self.tasks.requested(text,'auto',lambda:False))
  self.interpret.assert_not_called();self.messages.send.assert_not_called()
 def test_plan_cannot_send_or_run_shell(self):
  for kind in ['send','shell','software_install']:
   with self.assertRaises(ValueError):validate(plan(kind))
 def test_external_sources_and_cancelled_tasks_never_execute(self):
  self.assertIsNone(self.tasks.requested('message Alex saying hello','auto',lambda:False,external=True))
  self.interpret.return_value=plan('message',recipient='Alex',text='hello')
  self.tasks.requested('message Alex saying hello','auto',lambda:True)
  self.messages.prepare.assert_not_called()
 def test_tool_failure_is_reported_not_model_success(self):
  self.music.perform.side_effect=ValueError('Spotify is not responding')
  r=self.request('I want Spotify to continue',plan('music',music_action='play'))
  self.assertIn('Spotify is not responding',r['reply'])
 def test_named_music_never_plays_unrelated_songs(self):
  self.tasks.search.find.side_effect=ValueError('No verified track match')
  r=self.request('Find Adele on Spotify',plan('music',music_action='search',artist='Adele'))
  self.assertIn('No verified track match',r['reply']);self.music.perform.assert_not_called()
 def test_missing_recipient_then_answer(self):
  self.request('Send a message saying hello',plan('message',text='hello'))
  self.request('Alex',plan('message',recipient='Alex',text='hello'))
  self.assertEqual(self.messages.prepare.call_args.args[0]['recipient'],'Alex')
 def test_unrelated_turn_discards_incomplete_slots(self):
  self.request('Message Alex',plan('message',recipient='Alex'))
  self.request('What is the weather',plan('none'))
  self.assertIsNone(self.tasks.pending)
 def test_incomplete_task_expires(self):
  self.request('Message Alex',plan('message',recipient='Alex'))
  self.now=301;self.assertIsNone(self.tasks.context())
 def test_unknown_app_and_fabricated_link_rejected(self):
  self.request('Open calculator',plan('app',app='shell'))
  self.admin.desktop_apps.assert_not_called()
  self.request('Play music on Spotify',plan('music',music_action='uri',uri='spotify:track:madeup'))
  self.music.perform.assert_not_called()
 def test_invalid_model_output_does_not_fall_through_to_general_model(self):
  r=self.request('Message Alex',{'kind':'message'})
  self.assertIn('Nothing was changed',r['reply']);self.messages.prepare.assert_not_called()
