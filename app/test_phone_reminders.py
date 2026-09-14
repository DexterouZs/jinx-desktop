import jinx_test_support  # Isolate state and memory before importing jinx.
import unittest,tempfile,json
from pathlib import Path
from unittest.mock import patch
import morgen_tools as m
import jinx as j
from test_morgen_tools import C,F,E
class PhoneReminderTests(unittest.TestCase):
 def test_alert_roundtrip_accepts_google_normalisation(self):
  with tempfile.TemporaryDirectory() as d,patch.object(m,'STATE',Path(d)),patch.object(m,'config',return_value=C),patch.object(m,'api',side_effect=[{'event':E},{'event':{**E,'alerts':{'a':{'action':'display','trigger':{'offset':'-P0D'}}}}}]) as api:
   self.assertIn('Added',m.create({**F,'_reminder':True},'0000000000000001'))
   body=api.call_args_list[0].kwargs['body'];self.assertFalse(body['useDefaultAlerts']);self.assertEqual(body['freeBusyStatus'],'free');self.assertEqual(body['alerts']['jinx']['trigger']['offset'],'PT0S')
 def test_direct_reminder_prepares_cloud_proposal(self):
  item={'id':'test','kind':'reminder','fields':{'when':'2030-01-01T13:00:00+01:00','text':'Work','_calendar':C}}
  with patch.object(j,'propose',return_value={'proposal':item}) as propose:
   result=j.synced_reminder_request('Remind me tomorrow at 13:00 to go to work at 16:00')
   self.assertEqual(propose.call_args.args[0]['kind'],'reminder');self.assertEqual(result['_approval_items'],[item]);self.assertIn('yes or no',result['reply'])
 def test_timers_stay_local(self):
  with patch.object(j,'propose') as propose:
   self.assertIsNone(j.synced_reminder_request('Set a timer for ten minutes'));propose.assert_not_called()
if __name__=='__main__':unittest.main()
