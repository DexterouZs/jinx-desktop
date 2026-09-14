import jinx_test_support
import unittest,threading,time
from unittest.mock import patch,Mock
import jinx
from jinx_voice import VoiceCancelled

class BreezeSpeech(unittest.TestCase):
 def setUp(self):
  self.saved=jinx.status.copy();jinx.status.update(voice_epoch=5,timings={},speech=None)
 def tearDown(self):jinx.status.clear();jinx.status.update(self.saved)
 def test_sentence_order_and_completion(self):
  prepared=[];played=[]
  def synth(text,path,choice,speed,cancelled,on_chunk):
   prepared.append(text);on_chunk(b'\x00'*48000)
   return {'voice':choice,'engine':'test','fallback':''}
  def player(buffer,cancelled,started,progress,generated,ended):
   while not buffer.done:time.sleep(.001)
   if buffer.error:raise buffer.error
   generated();played.append(buffer.snapshot()[0]);ended()
  with patch.object(jinx.urllib.request,'urlopen',side_effect=OSError()),patch.object(jinx.voice,'synthesise',side_effect=synth),patch('streamed_audio.play',side_effect=player):
   jinx.breeze_say('First sentence. Second sentence.',5,1)
  self.assertEqual(prepared,['First sentence.','Second sentence.']);self.assertEqual(len(played),2)
  self.assertFalse(jinx.audio_lock.locked())
 def test_playback_failure_cancels_pending_synthesis(self):
  released=threading.Event()
  def synth(text,path,choice,speed,cancelled,on_chunk):
   try:
    while not cancelled():time.sleep(.005)
    raise VoiceCancelled()
   finally:released.set()
  with patch.object(jinx.urllib.request,'urlopen',side_effect=OSError()),patch.object(jinx.voice,'synthesise',side_effect=synth),patch('streamed_audio.play',side_effect=RuntimeError('Audio failed')):
   with self.assertRaisesRegex(RuntimeError,'Audio failed'):jinx.breeze_say('A sentence.',5,1)
  self.assertTrue(released.wait(1));self.assertFalse(jinx.audio_lock.locked())
 def test_existing_small_model_stays_resident(self):
  response=Mock();response.read.return_value='{"models":[{"name":"qwen3.5:4b","size_vram":4000000000}]}'
  with patch.object(jinx.urllib.request,'urlopen',return_value=response) as urlopen:jinx.breeze_say('',5,1)
  self.assertEqual(urlopen.call_count,1)

if __name__=='__main__':unittest.main()
