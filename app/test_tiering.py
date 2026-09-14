import jinx_test_support  # Isolate state and memory before importing jinx.
import json,unittest
from unittest.mock import patch
import jinx as j
import routing


class FakeStream:
 """Stands in for a streaming ollama response."""
 def __init__(self,chunks,done_reason='stop'):
  rows=[{'message':{'content':c}} for c in chunks]
  rows.append({'done':True,'done_reason':done_reason})
  self.lines=[json.dumps(r).encode()+b'\n' for r in rows]
 def __enter__(self):return self
 def __exit__(self,*a):return False
 def __iter__(self):return iter(self.lines)
 def close(self):pass


def stream(chunks,done_reason='stop'):
 return lambda req,timeout=None:FakeStream(chunks,done_reason)


class FastTurn(unittest.TestCase):
 def setUp(self):
  j.status['voice_epoch']=0;j.status['partial']=''

 def test_ordinary_reply_is_returned_and_streamed(self):
  seen=[]
  with patch.object(j.urllib.request,'urlopen',stream(['The kitchen ','lamp is on, and has been all afternoon.'])):
   reply,escalate=j.fast_turn('are the lights on',0,seen.append,[])
  self.assertEqual(reply,'The kitchen lamp is on, and has been all afternoon.')
  self.assertEqual(escalate,'')
  self.assertIn('kitchen',''.join(seen))

 def test_short_reply_still_reaches_the_caller(self):
  # Short replies are withheld until HANDOFF is ruled out; they must still be
  # delivered once the model finishes.
  seen=[]
  with patch.object(j.urllib.request,'urlopen',stream(['On.'])):
   reply,escalate=j.fast_turn('lights?',0,seen.append,[])
  self.assertEqual(reply,'On.')
  self.assertEqual(escalate,'')
  self.assertEqual(''.join(seen),'On.')

 def test_handoff_is_never_shown_to_the_user(self):
  seen=[]
  with patch.object(j.urllib.request,'urlopen',stream(['HANDOFF'])):
   reply,escalate=j.fast_turn('write me an essay',0,seen.append,[])
  self.assertTrue(escalate)
  self.assertEqual(''.join(seen),'',"HANDOFF must not be streamed to David")

 def test_backend_failure_escalates_instead_of_raising(self):
  def boom(req,timeout=None):raise OSError('connection refused')
  with patch.object(j.urllib.request,'urlopen',boom):
   reply,escalate=j.fast_turn('hello',0,lambda v:None,[])
  self.assertEqual(reply,'')
  self.assertTrue(escalate)

 def test_truncated_reply_escalates(self):
  with patch.object(j.urllib.request,'urlopen',stream(['a rambling answer that ran on'],done_reason='length')):
   _,escalate=j.fast_turn('explain',0,lambda v:None,[])
  self.assertIn('token cap',escalate)

 def test_cancellation_is_reported_not_answered(self):
  def cancel(req,timeout=None):
   j.status['voice_epoch']=1
   return FakeStream(['partial'])
  with patch.object(j.urllib.request,'urlopen',cancel):
   reply,escalate=j.fast_turn('hello',0,lambda v:None,[])
  self.assertEqual(escalate,'interrupted')


class Escalation(unittest.TestCase):
 def setUp(self):
  j.status['voice_epoch']=0;j.status['partial']='';j.status.pop('tier',None)
  j.status.pop('deep_loaded',None);j.status.pop('external_context',None)
  j.history.clear()

 def run_turn(self,text,fast_chunks=None,fast_fails=False):
  calls=[]
  def deep(request,prompt,epoch,delta):
   calls.append(request);return {'final_response':'deep answer'}
  def fast(req,timeout=None):
   if fast_fails:raise OSError('down')
   return FakeStream(fast_chunks or ['fine'])
  with patch.object(j,'run_agent_turn',deep),patch.object(j.urllib.request,'urlopen',fast):
   result=j.run_tiered_turn(text,text,'PROMPT',0,lambda v:None,{})
  return result,calls

 def test_everyday_turn_never_touches_the_large_model(self):
  result,deep_calls=self.run_turn('are the lights on',['They are on.'])
  self.assertEqual(result['final_response'],'They are on.')
  self.assertEqual(deep_calls,[])
  self.assertEqual(j.status['tier']['served_by'],routing.FAST)
  self.assertFalse(j.status['tier']['escalated'])

 def test_authoring_goes_straight_to_the_large_model(self):
  result,deep_calls=self.run_turn('Write me an essay about lamps')
  self.assertEqual(result['final_response'],'deep answer')
  self.assertEqual(len(deep_calls),1)
  self.assertFalse(j.status['tier']['escalated'])

 def test_handoff_escalates_exactly_once(self):
  result,deep_calls=self.run_turn('are the lights on',['HANDOFF'])
  self.assertEqual(result['final_response'],'deep answer')
  self.assertEqual(len(deep_calls),1,'the 27B must run once, not repeatedly')
  self.assertTrue(j.status['tier']['escalated'])

 def test_failing_fast_model_escalates_exactly_once(self):
  result,deep_calls=self.run_turn('are the lights on',fast_fails=True)
  self.assertEqual(result['final_response'],'deep answer')
  self.assertEqual(len(deep_calls),1)

 def test_silent_fast_model_escalates_rather_than_answering_nothing(self):
  result,deep_calls=self.run_turn('are the lights on',[''])
  self.assertEqual(result['final_response'],'deep answer')
  self.assertEqual(len(deep_calls),1)

 def test_escalation_clears_the_abandoned_fast_text(self):
  j.status['partial']='half a sentence'
  self.run_turn('are the lights on',['HANDOFF'])
  self.assertEqual(j.status['partial'],'')

 def test_escalation_marks_the_deep_model_for_release(self):
  self.run_turn('are the lights on',['HANDOFF'])
  self.assertTrue(j.status.get('deep_loaded'))

 def test_a_turn_cannot_loop_between_tiers(self):
  # Even when the deep model itself replies with the control token, nothing
  # routes back to the fast model.
  calls=[]
  def deep(request,prompt,epoch,delta):
   calls.append(request);return {'final_response':'HANDOFF'}
  with patch.object(j,'run_agent_turn',deep),patch.object(j.urllib.request,'urlopen',stream(['HANDOFF'])):
   result=j.run_tiered_turn('are the lights on','req','PROMPT',0,lambda v:None,{})
  self.assertEqual(len(calls),1)
  self.assertEqual(result['final_response'],'HANDOFF')


class Residency(unittest.TestCase):
 def test_release_is_a_no_op_when_the_deep_model_was_never_used(self):
  j.status.pop('deep_loaded',None)
  with patch.object(j.urllib.request,'urlopen') as opened:
   j.release_deep_model()
  opened.assert_not_called()

 def test_release_unloads_the_deep_model_once(self):
  j.status['deep_loaded']=True
  sent=[]
  def capture(req,timeout=None):
   sent.append(json.loads(req.data.decode()));return FakeStream([])
  with patch.object(j.urllib.request,'urlopen',capture):
   j.release_deep_model()
   j.release_deep_model()   # second call must do nothing
  self.assertEqual(len(sent),1)
  self.assertEqual(sent[0]['model'],routing.DEEP)
  self.assertEqual(sent[0]['keep_alive'],0)

 def test_warming_pins_the_fast_model_not_the_large_one(self):
  sent=[]
  def capture(req,timeout=None):
   sent.append(json.loads(req.data.decode()));return FakeStream([])
  with patch.object(j.urllib.request,'urlopen',capture),patch.dict(j.data,ai_mode='local_fast'):
   j.warm_model()
  self.assertEqual(sent[0]['model'],routing.FAST)
  self.assertEqual(sent[0]['keep_alive'],routing.KEEP_ALIVE_FAST)

 def test_warming_respects_explicit_large_model_even_when_cloud_available(self):
  sent=[]
  def capture(req,timeout=None):
   sent.append(json.loads(req.data.decode()));return FakeStream([])
  with patch.object(j.urllib.request,'urlopen',capture),patch.object(j.cloud,'available',return_value=True),patch.object(j.voice.breeze,'release') as release,patch.dict(j.data,ai_mode='local_deep'),patch.dict(j.status,deep_loaded=False):
   j.warm_model()
   self.assertTrue(j.status['deep_loaded'])
  release.assert_called_once()
  self.assertEqual(len(sent),1)
  self.assertEqual(sent[0]['model'],routing.DEEP)
  self.assertEqual(sent[0]['options']['num_ctx'],65536)
  self.assertEqual(sent[0]['keep_alive'],routing.KEEP_ALIVE_FAST)

 def test_online_mode_never_warms_a_local_model(self):
  with patch.object(j.urllib.request,'urlopen') as call,patch.dict(j.data,ai_mode='online'):
   j.warm_model()
  call.assert_not_called()

 def test_stopping_during_large_model_warm_releases_it_after_loading(self):
  def finish(req,timeout=None):
   j.status['voice_epoch']+=1
   return FakeStream([])
  with patch.object(j.urllib.request,'urlopen',finish),patch.object(j.voice.breeze,'release'),patch.object(j,'release_deep_model') as release,patch.dict(j.data,ai_mode='local_deep'),patch.dict(j.status,voice_epoch=12,busy=False,conversation=False,ptt=False,deep_loaded=False):
   j.warm_model()
   release.assert_called_once()

 def test_large_model_does_not_race_breeze_preloading(self):
  with patch.object(j.voice,'warm') as warm,patch.dict(j.data,ai_mode='local_deep',voice='breeze_tts2',speak=True):
   j.warm_selected_voice()
  warm.assert_not_called()


class VoiceSelection(unittest.TestCase):
 def test_confirmations_and_conversation_keep_the_selected_voice(self):
  self.assertEqual(j.pick_voice('Kitchen lamp on','jinx_local'),'jinx_local')
  self.assertEqual(j.pick_voice('It has been on since about four, and the hall one too.','jinx_local'),'jinx_local')

 def test_the_recorded_greeting_keeps_its_cached_voice(self):
  # Routing this to Piper would discard the 0.01s prerecorded reply.
  import quick_speech
  self.assertEqual(j.pick_voice(quick_speech.GREETING,'jinx_local'),'jinx_local')

 def test_a_chosen_voice_is_respected_for_conversation(self):
  self.assertEqual(j.pick_voice('A longer conversational reply that goes on a while.','kokoro_emma'),'kokoro_emma')




class StopBehaviour(unittest.TestCase):
 def test_a_stop_with_nothing_resident_starts_no_work(self):
  # An ordinary stop must not spawn threads; the second click that ends a
  # conversation relies on this.
  j.status.pop('deep_loaded',None)
  with patch.object(j.threading,'Thread') as thread:
   j.stop_turn()
  thread.assert_not_called()

 def test_a_stop_after_deep_use_releases_the_memory(self):
  j.status['deep_loaded']=True
  with patch.object(j.threading,'Thread') as thread:
   j.stop_turn()
  thread.assert_called_once()
  self.assertIs(thread.call_args.kwargs['target'],j.release_deep_model)



class FastPathContext(unittest.TestCase):
 def setUp(self):
  j.status['voice_epoch']=0;j.status['partial']='';j.history.clear()

 def test_recent_turns_are_carried_into_the_fast_model(self):
  # A fast turn bypasses the agent, so it must supply conversation context
  # itself or Jinx forgets the previous exchange mid-chat.
  j.history.extend([{'role':'user','content':'Tell me one fact about Saturn.'},
                    {'role':'assistant','content':'It would float in water.'}])
  sent={}
  def capture(req,timeout=None):
   sent.update(json.loads(req.data.decode()));return FakeStream(['Rings, mostly ice.'])
  with patch.object(j.urllib.request,'urlopen',capture):
   j.run_tiered_turn('And its rings?','And its rings?','PROMPT',0,lambda v:None,{})
  roles=[m['role'] for m in sent['messages']]
  contents=' '.join(m['content'] for m in sent['messages'])
  self.assertEqual(roles[0],'system')
  self.assertIn('Saturn',contents,'prior turns must reach the fast model')
  self.assertIn('float in water',contents)
  self.assertEqual(sent['messages'][-1]['content'],'And its rings?')

 def test_the_fast_model_gets_the_short_persona_not_the_full_one(self):
  sent={}
  def capture(req,timeout=None):
   sent.update(json.loads(req.data.decode()));return FakeStream(['Fine.'])
  with patch.object(j.urllib.request,'urlopen',capture):
   j.run_tiered_turn('how are you','how are you','THE FULL PERSONA',0,lambda v:None,{})
  self.assertTrue(sent['messages'][0]['content'].startswith(routing.FAST_PERSONA))
  self.assertIn('British English',sent['messages'][0]['content'])
  self.assertNotIn('THE FULL PERSONA',sent['messages'][0]['content'])



class ReleaseRace(unittest.TestCase):
 """Regression: unloading the 27B while a request was in flight wedged ollama
 in "Stopping..." and left status busy with phase "Stopping" until restart."""

 def tearDown(self):
  j.status['busy']=False;j.active_agent=None;j.status.pop('deep_loaded',None)

 def test_never_unloads_while_a_turn_is_in_flight(self):
  j.status['deep_loaded']=True;j.status['busy']=True
  with patch.object(j.urllib.request,'urlopen') as opened, patch.object(j.time,'sleep'):
   j.release_deep_model(settle=0.4)
  opened.assert_not_called()

 def test_a_skipped_release_is_retried_on_the_next_stop(self):
  j.status['deep_loaded']=True;j.status['busy']=True
  with patch.object(j.urllib.request,'urlopen'), patch.object(j.time,'sleep'):
   j.release_deep_model(settle=0.4)
  self.assertTrue(j.status.get('deep_loaded'),'the flag must survive so a later stop retries')

 def test_never_unloads_while_an_agent_is_still_active(self):
  j.status['deep_loaded']=True;j.status['busy']=False;j.active_agent=object()
  with patch.object(j.urllib.request,'urlopen') as opened, patch.object(j.time,'sleep'):
   j.release_deep_model(settle=0.4)
  opened.assert_not_called()

 def test_unloads_once_the_turn_has_finished(self):
  j.status['deep_loaded']=True;j.status['busy']=False;j.active_agent=None
  sent=[]
  def capture(req,timeout=None):
   sent.append(json.loads(req.data.decode()));return FakeStream([])
  with patch.object(j.urllib.request,'urlopen',capture):
   j.release_deep_model(settle=5)
  self.assertEqual(len(sent),1)
  self.assertEqual(sent[0]['keep_alive'],0)

 def test_release_waits_rather_than_giving_up_immediately(self):
  # busy clears part way through the wait; the release must still happen.
  j.status['deep_loaded']=True;j.status['busy']=True;j.active_agent=None
  ticks=[0]
  def tick(_):
   ticks[0]+=1
   if ticks[0]>=3:j.status['busy']=False
  sent=[]
  def capture(req,timeout=None):
   sent.append(1);return FakeStream([])
  with patch.object(j.time,'sleep',tick), patch.object(j.urllib.request,'urlopen',capture):
   j.release_deep_model(settle=5)
  self.assertEqual(len(sent),1,'must unload after the turn ends, not abandon it')

if __name__=='__main__':unittest.main()
