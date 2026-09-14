import jinx_test_support
import unittest,datetime as dt
from unittest.mock import patch
from zoneinfo import ZoneInfo
import jinx
class Dates(unittest.TestCase):
 def test_today_cannot_be_tomorrow(self):
  tomorrow=dt.datetime.now(ZoneInfo('Europe/Paris'))+dt.timedelta(days=1)
  with patch.object(jinx,'current_request','Remind me today at 13:00'),patch.dict(jinx.status,{'external_context':False}),patch.object(jinx.calendar_tools,'calendar_id'),patch('morgen_tools.config',return_value={}):
   with self.assertRaisesRegex(ValueError,'date does not match'):
    jinx.propose({'kind':'reminder','fields':{'text':'work','when':tomorrow.isoformat()}})
