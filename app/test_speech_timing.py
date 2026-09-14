import threading,unittest
from unittest.mock import Mock
import numpy as np
from speech_timing import envelope
from speech_prefetch import FirstSpeech
from workbench import speech_chunks

class SpeechTiming(unittest.TestCase):
 def test_waveform_preserves_padding_and_internal_pause(self):
  rate=24000;t=np.arange(rate//2)/rate
  tone=(6000*np.sin(2*np.pi*220*t)).astype('int16');silence=np.zeros(rate//2,dtype='int16')
  e=envelope(np.concatenate([silence,tone,silence,tone,silence]),rate)
  self.assertEqual(e['step_ms'],20)
  for start in [0,50,100]:self.assertEqual(max(e['levels'][start:start+25]),0)
  self.assertGreater(min(e['levels'][25:50]),.8)
 def test_quiet_audio_never_becomes_an_open_mouth(self):
  self.assertEqual(max(envelope(np.ones(24000)*3,24000)['levels']),0)
  self.assertEqual(envelope([],24000)['levels'],[])
 def test_envelope_is_bounded_and_stereo_safe(self):
  e=envelope(np.ones((24000*100,2))*2000,24000)
  self.assertLessEqual(len(e['levels']),2000)
  self.assertTrue(all(0<=x<=1 for x in e['levels']))
 def test_first_chunk_starts_short_and_keeps_all_words(self):
  s='Good morning David. '+('These are all the words that must be read back exactly. '*8).strip()
  chunks=speech_chunks(s)
  self.assertEqual(chunks[0],'Good morning David.')
  self.assertEqual(' '.join(chunks),s)
  self.assertTrue(all(len(x)<=150 for x in chunks))
 def test_prefetch_only_prepares_one_completed_chunk(self):
  voice=Mock();p=FirstSpeech(voice,'jinx_local',.9,lambda:False)
  p.feed('Hello David');self.assertIsNone(p.thread)
  p.feed('Hello David. The next sentence');p.thread.join(2)
  p.feed('Hello David. The next sentence is now complete.')
  self.assertEqual(voice.synthesise.call_count,1)
  self.assertEqual(voice.synthesise.call_args.args[0],'Hello David.')
  self.assertFalse(voice.synthesise.call_args.args[1].exists())
  voice.play.assert_not_called()
 def test_cancelled_prefetch_does_not_start(self):
  voice=Mock();p=FirstSpeech(voice,'jinx_local',.9,lambda:True)
  p.feed('Hello. More text here.');self.assertIsNone(p.thread);voice.synthesise.assert_not_called()

class EarlyPreparation(unittest.TestCase):
 def test_finished_short_sentence_is_prepared_before_another_token(self):
  voice=Mock();p=FirstSpeech(voice,'jinx_local',1,lambda:False)
  p.feed('I can help with that.');p.thread.join(2)
  self.assertEqual(voice.synthesise.call_args.args[0],'I can help with that.')
  voice.play.assert_not_called()
 def test_partial_words_do_not_trigger_synthesis(self):
  p=FirstSpeech(Mock(),'jinx_local',1,lambda:False)
  for text in ['', 'I can help', 'The value is 3.1']:p.feed(text)
  self.assertIsNone(p.thread)

if __name__=='__main__':unittest.main()
