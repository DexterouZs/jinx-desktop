import jinx_test_support  # Isolate state and memory before importing jinx.
import unittest, threading, time
from unittest.mock import patch
import jinx as a
import numpy as np
class Voice(unittest.TestCase):
 def setUp(self):
  self.saved=a.status.copy();self.olddata=a.data.copy()
  a.status.update(busy=False,ptt=False,suspended=False,voice_epoch=0,finish_record=False)
  a.data['listening']=False
 def tearDown(self):a.status.clear();a.status.update(self.saved);a.data.clear();a.data.update(self.olddata)
 def test_muted_click_needs_explicit_unmute(self):
  with patch.object(a,'mic_muted',return_value=True),patch.object(a,'cmd') as command:
   with self.assertRaises(ValueError):a.start_listen(False)
   command.assert_not_called();self.assertFalse(a.status['ptt'])
 def test_ptt_claims_microphone_before_thread_starts(self):
  with patch.object(a,'mic_muted',return_value=False),patch.object(a.threading,'Thread') as thread:
   a.data['listening']=True;a.start_listen()
   self.assertTrue(a.status['ptt']);self.assertEqual(thread.call_count,3)
 def test_second_click_finishes_recording(self):
  a.status['ptt']=True
  with patch.object(a.threading,'Thread') as thread:
   a.start_listen();self.assertTrue(a.status['finish_record']);thread.assert_not_called()
 def test_stop_invalidates_voice_and_cancels_generation(self):
  a.status.update(ptt=True,busy=True)
  with patch.object(a,'active_agent') as agent:
   a.stop_turn();agent.interrupt.assert_called_once_with(hard_cancel=True)
  self.assertFalse(a.status['ptt']);self.assertEqual(a.status['voice_epoch'],1)
 def test_record_stops_after_eight_quiet_blocks(self):
  class Stream:
   count=0
   def read(self,n):
    self.count+=1;return (np.ones(n,dtype='int16')*(600 if self.count<6 else 0)).tobytes(),False
  stream=Stream();a.status['ptt']=True
  chunks=a.record(stream)
  self.assertEqual(stream.count,13);self.assertEqual(len(chunks),13)
 def test_silent_microphone_times_out(self):
  class Stream:
   count=0
   def read(self,n):self.count+=1;return bytes(n*2),False
  stream=Stream();a.status['ptt']=True
  self.assertEqual(a.record(stream),[]);self.assertEqual(stream.count,50)
if __name__=='__main__':unittest.main()
