import jinx_test_support
import copy,datetime as dt,json,tempfile,time,unittest,urllib.error
from pathlib import Path
from unittest.mock import Mock,patch
import morgen_tools as m
import calendar_delete as d
import calendar_intents as ci
import jinx as j
C={'id':'calendar','accountId':'account','name':'Personal'}
E={'id':'Opaque+/== ID','accountId':'account','calendarId':'calendar','title':'Test appointment',
   'start':'2030-01-01T11:00:00','duration':'PT30M','timeZone':'Etc/UTC'}
P='1234567890abcdef'

def row(event=E):
 a,b=m.times(event)
 return {'event':copy.deepcopy(event),'title':event['title'],'calendar_name':'Personal','start':a.isoformat(),'end':b.isoformat(),'all_day':False}
def fields(event=E):
 r=row(event);return {**r,'fingerprint':d.digest(event),'prepared_at':time.time(),'series_mode':'single'}

class Delete(unittest.TestCase):
 def setUp(self):
  tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
  self.root=Path(tmp.name)
  for p in (patch.object(m,'STATE',self.root),patch.object(m,'config',return_value=C)):
   p.start();self.addCleanup(p.stop)
 def test_match_readback_and_id_unchanged(self):
  with patch.object(m,'api',return_value={'event':E}):f=d.prepare(row())
  with patch.object(m,'api',side_effect=[{'event':E},{'http_status':204},m.MorgenHTTPError(404)]) as api:
   self.assertIn('Deleted and verified',d.remove(f,P))
  self.assertEqual(api.call_args_list[1].args,('events/delete',{'seriesUpdateMode':'single'}))
  self.assertEqual(api.call_args_list[1].kwargs['body'],d.identity(E))
  backup=next((self.root/'calendar-deletions').glob('*.json'))
  self.assertEqual(json.loads(backup.read_text())['original_event'],E)
  self.assertEqual(backup.stat().st_mode&0o777,0o600)
 def test_changed_event_never_deleted(self):
  with patch.object(m,'api',return_value={'event':{**E,'title':'Changed'}}) as api:
   with self.assertRaisesRegex(ValueError,'changed after'):d.remove(fields(),P)
  self.assertEqual(api.call_count,1)
 def test_changed_readback_never_deleted(self):
  with patch.object(m,'api') as api:
   with self.assertRaisesRegex(ValueError,'read-back details'):d.remove({**fields(),'title':'Different'},P)
   api.assert_not_called()
 def test_uncertain_delete_never_reposts_even_with_new_proposal(self):
  with patch.object(m,'api',side_effect=[{'event':E},ValueError('timeout')]):
   with self.assertRaises(ValueError):d.remove(fields(),P)
  with patch.object(m,'api',return_value={'event':E}) as api:
   with self.assertRaisesRegex(ValueError,'not repeat'):d.remove(fields(),'abcdef1234567890')
   self.assertEqual(api.call_count,1);self.assertEqual(api.call_args.args[0],'events')
 def test_503_is_not_absence(self):
  with patch.object(m,'api',side_effect=[{'event':E},{'http_status':204},m.MorgenHTTPError(503)]):
   with self.assertRaises(m.MorgenHTTPError):d.remove(fields(),P)
 def test_acceptance_without_absence_is_unverified(self):
  with patch.object(m,'api',side_effect=[{'event':E},{'http_status':204},{'event':E}]):
   with self.assertRaisesRegex(ValueError,'unverified'):d.remove(fields(),P)
 def test_expired_no_write(self):
  with patch.object(m,'api') as api:
   with self.assertRaisesRegex(ValueError,'expired'):d.remove({**fields(),'prepared_at':time.time()-400},P)
   api.assert_not_called()
 def test_no_other_account_or_invite_or_series(self):
  for changed in ({'accountId':'other'},{'participants':{'other':{}}},{'recurrenceRules':[{'frequency':'weekly'}]}):
   with self.assertRaises(ValueError):d.allowed({**E,**changed})
 def test_provider_owner_metadata_is_not_a_guest(self):
  self.assertEqual(d.allowed({**E,'participants':{'self':{'accountOwner':True,'roles':{'owner':True}}}}),C)
  with self.assertRaises(ValueError):
   d.allowed({**E,'participants':{'self':{'accountOwner':True,'roles':{'owner':True}},'guest':{'roles':{'attendee':True}}}})

 def test_recurring_instance_explicit_single_only(self):
  event={**E,'masterEventId':'series','recurrenceId':'2030-01-01T11:00:00','recurrenceRules':[{'frequency':'weekly'}]}
  with patch.object(m,'api',side_effect=[{'event':event},{'http_status':204},m.MorgenHTTPError(404)]) as api:
   d.remove(fields(event),P)
   self.assertEqual(api.call_args_list[1].args[1],{'seriesUpdateMode':'single'})
 def test_preexisting_absence_no_post_and_no_false_claim(self):
  with patch.object(m,'api',side_effect=m.MorgenHTTPError(404)) as api:
   self.assertIn('I did not delete',d.remove(fields(),P));self.assertEqual(api.call_count,1)
 def test_multiple_calendars_and_wrong_account_detection(self):
  (self.root/'morgen-readable-calendars.json').write_text(json.dumps([C,{**C,'id':'work','name':'Work'}]))
  with patch.object(m,'api',return_value={'events':[E,{**E,'id':'second','calendarId':'work'}]}):
   self.assertEqual(len(d.candidates(dt.date(2030,1,1))),2)
  with patch.object(m,'api',return_value={'events':[{**E,'accountId':'wrong'}]}):
   with self.assertRaises(ValueError):d.candidates(dt.date(2030,1,1))
 def test_already_verified_second_confirmation_reads_only(self):
  with patch.object(m,'api',side_effect=[{'event':E},{'http_status':204},m.MorgenHTTPError(404)]):d.remove(fields(),P)
  with patch.object(m,'api',side_effect=m.MorgenHTTPError(404)) as api:
   self.assertIn('verified',d.remove(fields(),P));self.assertEqual(api.call_count,1)

class Dialogue(unittest.TestCase):
 def setUp(self):ci.reset();self.addCleanup(ci.reset)
 def test_ambiguous_selection_uses_actual_second_id(self):
  rows=[row(),row({**E,'id':'second','title':'Other'})]
  with patch.object(d,'candidates',return_value=rows),patch.object(d,'prepare',side_effect=lambda c:fields(c['event'])) as prepare:
   result=ci.requested('Jings, can you actually delete my appointment for tomorrow?')
   self.assertIn('Which appointment',result['reply']);prepare.assert_not_called()
   result=ci.requested('the second one')
   self.assertEqual(result['delete_fields']['event']['id'],'second')
 def test_missing_date_then_tomorrow(self):
  with patch.object(d,'candidates',return_value=[row()]),patch.object(d,'prepare',return_value=fields()):
   self.assertIn('Which day',ci.requested('delete my appointment')['reply'])
   self.assertIn('delete_fields',ci.requested('tomorrow'))
 def test_named_title_and_time(self):
  rows=[row(),row({**E,'id':'second','title':'Dentist','start':'2030-01-01T15:00:00'})]
  with patch.object(d,'candidates',return_value=rows),patch.object(d,'prepare',side_effect=lambda c:fields(c['event'])):
   f=ci.requested('delete my Dentist appointment tomorrow at 16:00')['delete_fields']
   self.assertEqual(f['event']['id'],'second')
 def test_no_event_no_inference_no_proposal(self):
  with patch.object(d,'candidates',return_value=[]):
   self.assertIn('no matching',ci.requested('delete my appointment tomorrow')['reply'])
 def test_cancel_and_new_session_clear_selection(self):
  ci.pending={'query':'appointment','expires':time.monotonic()+100}
  self.assertIn('Cancelled',ci.requested('cancel')['reply']);self.assertIsNone(ci.pending)
  ci.pending={'query':'appointment','expires':time.monotonic()+100};j.new_voice_session();self.assertIsNone(ci.pending)
 def test_proposal_only_then_unchanged_fresh_yes(self):
  saved=copy.deepcopy(j.data);old=j.current_request
  try:
   j.data['pending']=[];j.approval.clear()
   with patch.object(d,'candidates',return_value=[row()]),patch.object(d,'prepare',return_value=fields()),patch.object(d,'remove',return_value='Deleted and verified.') as remove,patch.object(j,'save'),patch.object(j,'say'):
    j.chat('delete my appointment tomorrow',False)
    remove.assert_not_called();self.assertEqual(j.data['pending'][0]['kind'],'calendar_delete')
    self.assertIn('Say yes or no',j.status['last_draft'])
    j.chat('yes',False);remove.assert_called_once()
    self.assertIsNone(j.approval.consume('yes',j.data['pending']))
  finally:j.data.clear();j.data.update(saved);j.current_request=old;j.approval.clear()
 def test_delete_confirmation_is_scoped_and_changed_offer_rejected(self):
  from voice_approval import Approval
  approval=Approval();item={'id':P,'kind':'calendar_delete','fields':fields()}
  approval.arm([item]);self.assertEqual(approval.consume('yes, delete it',[item])['decision'],'yes')
  approval.arm([{**item,'kind':'calendar_event'}]);self.assertIsNone(approval.consume('delete it',[{**item,'kind':'calendar_event'}]))
  approval.arm([item]);changed=copy.deepcopy(item);changed['fields']['title']='Changed'
  self.assertEqual(approval.consume('yes delete it',[changed])['decision'],'stale')

 def test_quoted_negative_and_other_tasks_not_claimed(self):
  for text in ('write an email saying delete my appointment tomorrow','Do not delete my appointment','Cancel my timer','Show my appointments tomorrow'):
   self.assertIsNone(ci.requested(text),text)

class Transport(unittest.TestCase):
 def test_204_empty_body_is_not_parsed(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'morgen-api.key').write_text('test-key')
   response=Mock(status=204);response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
   with patch.object(m,'STATE',p),patch.object(m.OPENER,'open',return_value=response):
    self.assertEqual(m.api('events/delete',{'seriesUpdateMode':'single'},body=d.identity(E)),{'http_status':204})
    response.read.assert_not_called()

if __name__=='__main__':unittest.main()
