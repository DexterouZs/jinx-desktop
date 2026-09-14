import unittest,tempfile,json,datetime as dt
from pathlib import Path
from unittest.mock import patch
import reminder_delivery as r
class Delivery(unittest.TestCase):
 def test_once_even_with_equivalent_timezones(self):
  with tempfile.TemporaryDirectory() as d,patch.object(r.subprocess,'run') as run:
   item={'id':'test','when':'2026-09-11T13:00:00+02:00','text':'test'}
   self.assertTrue(r.deliver(d,item));item['when']='2026-09-11T11:00:00+00:00'
   self.assertFalse(r.deliver(d,item));self.assertEqual(run.call_count,1)
 def test_notification_failure_is_retryable(self):
  with tempfile.TemporaryDirectory() as d,patch.object(r.subprocess,'run',side_effect=OSError):
   with self.assertRaises(OSError):r.deliver(d,{'id':'a','when':'2026-09-11T13:00:00+02:00','text':'test'})
   self.assertEqual([p.name for p in (Path(d)/'notification-delivery').iterdir()],['lock'])
 def test_due_without_mutating_assistant_state(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'state.json';s=json.dumps({'reminders':[{'id':'a','when':'2026-09-11T13:00:00+02:00','text':'test','done':False}]});p.write_text(s)
   self.assertEqual(len(r.due_items(d,dt.datetime(2026,9,11,14,tzinfo=dt.timezone.utc).timestamp())),1)
   self.assertEqual(p.read_text(),s)
