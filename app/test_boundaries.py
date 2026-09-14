import jinx_test_support  # Isolate state and memory before importing jinx.
import unittest,sys,tempfile,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import jinx as a
class Boundaries(unittest.TestCase):
 def setUp(self):
  self.oldstate=a.STATE;self.olddata=a.data;self.tmp=tempfile.TemporaryDirectory();a.STATE=Path(self.tmp.name);a.data={'memory':'','pending':[],'reminders':[]}
 def tearDown(self):a.STATE=self.oldstate;a.data=self.olddata;self.tmp.cleanup()
 def test_unapproved_memory_never_written(self):
  p=a.propose({'kind':'remember','fields':{'text':'A test fact'}});self.assertEqual(a.data['memory'],'');a.confirm(p['proposal']['id']);self.assertEqual(a.data['memory'],'\nA test fact')
 def test_unrecognised_action_refused(self):
  with self.assertRaises(ValueError):a.propose({'kind':'shell','fields':{'command':'id'}})
 def test_calendar_requires_timezone(self):
  with self.assertRaises(ValueError):a.action({'id':'test','kind':'calendar_draft','fields':{'start':'2027-01-01T12:00','end':'2027-01-01T13:00'}})
 def test_explicit_date_change_refused(self):
  a.current_request='Remind me on 9 September 2026 at 10:00'
  with self.assertRaises(ValueError):a.propose({'kind':'reminder','fields':{'text':'test','when':'2026-09-15T10:00:00+02:00'}})
  a.current_request=''
 def test_email_header_injection_refused(self):
  with self.assertRaises(ValueError):a.action({'id':'test','kind':'email_draft','fields':{'to':'x@example.com\nBcc: z@example.com','subject':'test','body':'test'}})
 def test_power_command_injection_refused(self):
  with self.assertRaises(ValueError):a.action({'id':'test','kind':'power_profile','fields':{'profile':'balanced; whoami'}})
if __name__=='__main__':unittest.main()
