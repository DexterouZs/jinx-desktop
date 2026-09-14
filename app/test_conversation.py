import jinx_test_support  # Isolate state and memory before importing jinx.
import copy,unittest
from contextlib import ExitStack
from unittest.mock import patch,MagicMock
import numpy as np
import jinx as a
from conversation_audio import record_utterance

class Conversation(unittest.TestCase):
 def setUp(self):
  self.status=copy.deepcopy(a.status);self.data=copy.deepcopy(a.data);self.history=a.history[:]
  a.history.clear();a.status.update(conversation=True,busy=False,ptt=True,voice_epoch=0,suspended=False,error='',messages=[])
  a.data['listening']=False
  self.open=False;self.captures=0;self.spoken=[]
 def tearDown(self):
  a.status.clear();a.status.update(self.status);a.data.clear();a.data.update(self.data);a.history[:]=self.history
  self.assertFalse(a.conversation_gate.locked())
 def run_session(self,record,transcribe=None,say=None):
  owner=self
  class Stream:
   def __enter__(self):owner.assertFalse(owner.open);owner.open=True;return self
   def __exit__(self,*args):owner.open=False
  def capture(*args):
   self.assertTrue(self.open);self.captures+=1;return record(*args)
  def hear(_):self.assertFalse(self.open);return 'Tell me one fact about Saturn.'
  def speak(text,**kwargs):self.assertFalse(self.open);self.spoken.append(text)
  agent=MagicMock();agent.run_conversation.return_value={'final_response':'Hello David.'}
  with ExitStack() as stack:
   stack.enter_context(patch('sounddevice.RawInputStream',return_value=Stream()))
   stack.enter_context(patch('conversation_audio.record_utterance',side_effect=capture))
   stack.enter_context(patch.object(a,'transcribe',side_effect=transcribe or hear))
   stack.enter_context(patch.object(a,'say',side_effect=say or speak))
   stack.enter_context(patch.object(a,'get_agent',return_value=agent))
   # These tests are about the conversation loop and the context handed to the
   # agent, not about tier selection. Force the agent path so they stay
   # deterministic and make no live model call; tiering has its own tests.
   stack.enter_context(patch.object(a.routing,'model_for',return_value=(a.routing.DEEP,'forced by test')))
   stack.enter_context(patch.object(a.admin,'preflight_request',return_value={}))
   stack.enter_context(patch.object(a.admin,'knowledge',return_value={'notes':''}))
   stack.enter_context(patch.object(a.time,'sleep'))
   a.conversation_gate.acquire();a.conversation_loop(0)
  self.assertFalse(self.open);self.assertFalse(a.status['conversation']);self.assertFalse(a.status['ptt'])
  return agent
 def test_two_turns_relisten_and_keep_context_until_click(self):
  def record(*args):
   if self.captures==3:a.stop_turn();return []
   return [np.zeros(1600,dtype='int16')]
  agent=self.run_session(record)
  self.assertEqual(self.captures,3);self.assertEqual(len(self.spoken),2)
  self.assertEqual(agent.run_conversation.call_args_list[1].kwargs['conversation_history'][0]['content'],'Tell me one fact about Saturn.')
  self.assertEqual(a.status['error'],'')
 def test_stop_during_reply_does_not_reopen_microphone(self):
  def say(text,**kwargs):self.assertFalse(self.open);a.stop_turn()
  self.run_session(lambda *args:[np.zeros(1600,dtype='int16')],say=say)
  self.assertEqual(self.captures,1)
 def test_stop_during_transcription_discards_text(self):
  def transcribe(_):a.stop_turn();return 'Do not act on this cancelled request'
  agent=self.run_session(lambda *args:[np.zeros(1600,dtype='int16')],transcribe=transcribe)
  agent.run_conversation.assert_not_called();self.assertEqual(self.captures,1)
 def test_muted_start_does_not_leave_session_or_gate_claimed(self):
  a.status.update(conversation=False,ptt=False)
  with patch.object(a,'mic_muted',return_value=True):
   with self.assertRaises(ValueError):a.start_conversation()
  self.assertFalse(a.status['conversation']);self.assertFalse(a.conversation_gate.locked())
 def test_second_start_click_ends_session(self):
  with patch.object(a.threading,'Thread') as thread:a.start_conversation();thread.assert_not_called()
  self.assertFalse(a.status['conversation'])

class Endpointer(unittest.TestCase):
 def test_silence_waits_beyond_old_five_second_timeout_until_stop(self):
  class Stream:
   n=0
   def read(self,n):self.n+=1;return bytes(n*2),False
  stream=Stream();levels=[]
  result=record_utterance(stream,lambda:stream.n<90,levels.append)
  self.assertEqual(stream.n,90);self.assertEqual(result,[]);self.assertEqual(levels[-1],0)
 def test_short_pause_is_inside_one_turn(self):
  # Five voiced blocks, a 600 ms pause, more speech, then a 1.1 second endpoint.
  flags=iter([True]*5+[False]*6+[True]*5+[False]*11)
  class Stream:
   n=0;voiced=False
   def read(self,n):self.n+=1;self.voiced=next(flags);return (np.ones(n,dtype='int16')*600).tobytes(),False
  stream=Stream();vad=MagicMock();vad.probability.side_effect=lambda *_:.99 if stream.voiced else 0
  with patch('conversation_audio.SpeechDetector',return_value=vad):
   result=record_utterance(stream,lambda:True,lambda _:None)
  self.assertEqual(stream.n,25);self.assertEqual(len(result),25)

if __name__=='__main__':unittest.main()
