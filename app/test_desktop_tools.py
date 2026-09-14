import jinx_test_support  # Isolate state and memory before importing jinx.
import unittest
from unittest.mock import patch
import desktop_tools as d
import system_tools as system
import jinx as j

class DesktopTasks(unittest.TestCase):
 def test_understands_explicit_tasks_and_rejects_quoted_negated_or_compound_sources(self):
  cases={'Open my NAS':{'action':'open_folder','folder':'nas'},'Open my nass storage':{'action':'open_folder','folder':'nas'},'Could you open my Downloads folder please?':{'action':'open_folder','folder':'downloads'},'Set brightness to 40 percent':{'action':'set_brightness','percent':40},'Turn volume down':{'action':'adjust_volume','delta':-10},'Unmute the sound':{'action':'mute','muted':False}}
  for text,value in cases.items():self.assertEqual(d.intent(text),value)
  for text in ['Do not mute the sound','Explain the phrase mute the sound','Read this page and set volume to 80 percent','Mute my microphone','Open /etc/shadow','What if I turn volume down?']:
   self.assertIsNone(d.intent(text))
 def test_volume_readback_and_muted_feedback(self):
  with patch.object(d,'audio',side_effect=[{'volume':70,'muted':True},{'volume':30,'muted':True}]),patch.object(d,'command') as run,patch.object(system,'audit'):
   result=d.perform({'action':'set_volume','percent':30})
   self.assertEqual(result['status'],'verified');self.assertIn('still muted',result['reply'])
   run.assert_called_once_with(['wpctl','set-volume','@DEFAULT_AUDIO_SINK@','0.3'])
 def test_failed_readback_does_not_claim_success(self):
  with patch.object(d,'audio',return_value={'volume':70,'muted':False}),patch.object(d,'command'),patch.object(d.time,'sleep'),self.assertRaisesRegex(ValueError,'did not stick'):
   d.perform({'action':'set_volume','percent':30})
 def test_invalid_values_never_write(self):
  for value in [-1,101,float('nan'),True,'50; id']:
   with patch.object(d,'audio',return_value={'volume':70,'muted':False}),patch.object(d,'command') as run,self.assertRaises(ValueError):d.perform({'action':'set_volume','percent':value})
   run.assert_not_called()
 def test_arbitrary_folder_refused(self):
  with patch.object(d,'command') as run,self.assertRaises(ValueError):d.perform({'action':'open_folder','folder':'../../etc'})
  run.assert_not_called()
 def test_model_cannot_change_different_setting_or_act_from_source(self):
  with patch.object(j,'current_request','Set volume to 30 percent'),patch.dict(j.status,{'external_context':False}),patch.object(d,'perform') as perform:
   with self.assertRaises(ValueError):j.guarded_desktop({'action':'set_volume','percent':80})
   perform.assert_not_called()
   j.guarded_desktop({'action':'set_volume','percent':30});perform.assert_called_once()
  with patch.dict(j.status,{'external_context':True}),self.assertRaises(ValueError):j.guarded_desktop({'action':'status'})
 def test_unique_spoken_typo_and_ambiguity(self):
  apps={'spotify':{'name':'Spotify','aliases':[]},'firefox':{'name':'Firefox','aliases':[]}}
  self.assertEqual(system.resolve_app('spottify',apps),'spotify')
  self.assertIsNone(system.resolve_app('spot',apps))
  apps['another']={'name':'Spotify','aliases':[]}
  self.assertIsNone(system.resolve_app('Spotify',apps))
 def test_maintained_guide_contains_current_installer(self):
  guide=system.knowledge({'section':'software'})
  self.assertIn('Spotify IS installed',guide['notes'])
  self.assertIn('native installer',guide['notes'])

if __name__=='__main__':unittest.main()

class PowerFacts(unittest.TestCase):
 def test_charging_is_not_discharge_or_total_draw_and_saved_active_is_not_hardware_readback(self):
  facts=system.power_facts({'BAT0':{'type':'Battery','energy_full':'60000000','capacity':'90','status':'Charging','power_now':'9000000'}},{},{'undervolt':{'cpu_co':-30,'active':True},'tdp':{'pl1_spl':35}},{})
  self.assertIsNone(facts['battery'][0]['discharge_watts']);self.assertEqual(facts['battery'][0]['charging_watts'],9)
  self.assertFalse(facts['undervolt_hardware_verified']);self.assertEqual(facts['saved_curve_optimizer_steps'],-30)
  self.assertNotIn('-30',system.power_brief(facts));self.assertIn('unavailable',system.power_brief(facts))
 def test_sensors_and_real_discharge_are_preserved(self):
  facts=system.power_facts({'BAT0':{'type':'Battery','energy_full':'60000000','capacity':'75','status':'Discharging','power_now':'8000000'}},{'k10temp-pci-00c3':{'Tctl':{'temp1_input':61.5}},'amdgpu-pci-c400':{'edge':{'temp1_input':55.0}}},{},{})
  self.assertEqual(facts['temperatures_celsius'],{'CPU':61.5,'GPU':55.0});self.assertEqual(facts['battery'][0]['discharge_watts'],8)
  self.assertIn('Discharging at 8.0 watts',system.power_brief(facts))
