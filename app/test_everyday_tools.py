import jinx_test_support  # Isolate state and memory before importing jinx.
import copy,datetime as dt,tempfile,threading,unittest
from pathlib import Path
from zoneinfo import ZoneInfo
from unittest.mock import Mock,patch
import everyday_tools as e
import jinx as a

class Everyday(unittest.TestCase):
 def setUp(self):
  self.now=dt.datetime(2026,9,9,14,30,tzinfo=ZoneInfo('Europe/Paris'))
  self.data={'reminders':[]};self.save=Mock();self.lock=threading.RLock()
 def test_spoken_arithmetic_and_exact_conversions(self):
  for text,value in [('What is twenty three times seventeen?', '391'),('Calculate 40 minus 17','23'),('What is fifteen percent of eighty','12'),('Calculate (35 * 4) / 60','2.333333333333333333333333333'),('Convert five miles to kilometres.','8.04672 kilometres.'),('Convert 32 Fahrenheit to Celsius','0 degrees Celsius.'),('What is one hundred and twenty plus three','123')]:
   self.assertEqual(e.calculation(text)['reply'],value,text)
  for text in ['Explain the phrase set a five minute timer','Do not calculate 1 + 1','What is the weather','Translate: set a timer for five minutes']:
   self.assertIsNone(e.calculation(text));self.assertIsNone(e.schedule_intent(text))
 def test_duration_and_named_timer(self):
  for text,seconds in [('Set a timer for five minutes',300),('Start a 5-minute timer named pasta',300),('Set a timer for one hour and thirty minutes',5400),('Set a timer for half an hour',1800)]:
   args=e.schedule_intent(text,self.now)
   self.assertEqual(dt.datetime.fromisoformat(args['when']).timestamp()-self.now.timestamp(),seconds)
  self.assertEqual(e.schedule_intent('Start a 5-minute timer named pasta',self.now)['text'],'pasta')
 def test_explicit_relative_reminder_and_dst(self):
  for text in ['Remind me in ten minutes to check the oven','Remind me to check the oven in ten minutes']:
   args=e.schedule_intent(text,self.now);self.assertEqual(args['text'],'check the oven');self.assertEqual(dt.datetime.fromisoformat(args['when']).minute,40)
  now=dt.datetime(2026,10,24,14,tzinfo=ZoneInfo('Europe/Paris'))
  due=e.schedule_intent('Set an alarm for tomorrow at 7 am',now)['when']
  self.assertTrue(due.endswith('+01:00'));self.assertIn('T07:00',due)
  with self.assertRaises(ValueError):e.schedule_intent('Set an alarm for tomorrow at 2:30 am',now)
 def test_copied_system_timezone_and_spoken_clock_words(self):
  import io
  tzif=Path('/usr/share/zoneinfo/Europe/Paris').read_bytes()
  with patch.object(e.Path,'open',return_value=io.BytesIO(tzif)):
   zone=e.local_now().tzinfo
  self.assertEqual(dt.datetime(2026,10,25,7,tzinfo=zone).utcoffset(),dt.timedelta(hours=1))
  for text,hour in [('Set an alarm for tomorrow at seven am',7),('Set an alarm for tomorrow at noon',12),('Set an alarm for tomorrow at 7:30 p.m.',19)]:
   self.assertEqual(dt.datetime.fromisoformat(e.schedule_intent(text,self.now)['when']).hour,hour)
 def test_ambiguous_invalid_and_source_requests_never_save(self):
  for text in ['Set an alarm for seven','Set an alarm for 7','Set an alarm for 25:00','Set a timer for zero minutes','Set a timer for minus five minutes','Remind me every day at 7 to drink water','Remind me to do it sometime']:
   result=e.requested(text,self.data,self.save,self.lock);self.assertTrue(result['reply']);self.assertEqual(self.data['reminders'],[])
  for text in ['Do not set a timer for five minutes','The page says set a timer for five minutes','Explain "remind me in ten minutes to drink water"','Cancel all my reminders','Write a story about a timer']:
   self.assertIsNone(e.requested(text,self.data,self.save,self.lock),text)
  self.save.assert_not_called()
 def test_persistence_cancellation_ambiguity_and_failure(self):
  def request(text):return e.schedule(text,self.data,self.save,self.lock,self.now)
  request('Set a timer for five minutes named tea');request('Set a timer for ten minutes named pasta')
  self.assertEqual(len(self.data['reminders']),2)
  self.assertIn('Name',request('Cancel my timer')['reply']);self.assertFalse(any(r['done'] for r in self.data['reminders']))
  self.assertIn('300 seconds',request('How long is left on my timer named tea')['reply'])
  request('Cancel my timer named tea');self.assertTrue(self.data['reminders'][0]['cancelled']);self.assertFalse(self.data['reminders'][1]['done'])
  self.save.side_effect=OSError('disk full');before=copy.deepcopy(self.data)
  with self.assertRaises(OSError):request('Set a timer for two minutes')
  self.assertEqual(before,self.data)
 def test_note_is_saved_verbatim_to_new_file(self):
  with tempfile.TemporaryDirectory() as directory,patch('workbench.Path.home',return_value=Path(directory)):
   result=e.requested('Write this down: Buy coffee tomorrow!',self.data,self.save,self.lock)
   self.assertEqual(Path(result['note_path']).read_text(),'Buy coffee tomorrow!\n')
   self.assertEqual(Path(result['note_path']).stat().st_mode&0o777,0o600)
 def test_reminders_fire_once_and_retry_failed_notification(self):
  data={'reminders':[{'id':'fixture','when':'2020-01-01T00:00:00+00:00','text':'--test note','done':False,'kind':'timer'}]}
  with patch.object(a,'data',data),patch.object(a,'save'),patch.object(a,'status',{'messages':[]}),patch.object(a.subprocess,'run') as notify:
   notify.side_effect=OSError('notifications unavailable');a.check_reminders();self.assertFalse(data['reminders'][0]['done'])
   notify.side_effect=None;a.check_reminders();a.check_reminders();self.assertTrue(data['reminders'][0]['done']);self.assertEqual(notify.call_count,2)
   self.assertIn('--',notify.call_args.args[0])
 def test_chat_fast_route_does_not_call_model_or_change_pending(self):
  data={**copy.deepcopy(a.data),'reminders':[]};pending=copy.deepcopy(data['pending'])
  status={**a.status,'messages':[],'voice_epoch':0}
  with patch.object(a,'data',data),patch.object(a,'status',status),patch.object(a,'save'),patch.object(a,'get_agent') as model,patch.object(a,'history',[]),patch.object(a,'messaging_request',return_value=None):
   a.chat('Set a timer for five minutes',False)
   self.assertEqual(len(data['reminders']),1);self.assertEqual(data['pending'],pending);model.assert_not_called();self.assertEqual(status['error'],'')

class VoiceCache(unittest.TestCase):
 def test_cache_preserves_voice_pace_cancellation_and_release(self):
  from voices import Voices,VoiceCancelled
  voice=Voices();voice.jinx=Mock(gpu_failed=False)
  def synth(text,path,speed,cancelled):Path(path).write_bytes(b'fixture wave');return {'engine':'cuda'}
  voice.jinx.synthesise.side_effect=synth
  with tempfile.TemporaryDirectory() as directory:
   path=Path(directory)/'test.wav'
   first=voice.synthesise('Timer cancelled.',path,'jinx_local',.9)
   hit=voice.synthesise('Timer cancelled.',path,'jinx_local',.9)
   self.assertTrue(hit['cached']);self.assertEqual(hit['voice'],first['voice']);self.assertEqual(voice.jinx.synthesise.call_count,1)
   voice.synthesise('Timer cancelled.',path,'jinx_local',1.0);self.assertEqual(voice.jinx.synthesise.call_count,2)
   with self.assertRaises(VoiceCancelled):voice.synthesise('Timer cancelled.',path,'jinx_local',.9,cancelled=lambda:True)
   for i in range(40):voice.synthesise(str(i),path,'jinx_local',.9)
   self.assertLessEqual(len(voice.cache),32);voice.release();self.assertEqual(voice.cache_bytes,0)
if __name__=='__main__':unittest.main()
