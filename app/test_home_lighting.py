import copy,time,unittest
from unittest.mock import patch
import home_tools as h

LIGHT={'entity_id':'light.bedroom_light','domain':'light','name':'Bedroom Light',
       'state':'on','unit':'','attributes':{'supported_color_modes':['hs','white'],
       'hs_color':[180,31.2],'brightness':12}}


class FakeHome:
 def __init__(self):self.calls=[]
 def states(self,force=False):return [copy.deepcopy(LIGHT)]
 def execute(self,e,a,v):
  self.calls.append((e,a,v));return {'verified':True,'entity':copy.deepcopy(LIGHT)}
 def call(self,e,on,brightness=None):return self.execute(e,'set_brightness',brightness)


class Lighting(unittest.TestCase):
 def setUp(self):h.LIGHT_CONTEXT.clear()
 def tearDown(self):h.LIGHT_CONTEXT.clear()

 def turn(self,text,home):
  with patch.object(h,'configured',return_value=True):
   return h.followup_request(text,home) or h.requested(text,home)

 def test_real_failed_phrases_now_work_in_sequence(self):
  home=FakeHome()
  a=self.turn('Jinx, can you make the bedroom light blue?',home)
  b=self.turn('Well, make the brightness maximum.',home)
  self.assertEqual(a['reply'],'Bedroom Light set to blue')
  self.assertEqual(b['reply'],'Bedroom Light set to 100%')
  self.assertEqual(home.calls,[('light.bedroom_light','set_colour','blue'),('light.bedroom_light','set_brightness',100)])

 def test_named_and_pronoun_variants(self):
  home=FakeHome()
  for text in ['set the bedroom light to blue','make it red','set it to 40 percent','make it maximum brightness']:
   self.assertIn('Bedroom Light',self.turn(text,home)['reply'])
  self.assertEqual(len(home.calls),4)

 def test_unrelated_turn_expires_target(self):
  home=FakeHome();self.turn('make the bedroom light blue',home)
  self.assertIsNone(h.followup_request('What is the weather?',home))
  a=self.turn('make it red',home)
  self.assertIn('Which light',a['reply']);self.assertEqual(len(home.calls),1)

 def test_timeout_expires_target(self):
  h.LIGHT_CONTEXT.update(entity_id='light.bedroom_light',at=time.monotonic()-121)
  home=FakeHome();a=self.turn('make it blue',home)
  self.assertIn('Which light',a['reply']);self.assertFalse(home.calls)

 def test_screen_brightness_without_light_context_is_not_stolen(self):
  self.assertIsNone(h.followup_request('set brightness to 40 percent',FakeHome()))
  self.assertIsNone(h.followup_request('set screen brightness to 40 percent',FakeHome()))

 def test_colour_is_capability_checked_and_actual_state_verified(self):
  home=h.Home();before=copy.deepcopy(LIGHT);after=copy.deepcopy(LIGHT)
  after['attributes']['hs_color']=[240,100]
  with patch.object(home,'states',side_effect=[[before],[after]]),patch.object(h,'_request') as send:
   r=home.execute(LIGHT['entity_id'],'set_colour','blue')
  self.assertTrue(r['verified'])
  send.assert_called_once_with('/api/services/light/turn_on',{'entity_id':LIGHT['entity_id'],'hs_color':[240,100]})

 def test_no_change_if_bulb_lacks_colour(self):
  home=h.Home();row=copy.deepcopy(LIGHT);row['attributes']['supported_color_modes']=['brightness']
  with patch.object(home,'states',return_value=[row]),patch.object(h,'_request') as send:
   with self.assertRaises(h.HomeError):home.execute(LIGHT['entity_id'],'set_colour','blue')
   send.assert_not_called()

 def test_http_acknowledgement_does_not_fake_colour_success(self):
  home=h.Home()
  with patch.object(home,'states',return_value=[copy.deepcopy(LIGHT)]),patch.object(h,'_request'),patch.object(h.time,'monotonic',side_effect=[0,4]):
   r=home.execute(LIGHT['entity_id'],'set_colour','blue')
  self.assertFalse(r['verified'])


if __name__=='__main__':unittest.main()
