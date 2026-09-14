import jinx_test_support
import unittest
from unittest.mock import patch
import jinx,routing
class Selection(unittest.TestCase):
 def test_unknown_rejected(self):
  for mode in ('arbitrary-model',None,[],True):
   with self.assertRaises(ValueError):routing.validate_mode(mode)
 def test_local_selection_preserves_tools(self):
  self.assertEqual(routing.selected_local('local_fast','hello')[0],routing.FAST)
  self.assertEqual(routing.selected_local('local_fast','install Spotify')[0],routing.DEEP)
  self.assertEqual(routing.selected_local('local_fast','hello',vision=True)[0],routing.DEEP)
  self.assertEqual(routing.selected_local('local_deep','hello')[0],routing.DEEP)
 def test_local_never_calls_online(self):
  for mode in ('local_fast','local_deep'):
   with patch.dict(jinx.data,ai_mode=mode),patch.dict(jinx.status,voice_epoch=7,external_context=False),patch.object(jinx.cloud,'available') as available,patch.object(jinx.workspace,'metadata',return_value={}),patch.object(jinx,'fast_turn',return_value=('hello','')),patch.object(jinx,'run_agent_turn',return_value={'final_response':'deep'}):
    result=jinx.run_tiered_turn('hello','hello','',7,lambda t:None,{})
    self.assertIn('final_response',result);available.assert_not_called()
 def test_online_unavailable_stays_online(self):
  with patch.dict(jinx.data,ai_mode='online'),patch.object(jinx.cloud,'available',return_value=False),patch.object(jinx,'fast_turn') as fast,patch.object(jinx,'run_agent_turn') as deep:
   with self.assertRaisesRegex(RuntimeError,'unavailable'):jinx.run_tiered_turn('hello','hello','',7,lambda t:None,{})
   fast.assert_not_called();deep.assert_not_called()
 def test_auto_can_fallback(self):
  with patch.dict(jinx.data,ai_mode='auto'),patch.dict(jinx.status,voice_epoch=7,external_context=False),patch.object(jinx.cloud,'available',return_value=False),patch.object(jinx.workspace,'metadata',return_value={}),patch.object(jinx,'fast_turn',return_value=('hello','')):
   self.assertEqual(jinx.run_tiered_turn('hello','hello','',7,lambda t:None,{}),{'final_response':'hello'})
