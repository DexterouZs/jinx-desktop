"""Whole chat pipeline with real draft state and simulated external application."""
import jinx_test_support
import unittest,tempfile
from pathlib import Path
from unittest.mock import Mock,patch
import jinx as j
from message_tools import Messages
from task_understanding import Tasks
from test_task_understanding import plan

class Conversations(unittest.TestCase):
 def test_missing_details_correction_readback_then_one_send(self):
  with tempfile.TemporaryDirectory() as d:
   messages=Messages(Path(d));messages.browser=Mock()
   messages.browser.status.return_value={'connected':True}
   messages.browser.stage.return_value=True
   messages.browser.send.return_value={'state':'sent','message':'Verified sent'}
   messages.save_contact('Alex','+12025550101')
   interpret=Mock(side_effect=[plan('message',recipient='Alex'),plan('message',recipient='Alex',text='Home at six'),plan('message',recipient='Alex',text='Home at seven')])
   music=Mock();music.intent.return_value=None
   admin=Mock();admin.app_catalog.return_value={}
   router=Tasks(interpret,messages,music,admin)
   with patch.object(j,'messages',messages),patch.object(j,'task_router',router),patch.object(j,'history',[]),patch.object(j,'data',{'pending':[],'memory':'','listening':False,'speak':False,'voice':'jinx_local','voice_speed':1,'ai_mode':'auto'}),patch.dict(j.status,{'messages':[],'voice_epoch':0,'busy':False,'ptt':False,'external_context':False}),patch.object(j,'say') as say,patch.object(j,'run_tiered_turn') as free_model:
    j.chat('Could you drop Alex a message?')
    self.assertIsNone(messages.draft)
    j.chat('Tell her home at six')
    self.assertEqual(messages.draft['text'],'Home at six')
    messages.browser.send.assert_not_called()
    j.chat('Actually make that seven')
    self.assertEqual(messages.draft['text'],'Home at seven')
    self.assertTrue(messages.armed)
    j.chat('Yes, send it.')
    self.assertEqual(messages.draft['state'],'sent')
    j.chat('Yes, send it.')
    messages.browser.send.assert_called_once()
    free_model.assert_not_called()
    self.assertTrue(say.called)
