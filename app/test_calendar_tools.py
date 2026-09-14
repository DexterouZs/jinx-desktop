import datetime as dt
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import calendar_tools as c
import morgen_tools as m

class CalendarTests(unittest.TestCase):
 def setUp(self):
  folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
  config=Path(folder.name)/'config';config.write_text('{}')
  p=patch.object(c,'CONFIG',config);p.start();self.addCleanup(p.stop)
 def calendar(self,body):
  folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
  p=Path(folder.name)/'calendar.ics';p.write_text('BEGIN:VCALENDAR\nVERSION:2.0\n'+body+'END:VCALENDAR\n')
  return p
 def test_winter_timezone_and_recurrence(self):
  p=self.calendar('BEGIN:VEVENT\nUID:test\nDTSTART:20300101T110000Z\nDTEND:20300101T111000Z\nRRULE:FREQ=DAILY;COUNT=2\nSUMMARY:Work\nEND:VEVENT\n')
  with patch.object(c,'CALENDAR_FILE',p),patch.object(c,'calendar_id',return_value='7'):
   result=c.read({'date':'2030-01-01','days':3})
  self.assertEqual([e['start'] for e in result['events']],['2030-01-01T12:00:00+01:00','2030-01-02T12:00:00+01:00'])
 def test_summer_timezone(self):
  p=self.calendar('BEGIN:VEVENT\nUID:test\nDTSTART:20300701T110000Z\nDTEND:20300701T111000Z\nSUMMARY:Work\nEND:VEVENT\n')
  with patch.object(c,'CALENDAR_FILE',p),patch.object(c,'calendar_id',return_value='7'):
   self.assertEqual(c.read({'date':'2030-07-01'})['events'][0]['start'],'2030-07-01T13:00:00+02:00')
 def test_all_day(self):
  p=self.calendar('BEGIN:VEVENT\nUID:test\nDTSTART;VALUE=DATE:20300101\nDTEND;VALUE=DATE:20300102\nSUMMARY:Holiday\nEND:VEVENT\n')
  with patch.object(c,'CALENDAR_FILE',p),patch.object(c,'calendar_id',return_value='7'):
   e=c.read({'date':'2030-01-01'})['events'][0]
  self.assertTrue(e['all_day']);self.assertEqual(e['start'],'2030-01-01')
 def test_verification_rejects_wrong_time(self):
  p=self.calendar('BEGIN:VEVENT\nUID:test\nDTSTART:20300101T110000Z\nDTEND:20300101T111000Z\nSUMMARY:Work\nEND:VEVENT\n')
  with patch.object(c,'CALENDAR_FILE',p):
   self.assertFalse(c.verified('test','Work',dt.datetime(2030,1,1,12,tzinfo=dt.timezone.utc),dt.datetime(2030,1,1,12,10,tzinfo=dt.timezone.utc)))
 def test_morgen_requires_real_connection(self):
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)/'config';p.write_text('{"preferred_app":"morgen"}')
   with patch.object(c,'CONFIG',p),patch.object(m,'STATE',Path(folder)),patch.object(c,'run') as run:
    self.assertIn('API connection',c.read({})['error']);run.assert_not_called()
 def test_missing_end_cannot_be_scheduled(self):
  with self.assertRaises(ValueError):c.validate({'title':'Work','start':'2030-01-01T12:00:00+01:00'})

if __name__=='__main__':unittest.main()
