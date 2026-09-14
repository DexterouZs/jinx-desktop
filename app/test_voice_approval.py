import jinx_test_support  # Isolate state and memory before importing jinx.
import copy,unittest
from unittest.mock import patch
from voice_approval import Approval
import jinx as j

ITEM={'id':'new','kind':'remember','fields':{'text':'A test note'}}
OLD={'id':'old','kind':'power_profile','fields':{'profile':'performance'}}

class ApprovalTests(unittest.TestCase):
 def test_yes_applies_only_to_read_back_item(self):
  a=Approval();a.arm([ITEM]);r=a.consume('yes',[OLD,ITEM])
  self.assertEqual(r['item'],ITEM);self.assertEqual(r['decision'],'yes')
  self.assertIsNone(a.consume('yes',[OLD,ITEM]))
 def test_no_is_specific(self):
  a=Approval();a.arm([ITEM]);self.assertEqual(a.consume('No thanks',[OLD,ITEM])['decision'],'no')
 def test_unrelated_turn_disarms(self):
  a=Approval();a.arm([ITEM]);a.consume('what time is it',[ITEM]);self.assertIsNone(a.consume('yes',[ITEM]))
 def test_changed_item_requires_new_readback(self):
  a=Approval();a.arm([ITEM]);changed=copy.deepcopy(ITEM);changed['fields']['text']='Different'
  self.assertEqual(a.consume('yes',[changed])['decision'],'stale')
 def test_expired_offer_does_not_execute(self):
  a=Approval();a.arm([ITEM]);a.offer['at']-=121
  self.assertEqual(a.consume('yes',[ITEM])['decision'],'stale')
 def test_no_offer_never_selects_old_pending(self):
  self.assertIsNone(Approval().consume('yes',[OLD]))
 def test_only_exact_assent_counts(self):
  for text in ['yes but change the time','yesterday','no problem','I said yes earlier']:
   a=Approval();a.arm([ITEM]);self.assertIsNone(a.consume(text,[ITEM]))
 def test_execute_uses_existing_action_only_once(self):
  a=Approval();a.arm([ITEM])
  with patch.object(j,'approval',a),patch.object(j,'data',{'pending':[OLD,ITEM]}),patch.object(j,'confirm',return_value='Saved') as execute,patch.object(j.messages,'disarm'):
   self.assertEqual(j.approval_request('yes')['reply'],'Saved')
   self.assertIsNone(j.approval_request('yes'))
   execute.assert_called_once_with('new',record_message=False)
 def test_no_retains_other_pending_settings(self):
  a=Approval();a.arm([ITEM]);data={'pending':[OLD,ITEM]}
  with patch.object(j,'approval',a),patch.object(j,'data',data),patch.object(j,'save'),patch.object(j,'confirm') as execute,patch.object(j.messages,'disarm'):
   self.assertIn('Cancelled',j.approval_request('no')['reply']);execute.assert_not_called()
   self.assertEqual(data['pending'],[OLD])
 def test_summary_reads_exact_reminder_without_click(self):
  text=j.proposal_summary({'kind':'reminder','fields':{'when':'2026-09-12T16:00:00+02:00','text':'Work time'}})
  self.assertIn('16:00',text);self.assertIn('Work time',text);self.assertIn('yes or no',text);self.assertNotIn('Click',text)
 def test_software_does_not_depend_on_preview_window(self):
  text=j.proposal_summary({'id':'software','kind':'software_install','fields':{'package':'merkuro','version':'1','repo':'extra'}})
  self.assertIn('merkuro',text);self.assertIn('yes or no',text);self.assertNotIn('window is open',text)

if __name__=='__main__':unittest.main()

class ChatApprovalTests(unittest.TestCase):
 def exercise(self,cancel=False):
  from contextlib import ExitStack
  state=copy.deepcopy(j.data);state['pending']=[copy.deepcopy(OLD),copy.deepcopy(ITEM)];state['speak']=False
  approval=Approval();calls=[]
  with ExitStack() as stack:
   stack.enter_context(patch.object(j,'data',state));stack.enter_context(patch.object(j,'approval',approval))
   stack.enter_context(patch.dict(j.status,{'messages':[],'voice_epoch':100}))
   stack.enter_context(patch.object(j,'history',[]));stack.enter_context(patch.object(j,'save'))
   stack.enter_context(patch.object(j.home_tools,'followup_request',return_value={}))
   stack.enter_context(patch.object(j.messages,'disarm'))
   def speak(text,*args,**kwargs):
    self.assertIsNone(approval.offer);calls.append(text)
    if cancel:j.status['voice_epoch']+=1
   stack.enter_context(patch.object(j,'say',side_effect=speak))
   execute=stack.enter_context(patch.object(j,'action',return_value='Saved'))
   j.chat('review the pending action',spoken=True)
   self.assertFalse(j.status['error']);execute.assert_not_called();self.assertIn('yes or no',calls[0])
   if cancel:self.assertIsNone(approval.offer);return
   self.assertIsNotNone(approval.offer)
   j.chat('yes',spoken=False)
   execute.assert_called_once_with(ITEM);self.assertEqual(state['pending'],[OLD]);self.assertIsNone(approval.offer)
 def test_full_chat_only_executes_after_readback_and_yes(self):self.exercise()
 def test_cancelled_speech_never_arms(self):self.exercise(True)
