import unittest
from unittest.mock import patch
import home_tools as h

ROWS=[
 {'entity_id':'light.kitchen_lamp','domain':'light','name':'Kitchen lamp','state':'off','unit':''},
 {'entity_id':'light.desk_lamp','domain':'light','name':'Desk lamp','state':'on','unit':''},
 {'entity_id':'switch.coffee','domain':'switch','name':'Coffee machine','state':'off','unit':''},
 {'entity_id':'sensor.hall_temp','domain':'sensor','name':'Hall temperature','state':'19.4','unit':'°C'},
 {'entity_id':'lock.front','domain':'lock','name':'Front door','state':'locked','unit':''},
]

class FakeHome:
 def __init__(self):self.calls=[]
 def states(self,force=False):return ROWS
 def resolve(self,name,domains=None):return h.resolve(ROWS,name,domains)
 def call(self,entity_id,turn_on,brightness=None):
  if entity_id.split('.')[0] not in h.CONTROL:raise h.HomeError('read-only')
  self.calls.append((entity_id,turn_on,brightness));return {'verified':True,'entity':next(r for r in ROWS if r['entity_id']==entity_id)}

class Parsing(unittest.TestCase):
 def test_reads_control_and_query_phrasings(self):
  cases={
   'Turn on the kitchen lamp':{'action':'set','on':True,'name':'the kitchen lamp'},
   'turn the desk lamp off':{'action':'set','on':False,'name':'the desk lamp'},
   'Switch off the coffee machine':{'action':'set','on':False,'name':'the coffee machine'},
   'Jinx, is the desk lamp on?':{'action':'state','name':'desk lamp'},
   'are the kitchen lamp on':{'action':'state','name':'kitchen lamp'},
  }
  for text,value in cases.items():
   self.assertEqual(h.parse(text),value,text)
  got=h.parse('Set the kitchen lamp to 40%')
  self.assertEqual((got['action'],got['on'],got['brightness']),('set',True,40))

 def test_ignores_requests_that_are_not_home_commands(self):
  for text in ['','What is the weather like','Write me an essay about lamps','Play some music']:
   self.assertIsNone(h.parse(text))

class Resolution(unittest.TestCase):
 def test_exact_and_partial_names_resolve(self):
  self.assertEqual(h.resolve(ROWS,'Kitchen lamp')['entity']['entity_id'],'light.kitchen_lamp')
  self.assertEqual(h.resolve(ROWS,'coffee')['entity']['entity_id'],'switch.coffee')

 def test_ambiguity_asks_instead_of_guessing(self):
  found=h.resolve(ROWS,'lamp')
  self.assertIn('error',found)
  self.assertIn('Desk lamp',found['error'])
  self.assertIn('Kitchen lamp',found['error'])

 def test_unknown_device_is_reported(self):
  self.assertIn('error',h.resolve(ROWS,'garage door'))

 def test_control_requests_do_not_match_read_only_devices(self):
  self.assertIn('error',h.resolve(ROWS,'Front door',h.CONTROL))
  self.assertEqual(h.resolve(ROWS,'Front door')['entity']['domain'],'lock')

class Requests(unittest.TestCase):
 def test_state_query_answers_without_acting(self):
  home=FakeHome()
  with patch.object(h,'configured',return_value=True):
   self.assertEqual(h.requested('is the desk lamp on',home)['reply'],'Desk lamp is on')
  self.assertEqual(home.calls,[])

 def test_sensor_reply_includes_unit(self):
  home=FakeHome()
  with patch.object(h,'configured',return_value=True):
   self.assertEqual(h.requested('is the hall temperature',home)['reply'],'Hall temperature is 19.4°C')

 def test_control_acts_and_confirms(self):
  home=FakeHome()
  with patch.object(h,'configured',return_value=True):
   self.assertEqual(h.requested('turn on the kitchen lamp',home)['reply'],'Kitchen lamp on')
  self.assertEqual(home.calls,[('light.kitchen_lamp',True,None)])

 def test_brightness_is_applied_and_bounded(self):
  home=FakeHome()
  with patch.object(h,'configured',return_value=True):
   h.requested('set the kitchen lamp to 40%',home)
  self.assertEqual(home.calls,[('light.kitchen_lamp',True,40)])

 def test_locks_are_never_actuated(self):
  home=FakeHome()
  with patch.object(h,'configured',return_value=True):
   reply=h.requested('turn off the front door',home)['reply']
  self.assertIn('No device',reply)
  self.assertEqual(home.calls,[])

 def test_unconfigured_falls_through_silently(self):
  with patch.object(h,'configured',return_value=False):
   self.assertIsNone(h.requested('turn on the kitchen lamp',FakeHome()))

 def test_backend_failure_reports_without_leaking_token(self):
  class Broken(FakeHome):
   def states(self,force=False):raise h.HomeError('Home Assistant rejected the access token')
  with patch.object(h,'configured',return_value=True):
   reply=h.requested('turn on the kitchen lamp',Broken())['reply']
  self.assertEqual(reply,'Home Assistant rejected the access token')

class AgentTool(unittest.TestCase):
 def test_tool_lists_states_and_acts(self):
  home=FakeHome()
  with patch.object(h,'configured',return_value=True):
   self.assertEqual(len(h.tool({'action':'list','domain':'light'},home)['devices']),2)
   self.assertEqual(h.tool({'action':'state','name':'coffee'},home)['device'],'Coffee machine is off')
   self.assertEqual(h.tool({'action':'turn_on','name':'coffee'},home)['done'],'Coffee machine on')
   self.assertIn('error',h.tool({'action':'turn_off','name':'front door'},home))
   self.assertIn('error',h.tool({'action':'run_script','name':'anything'},home))



SUB_ENTITIES=[
 {'entity_id':'switch.living_room_lamp','domain':'switch','name':'Living Room Lamp','state':'on','unit':''},
 {'entity_id':'switch.lamp_child_lock','domain':'switch','name':'Lamp Child Lock','state':'off','unit':''},
 {'entity_id':'sensor.lamp_energy','domain':'sensor','name':'Lamp Energy','state':'4.1','unit':'kWh'},
 {'entity_id':'sensor.washer_energy_last_month','domain':'sensor','name':'Washer Energy last month','state':'9','unit':'kWh'},
 {'entity_id':'media_player.bedroom_echo','domain':'media_player','name':'Bedroom Echo','state':'idle','unit':''},
 {'entity_id':'media_player.living_room_echo','domain':'media_player','name':'Living Room Echo','state':'idle','unit':''},
 {'entity_id':'switch.bedroom_echo_dnd','domain':'switch','name':'Bedroom Echo DND','state':'off','unit':''},
]

class SubEntities(unittest.TestCase):
 def test_the_device_wins_over_its_diagnostic_sub_entities(self):
  # Smart plugs expose "Lamp Child Lock" and "Lamp Energy" beside the lamp;
  # without this, every ordinary command is ambiguous.
  self.assertEqual(h.resolve(SUB_ENTITIES,'lamp')['entity']['entity_id'],'switch.living_room_lamp')

 def test_metric_sub_entities_are_not_devices(self):
  for row in SUB_ENTITIES:
   if row['name'] in ('Lamp Child Lock','Lamp Energy','Washer Energy last month','Bedroom Echo DND'):
    self.assertFalse(h.primary(row),row['name'])
   else:
    self.assertTrue(h.primary(row),row['name'])

 def test_genuinely_several_devices_still_ask(self):
  # Two real Echoes must stay ambiguous; the filter must not collapse them.
  found=h.resolve(SUB_ENTITIES,'echo')
  self.assertIn('error',found)
  self.assertIn('Bedroom Echo',found['error'])
  self.assertIn('Living Room Echo',found['error'])

 def test_a_sub_entity_is_still_reachable_by_its_own_full_name(self):
  self.assertEqual(h.resolve(SUB_ENTITIES,'Lamp Child Lock')['entity']['entity_id'],'switch.lamp_child_lock')

if __name__=='__main__':unittest.main()
