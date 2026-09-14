import unittest,tempfile,json,datetime as dt
from pathlib import Path
from unittest.mock import patch
import morgen_tools as m
C={'id':'calendar','accountId':'account','name':'Personal','integrationId':'google'}
F={'title':'Test','start':'2030-01-01T12:00:00+01:00','end':'2030-01-01T12:30:00+01:00','_calendar':C}
E={'id':'event','title':'Test','start':'2030-01-01T11:00:00','duration':'PT30M','timeZone':'Etc/UTC','calendarId':'calendar','accountId':'account'}
class MorgenTests(unittest.TestCase):
 def setUp(self):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
  p=patch.object(m,'STATE',Path(t.name));p.start();self.addCleanup(p.stop)
  p=patch.object(m,'config',return_value=C);p.start();self.addCleanup(p.stop)
 def test_write_verified_and_retry_reads_only(self):
  with patch.object(m,'api',side_effect=[{'event':E},{'event':E},{'event':E}]) as api:
   self.assertIn('Added',m.create(F,'000000000000feed'));self.assertIn('Added',m.create(F,'000000000000feed'))
   self.assertEqual([v.args[0] for v in api.call_args_list],['events/create','events','events'])
   body=api.call_args_list[0].kwargs['body'];self.assertNotIn('participants',body);self.assertEqual(body['start'],'2030-01-01T11:00:00')
 def test_uncertain_write_never_repeated(self):
  with patch.object(m,'api',side_effect=ValueError('Network failed')) as api:
   with self.assertRaises(ValueError):m.create(F,'000000000000feed')
   with self.assertRaisesRegex(ValueError,'duplicate'):m.create(F,'000000000000feed')
   self.assertEqual(api.call_count,1)
 def test_wrong_readback_never_reports_success(self):
  with patch.object(m,'api',side_effect=[{'event':E},{'event':{**E,'title':'Different'}}]):
   with self.assertRaisesRegex(ValueError,'did not match'):m.create(F,'000000000000feed')
 def test_calendar_change_invalidates_confirmation(self):
  with patch.object(m,'config',return_value={**C,'id':'different'}),patch.object(m,'api') as api:
   with self.assertRaisesRegex(ValueError,'selection changed'):m.create(F,'000000000000feed')
   api.assert_not_called()
 def test_read_uses_local_timezone(self):
  with patch.object(m,'api',return_value={'events':[E]}) as api:
   r=m.read({'date':'2030-01-01','days':1})
   self.assertEqual(r['events'][0]['start'],'2030-01-01T12:00:00+01:00')
   self.assertEqual(api.call_args.args[1]['calendarIds'],'calendar')
 def test_all_day_and_dst_elapsed_duration(self):
  a,b=m.times({**E,'start':'2030-01-01T00:00:00','duration':'P1D','showWithoutTime':True})
  self.assertEqual(b,dt.date(2030,1,2))
  a,b=m.times({**E,'start':'2026-10-25T00:30:00','duration':'PT2H'})
  self.assertEqual(a.isoformat(),'2026-10-25T02:30:00+02:00');self.assertEqual(b.isoformat(),'2026-10-25T03:30:00+01:00')
if __name__=='__main__':unittest.main()

class MultiCalendarTests(unittest.TestCase):
 setUp=MorgenTests.setUp
 def test_daily_read_includes_all_selected_calendars(self):
  (m.STATE/'morgen-readable-calendars.json').write_text(json.dumps([{'id':'calendar','accountId':'account','name':'Personal'},{'id':'work','accountId':'account','name':'Work'}]))
  with patch.object(m,'api',return_value={'events':[E,{**E,'id':'event2','calendarId':'work','title':'Work meeting'}]}) as api:
   result=m.read({'date':'2030-01-01','days':1})
   self.assertEqual(api.call_args.args[1]['calendarIds'],'calendar,work')
   self.assertEqual([e['calendar'] for e in result['events']],['Personal','Work'])
