import jinx_test_support
import unittest
import numpy as np
from unittest.mock import patch
import jinx
from npu_speech import NpuUnavailable,SpeechCancelled
class TranscriptionIntegration(unittest.TestCase):
 def setUp(self):
  self.samples=[np.zeros(16000,dtype='int16')];self.old=jinx.data.get('speech_engine');self.epoch=jinx.status['voice_epoch'];self.suspended=jinx.status['suspended'];jinx.status['suspended']=False
 def tearDown(self):
  if self.old is None:jinx.data.pop('speech_engine',None)
  else:jinx.data['speech_engine']=self.old
  jinx.status['voice_epoch']=self.epoch;jinx.status['suspended']=self.suspended
 def test_npu_success_skips_cpu(self):
  jinx.data['speech_engine']='npu'
  with patch.object(jinx.npu_speech,'transcribe',return_value='Hello David'),patch.object(jinx,'cmd') as cpu:
   self.assertEqual(jinx.transcribe(self.samples),'Hello David');cpu.assert_not_called()
 def test_npu_failure_uses_existing_cpu(self):
  jinx.data['speech_engine']='npu'
  with patch.object(jinx.npu_speech,'transcribe',side_effect=NpuUnavailable()),patch.object(jinx,'cmd',return_value='Hello David') as cpu:
   self.assertEqual(jinx.transcribe(self.samples),'Hello David');self.assertEqual(cpu.call_args.args[0][0],'whisper-cli');self.assertIn('CPU',jinx.status['speech_notice'])
 def test_cpu_choice_skips_npu(self):
  jinx.data['speech_engine']='cpu'
  with patch.object(jinx.npu_speech,'transcribe') as npu,patch.object(jinx,'cmd',return_value='Hello David'):
   self.assertEqual(jinx.transcribe(self.samples),'Hello David');npu.assert_not_called()
 def test_cancellation_never_falls_back_and_executes_nothing(self):
  jinx.data['speech_engine']='npu'
  with patch.object(jinx.npu_speech,'transcribe',side_effect=SpeechCancelled()),patch.object(jinx,'cmd') as cpu:
   self.assertEqual(jinx.transcribe(self.samples),'');cpu.assert_not_called()
