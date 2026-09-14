"""Regression tests for actual integration gaps; never actuates real devices."""
import jinx_test_support  # Isolate state and memory before importing jinx.
import unittest
from unittest.mock import patch
import home_tools as h

def entity(eid,state='off',**attrs):
 return {'entity_id':eid,'domain':eid.split('.')[0],'name':eid.split('.')[1], 'state':state,'unit':'','attributes':attrs}

class Execution(unittest.TestCase):
 def execute(self,row,action,value=None,after=None):
  home=h.Home()
  with patch.object(home,'states',side_effect=[[row],[after or row]]),patch.object(h,'_request') as request,patch.object(h.time,'monotonic',side_effect=[0,4]):
   result=home.execute(row['entity_id'],action,value)
  return result,request
 def test_tv_on_is_power_not_play(self):
  row=entity('media_player.tv',supported_features=128)
  result,req=self.execute(row,'turn_on',after={**row,'state':'idle'})
  req.assert_called_once_with('/api/services/media_player/turn_on',{'entity_id':'media_player.tv'})
  self.assertTrue(result['verified'])
 def test_tv_pause_is_distinct(self):
  row=entity('media_player.tv','playing',supported_features=1)
  result,req=self.execute(row,'pause',after={**row,'state':'paused'})
  self.assertTrue(result['verified']);self.assertIn('media_pause',req.call_args.args[0])
 def test_http_success_does_not_mean_device_changed(self):
  result,req=self.execute(entity('light.test'),'turn_on')
  self.assertFalse(result['verified']);req.assert_called_once()
 def test_unavailable_device_does_not_receive_command(self):
  with patch.object(h,'_request') as req,patch.object(h.Home,'states',return_value=[entity('fan.test','unavailable')]):
   with self.assertRaises(h.HomeError):h.Home().execute('fan.test','turn_on')
  req.assert_not_called()
 def test_humidifier_target_is_not_light_brightness(self):
  row=entity('humidifier.test','on',humidity=45,min_humidity=30,max_humidity=80)
  result,req=self.execute(row,'set_humidity',50,{**row,'attributes':{**row['attributes'],'humidity':50}})
  req.assert_called_once_with('/api/services/humidifier/set_humidity',{'entity_id':'humidifier.test','humidity':50})
  self.assertTrue(result['verified'])
 def test_reject_wrong_domain_and_invalid_percentages(self):
  for row,action,value in [(entity('humidifier.test'),'set_brightness',40),(entity('light.test'),'set_brightness',140),(entity('light.test'),'set_brightness',-1),(entity('fan.test'),'set_fan_mode','unknown')]:
   with patch.object(h.Home,'states',return_value=[row]),patch.object(h,'_request') as req:
    with self.assertRaises(h.HomeError):h.Home().execute(row['entity_id'],action,value)
    req.assert_not_called()
 def test_curtains_can_move_but_garage_cannot(self):
  row=entity('cover.bedroom','closed',device_class='curtain',supported_features=15)
  result,req=self.execute(row,'open_cover',after={**row,'state':'open'})
  self.assertTrue(result['verified']);self.assertIn('open_cover',req.call_args.args[0])
  for cls in ('garage','door','gate',None):
   with patch.object(h.Home,'states',return_value=[entity('cover.garage','closed',device_class=cls)]),patch.object(h,'_request') as req:
    with self.assertRaises(h.HomeError):h.Home().execute('cover.garage','open_cover')
    req.assert_not_called()
 def test_scene_off_never_activates_scene(self):
  with patch.object(h.Home,'states',return_value=[entity('scene.bedtime','unknown')]),patch.object(h,'_request') as req:
   with self.assertRaises(h.HomeError):h.Home().execute('scene.bedtime','turn_off')
   req.assert_not_called()
 def test_washer_power_is_monitoring_only(self):
  with patch.object(h,'_request') as req:
   with self.assertRaises(h.HomeError):h.Home().execute('switch.washer_power','turn_off')
   req.assert_not_called()
 def test_same_name_devices_do_not_pick_first(self):
  rows=[{**entity('light.one'),'name':'Bedroom'},{**entity('light.two'),'name':'Bedroom'}]
  self.assertIn('error',h.resolve(rows,'Bedroom'))
 def test_entity_metadata_hides_private_attributes(self):
  with patch.object(h,'_request',return_value=[{'entity_id':'humidifier.test','state':'on','attributes':{'friendly_name':'Humidifier','humidity':45,'current_humidity':60,'token':'test-private','mac':'test-private'}}]):
   row=h.Home().states()[0]
  self.assertEqual(row['attributes'],{'humidity':45,'current_humidity':60})
 def test_compound_percent_text_cannot_become_a_number(self):
  self.assertIsNone(h.parse('set the bedroom light to 40 percent and turn off the router'))
 def test_supported_phrasings(self):
  for text,action in [('set the humidifier to 45 percent','set_humidity'),('set the purifier to sleep mode','set_fan_mode'),('open the bedroom curtains','open_cover'),('stop the curtains','stop_cover'),('pause the C4','pause'),('is the washer finished','state')]:
   self.assertEqual(h.parse(text)['action'],action)
 def test_alias_group_reports_each_device_without_acting(self):
  home=h.Home();rows=[entity('light.bedroom_main_light'),entity('light.bedroom_light','on')]
  with patch.object(h,'configured',return_value=True),patch.object(home,'states',return_value=rows),patch.object(home,'call') as call:
   reply=h.requested('are the bedroom lights on',home)['reply']
  self.assertIn('bedroom_main_light is off',reply);self.assertIn('bedroom_light is on',reply);call.assert_not_called()
 def test_missing_group_member_blocks_partial_execution(self):
  home=h.Home()
  with patch.object(h,'configured',return_value=True),patch.object(home,'states',return_value=[entity('light.bedroom_main_light')]),patch.object(home,'call') as call:
   reply=h.requested('turn on the bedroom lights',home)['reply']
  self.assertIn('missing',reply);call.assert_not_called()
 def test_model_home_tool_cannot_mutate_or_read_from_external_source_turn(self):
  import jinx
  with patch.object(h,'tool') as tool,patch.dict(jinx.status,{'external_context':False}):
   self.assertIn('error',jinx.guarded_home({'action':'turn_on','name':'humidifier'}));tool.assert_not_called()
  with patch.object(h,'tool') as tool,patch.dict(jinx.status,{'external_context':True}):
   self.assertIn('error',jinx.guarded_home({'action':'state','name':'humidifier'}));tool.assert_not_called()

if __name__=='__main__':unittest.main()
