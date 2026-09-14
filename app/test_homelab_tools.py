import unittest
from unittest.mock import patch
import homelab_tools as hl

UP={'key':'nas','name':'NAS','up':True,'detail':''}
DOWN={'key':'proxmox','name':'Proxmox','up':False,'detail':'not responding'}
JELLY={'key':'jellyfin','name':'Jellyfin','up':True,'detail':'Nichtflix v12.0.0'}

class Parsing(unittest.TestCase):
 def test_recognises_status_questions(self):
  self.assertEqual(hl.parse('is the NAS up'),{'action':'one','name':'nas','negated':False})
  self.assertEqual(hl.parse('Is Proxmox running?'),{'action':'one','name':'proxmox','negated':False})
  self.assertEqual(hl.parse('Hey Jinx, is jellyfin online?'),{'action':'one','name':'jellyfin','negated':False})
  self.assertEqual(hl.parse('is everything up'),{'action':'all'})
  self.assertEqual(hl.parse('is anything down?'),{'action':'all'})

 def test_down_questions_are_marked_negated(self):
  self.assertTrue(hl.parse('is the NAS down')['negated'])

 def test_ignores_unrelated_requests(self):
  for text in ['','what time is it','play some music','is the desk lamp on']:
   got=hl.parse(text)
   # Lamp phrasing parses as a service question but resolves to no service,
   # which is what makes requested() fall through to Home Assistant.
   if got and got.get('action')=='one':
    self.assertIsNone(hl.find(got['name']),text)
   else:
    self.assertIsNone(got,text)

class Lookup(unittest.TestCase):
 def test_aliases_find_services(self):
  for alias,key in [('nas','nas'),('storage','nas'),('proxmox','proxmox'),('pve','proxmox'),
                    ('jellyfin','jellyfin'),('nichtflix','jellyfin'),('home assistant','home_assistant')]:
   found=hl.find(alias)
   self.assertIsNotNone(found,alias)
   self.assertEqual(found['key'],key,alias)

 def test_unknown_names_are_not_invented(self):
  for name in ['desk lamp','kitchen','','printer']:
   self.assertIsNone(hl.find(name),name)

class Reporting(unittest.TestCase):
 def test_a_reachable_service_reads_naturally(self):
  self.assertEqual(hl.describe(UP),'NAS is up')
  self.assertEqual(hl.describe(JELLY),'Jellyfin is up — Nichtflix v12.0.0')

 def test_an_unreachable_service_is_not_dressed_up(self):
  self.assertEqual(hl.describe(DOWN),'Proxmox is not responding')

 def test_summary_names_what_is_down(self):
  self.assertEqual(hl.summarise([UP,JELLY]),'All 2 services are up')
  summary=hl.summarise([UP,DOWN,JELLY])
  self.assertIn('Proxmox',summary)
  self.assertIn('1 down',summary)

class Requests(unittest.TestCase):
 def test_single_service_question_checks_only_that_service(self):
  with patch.object(hl,'check',return_value=UP) as checked, patch.object(hl,'check_all') as all_checked:
   self.assertEqual(hl.requested('is the NAS up')['reply'],'NAS is up')
  checked.assert_called_once();all_checked.assert_not_called()

 def test_everything_question_checks_all(self):
  with patch.object(hl,'check_all',return_value=[UP,DOWN]):
   self.assertIn('Proxmox',hl.requested('is everything up')['reply'])

 def test_a_down_question_answers_in_the_same_sense(self):
  with patch.object(hl,'check',return_value=UP):
   self.assertEqual(hl.requested('is the NAS down')['reply'],'No, NAS is up')
  with patch.object(hl,'check',return_value=DOWN):
   self.assertEqual(hl.requested('is proxmox down')['reply'],'Proxmox is not responding')

 def test_unrelated_questions_fall_through(self):
  # "is the desk lamp on" must reach Home Assistant, not be answered here.
  with patch.object(hl,'check') as checked:
   self.assertIsNone(hl.requested('is the desk lamp on'))
   self.assertIsNone(hl.requested('what time is it'))
  checked.assert_not_called()

class Safety(unittest.TestCase):
 def test_only_configured_hosts_can_be_probed(self):
  # There is no way to pass an arbitrary address in; the tool takes a name and
  # looks it up in a fixed table.
  self.assertIn('error',hl.tool({'action':'one','name':'10.0.0.5'}))
  self.assertIn('error',hl.tool({'action':'connect','name':'nas'}))

 def test_every_configured_service_is_on_the_local_network(self):
  for service in hl.DEFAULT_SERVICES:
   self.assertTrue(service['host'].startswith('192.168.'),service['host'])

if __name__=='__main__':unittest.main()
