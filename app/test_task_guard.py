import jinx_test_support
import json
import threading
import unittest
from unittest.mock import Mock, patch
import jinx as j
import jinx_skills
from task_guard import TaskGuard, failed, read_only


class Budget(unittest.TestCase):
 def test_duplicate_write_is_never_dispatched_twice(self):
  g=TaskGuard();args={'action':'open','app':'firefox'}
  self.assertIsNone(g.before('jinx_apps',args));g.after('jinx_apps',{'status':'launch_requested'})
  self.assertTrue(g.before('jinx_apps',args)['task_stopped'])
  self.assertEqual(g.calls,1)
  self.assertTrue(g.before('jinx_shell',{'command':'firefox'})['task_stopped'])

 def test_read_verify_allowed_but_third_read_stops(self):
  g=TaskGuard()
  for _ in range(2):self.assertIsNone(g.before('jinx_music',{'action':'status'}))
  self.assertTrue(g.before('jinx_music',{'action':'status'})['task_stopped'])

 def test_same_shell_with_other_timeout_is_duplicate(self):
  g=TaskGuard();g.before('jinx_shell',{'command':' touch example ','timeout':5})
  self.assertTrue(g.before('jinx_shell',{'timeout':30,'command':'touch example'})['task_stopped'])

 def test_simple_shell_check_can_verify_before_and_after(self):
  g=TaskGuard()
  for _ in range(2):self.assertIsNone(g.before('jinx_shell',{'command':'free -m'}))
  self.assertTrue(g.before('jinx_shell',{'command':'free -m'})['task_stopped'])
  for command in ('free -m; touch example','free $(touch example)','free > example'):
   self.assertFalse(read_only('jinx_shell',{'command':command}))

 def test_total_budget_across_different_tools(self):
  g=TaskGuard(max_calls=2)
  self.assertIsNone(g.before('jinx_system',{'topic':'audio'}))
  self.assertIsNone(g.before('jinx_logs',{'topic':'audio'}))
  self.assertTrue(g.before('jinx_system',{'topic':'network'})['task_stopped'])

 def test_changed_arguments_do_not_allow_infinite_failures(self):
  g=TaskGuard()
  for i in range(3):
   self.assertIsNone(g.before('jinx_web_read',{'url':f'https://example.org/{i}'}))
   g.after('jinx_web_read',{'error':'unreachable'})
  self.assertIn('failed three times',g.reason)
  self.assertTrue(g.before('jinx_web_search',{'query':'other'})['task_stopped'])

 def test_permission_denial_stops_without_bypass(self):
  g=TaskGuard();g.before('jinx_shell',{'command':'sudo example'})
  g.after('jinx_shell',{'ok':False,'denied':'Privilege escalation unavailable'})
  self.assertIn('denied',g.reason)

 def test_finite_corrected_attempt_can_succeed(self):
  g=TaskGuard()
  g.before('jinx_web_read',{'url':'https://example.org/wrong'});g.after('jinx_web_read',{'error':'404'})
  self.assertIsNone(g.before('jinx_web_read',{'url':'https://example.org/right'}))
  g.after('jinx_web_read',{'text':'page'})
  self.assertFalse(g.reason)

 def test_deadline_and_new_request_reset(self):
  clock=Mock(return_value=0);g=TaskGuard(seconds=3,clock=clock)
  clock.return_value=4
  self.assertTrue(g.before('jinx_apps',{'action':'open','app':'firefox'})['task_stopped'])
  self.assertIsNone(TaskGuard().before('jinx_apps',{'action':'open','app':'firefox'}))

 def test_concurrent_duplicate_reservation(self):
  g=TaskGuard();results=[]
  threads=[threading.Thread(target=lambda:results.append(g.before('jinx_browser',{}))) for _ in range(8)]
  for t in threads:t.start()
  for t in threads:t.join()
  self.assertEqual(results.count(None),1)

 def test_progress_does_not_store_arguments_or_tool_output(self):
  g=TaskGuard();g.before('jinx_shell',{'command':'echo private-example'});g.after('jinx_shell',{'ok':False,'stderr':'private-example'})
  self.assertNotIn('private-example',json.dumps(g.snapshot()))

 def test_failures_include_uncertain_side_effects(self):
  for result in ({'status':'uncertain'},{'status':'unconfirmed'},{'error':'failed'},{'exit_code':5},{'ok':False}):self.assertTrue(failed(result))
  self.assertFalse(failed({'status':'launch_requested'}))


class Integration(unittest.TestCase):
 def test_stuck_agent_response_replaced_and_scope_cleared(self):
  def run(*args):
   j.task_guard.stop('the assistant tried to repeat the same action')
   return {'final_response':'Everything is done!'}
  with patch.object(j,'_run_tiered_turn',side_effect=run),patch.dict(j.status,voice_epoch=7):
   result=j.run_tiered_turn('test','test','',7,lambda x:None,{})
  self.assertTrue(result['task_stopped']);self.assertNotIn('Everything is done',result['final_response'])
  self.assertIsNone(j.task_guard)

 def test_success_remains_success(self):
  with patch.object(j,'_run_tiered_turn',return_value={'final_response':'Checked.'}):
   result=j.run_tiered_turn('test','test','',7,lambda x:None,{})
  self.assertEqual(result,{'final_response':'Checked.'});self.assertIsNone(j.task_guard)

 def test_exception_cleans_guard_and_deadline(self):
  with patch.object(j,'_run_tiered_turn',side_effect=ValueError('unexpected')):
   with self.assertRaises(ValueError):j.run_tiered_turn('test','test','',7,lambda x:None,{})
  self.assertIsNone(j.task_guard)

 def test_old_watchdog_cannot_interrupt_new_agent(self):
  old,new=TaskGuard(),TaskGuard();agent=Mock()
  with patch.object(j,'task_guard',new),patch.object(j,'active_agent',agent):j.stop_guarded_agent(old)
  agent.interrupt.assert_not_called()

 def test_real_registry_wrapper_blocks_duplicates(self):
  # Instantiate the real agent/tool registry without model inference.
  config=j.STATE/'hermes'/'config.yaml';config.parent.mkdir(parents=True,exist_ok=True)
  config.write_text('tools:\n  tool_search:\n    enabled: off\n')
  from tools.registry import registry
  previous=j.agent
  fake=Mock(return_value={'status':'launch_requested'})
  with patch.object(j,'agent',None),patch.object(j,'guarded_apps',fake):
   agent=j.get_agent();g=TaskGuard()
   with patch.object(j,'task_guard',g),patch.object(j,'active_agent',Mock()):
    first=json.loads(registry.dispatch('jinx_apps',{'action':'open','app':'firefox'}))
    second=json.loads(registry.dispatch('jinx_apps',{'app':'firefox','action':'open'}))
   self.assertEqual(first['status'],'launch_requested');self.assertTrue(second['task_stopped'])
   fake.assert_called_once()
  # Re-register normal handlers before other suites can use this registry.
  with patch.object(j,'agent',None):j.get_agent()
  j.agent=previous

 def test_skills_cover_real_workflows_without_confirmation_click(self):
  for query,expected in [('Install Spotify','jinx_software'),('write an email','jinx_email_draft'),('open Nexus Mods','jinx_browser'),('calendar tomorrow','jinx_calendar'),('play my music','jinx_music')]:
   self.assertIn(expected,jinx_skills.brief_for_request(query))
  self.assertNotIn('Confirm preview',jinx_skills.view({'name':'troubleshooting'})['instructions'])

if __name__=='__main__':unittest.main()
