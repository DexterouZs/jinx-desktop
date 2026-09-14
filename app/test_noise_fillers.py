import unittest,tempfile,json,threading,time
from pathlib import Path
from unittest.mock import patch,MagicMock
import numpy as np
from conversation_audio import clean_transcript,record_utterance
from thinking_sounds import ThinkingSounds
class Noise(unittest.TestCase):
 def test_non_speech_markers_are_not_requests(self):
  for text in ['[BLANK_AUDIO]',' [Music] ','(noise)','...','[silence] [BLANK_AUDIO]']:
   self.assertEqual(clean_transcript(text),'')
  self.assertEqual(clean_transcript('Yes.'),'Yes.')
  self.assertEqual(clean_transcript('Thanks for watching.'),'Thanks for watching.')
 def test_single_loud_impulse_does_not_start_a_turn(self):
  class Stream:
   n=0
   def read(self,n):self.n+=1;return (np.ones(n,dtype='int16')*(14000 if self.n==10 else 0)).tobytes(),False
  stream=Stream();detector=MagicMock();detector.probability.side_effect=lambda _:.99 if stream.n==10 else 0
  with patch('conversation_audio.SpeechDetector',return_value=detector):
   self.assertEqual(record_utterance(stream,lambda:stream.n<40,lambda _:None),[])
 def test_fan_like_hum_and_hiss_not_speech_with_real_detector(self):
  rng=np.random.default_rng(9)
  class Stream:
   n=0
   def read(self,n):
    t=(np.arange(n)+self.n*n)/16000;self.n+=1
    a=650*np.sin(2*np.pi*120*t)+300*np.sin(2*np.pi*240*t)+rng.normal(0,180,n)
    return a.astype('int16').tobytes(),False
  stream=Stream();self.assertEqual(record_utterance(stream,lambda:stream.n<80,lambda _:None),[])
class Fillers(unittest.TestCase):
 def make_bank(self,p):
  entries=[]
  for i in range(10):
   name=f'{i}.wav';(p/name).touch();entries.append({'file':name,'text':str(i)})
  (p/'manifest.json').write_text(json.dumps(entries));return ThinkingSounds(p)
 def test_ten_distinct_choices_before_repeat(self):
  with tempfile.TemporaryDirectory() as directory:
   bank=self.make_bank(Path(directory));choices=[bank.choose()[1] for _ in range(10)]
   self.assertEqual(len(set(choices)),10);self.assertNotEqual(bank.choose()[1],choices[-1])
 def test_fast_answer_cancels_pending_filler(self):
  with tempfile.TemporaryDirectory() as directory:
   play=MagicMock();session=self.make_bank(Path(directory)).begin(play,lambda:False,delay=10)
   session.stop();play.assert_not_called();self.assertFalse(session.thread.is_alive())
 def test_ready_answer_interrupts_an_active_filler(self):
  with tempfile.TemporaryDirectory() as directory:
   started=threading.Event()
   def play(path,text,stopped):
    started.set()
    while not stopped():time.sleep(.005)
   session=self.make_bank(Path(directory)).begin(play,lambda:False,delay=0)
   self.assertTrue(started.wait(1));start=time.monotonic();session.stop()
   self.assertLess(time.monotonic()-start,.2);self.assertFalse(session.thread.is_alive())
if __name__=='__main__':unittest.main()
