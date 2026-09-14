"""Adaptive latency and deliberate reasoning without touching deployed state."""
import jinx_test_support
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import jinx as j
import routing
from long_memory import LongMemory


class Adaptive(unittest.TestCase):
 def test_explicit_model_and_reasoning_requests(self):
  for text in ('think carefully about this', 'take your time', 'denk gründlich nach'):
   with self.subTest(text=text):
    self.assertTrue(routing.deliberate(text))
    self.assertEqual(routing.model_for(text)[0],routing.DEEP)

 def test_choosing_large_model_does_not_force_thinking(self):
  for text in ('Use 27B', 'use Qwen 3.8 27B', 'use the big model'):
   with self.subTest(text=text):
    self.assertEqual(routing.model_for(text)[0],routing.DEEP)
    self.assertFalse(routing.needs_thinking(text))
  self.assertTrue(routing.needs_thinking('Use 27B and think carefully'))
  self.assertTrue(routing.needs_thinking('Use 27B to diagnose the issue'))

 def test_quick_answers_stay_quick_after_previous_work(self):
  for text in ('What is a GPU?', 'Hello', 'What is a penguin?'):
   self.assertEqual(routing.model_for(text,history_turns=20,shared_document=True)[0],routing.FAST)
  self.assertEqual(routing.model_for('Summarise that document',shared_document=True)[0],routing.DEEP)
  self.assertFalse(routing.deliberate("Don't think carefully, just say hello"))
  self.assertFalse(routing.needs_thinking('Open Spotify'))
  self.assertTrue(routing.needs_thinking('hello',escalated=True))

 def test_first_ordinary_chunk_is_delivered_before_next_network_chunk(self):
  seen=[]
  class Response:
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def __iter__(self):
    yield json.dumps({'message':{'content':'Hello'}}).encode()
    assert seen==['Hello'], 'ordinary text waited for another network chunk'
    yield json.dumps({'done':True,'done_reason':'stop'}).encode()
  with patch.dict(j.status,voice_epoch=5),patch.object(j.urllib.request,'urlopen',return_value=Response()):
   self.assertEqual(j.fast_turn('hello',5,seen.append,[]),('Hello',''))

 def test_fragmented_handoff_never_reaches_speech(self):
  from test_tiering import FakeStream
  seen=[]
  with patch.dict(j.status,voice_epoch=5),patch.object(j.urllib.request,'urlopen',return_value=FakeStream(['H','AN','DO','FF','.'])):
   reply,reason=j.fast_turn('hello',5,seen.append,[])
  self.assertTrue(reason)
  self.assertEqual(seen,[])

 def test_reasoning_is_reset_on_reused_agent(self):
  agent=Mock()
  agent.run_conversation.return_value={'final_response':'Done.'}
  with patch.object(j,'get_agent',return_value=agent),patch.object(j.voice.breeze,'release'),patch.dict(j.status,voice_epoch=9):
   for deliberate in (True,False):
    j.status['deliberate']=deliberate
    j.run_agent_turn('synthetic test','',9,lambda text:None)
    self.assertEqual(agent.reasoning_config['enabled'],deliberate)
    self.assertEqual(agent.request_overrides['extra_body']['think'],deliberate)
    self.assertEqual(agent.request_overrides['reasoning_effort'],'medium' if deliberate else 'none')
    self.assertIsNone(j.active_agent)

 def test_fast_memory_does_not_load_embedding_model(self):
  embed=Mock(side_effect=AssertionError('should not load another model'))
  with tempfile.TemporaryDirectory() as directory:
   memory=LongMemory(Path(directory)/'memory.db',embed=embed)
   memory.add('fact','David likes tea',pinned=True,semantic=False)
   memory.record_episode('I visited Edinburgh','A fine city.')
   result=memory.prompt_block('Edinburgh',semantic=False)
   self.assertIn('David likes tea',result)
   self.assertIn('Edinburgh',result)
   embed.assert_not_called()

if __name__=='__main__':unittest.main()
