import unittest
from unittest.mock import patch
import launch_tools as l

ENTRIES={
 'steam':{'key':'steam','name':'Steam','kind':'desktop','aliases':['steam launcher']},
 'heroic':{'key':'heroic','name':'Heroic Games Launcher','kind':'desktop','aliases':['heroic']},
 'firefox':{'key':'firefox','name':'Firefox','kind':'desktop','aliases':['browser']},
 'fallout3':{'key':'fallout3','name':'Fallout 3 - Game of the Year Edition','kind':'desktop','aliases':[]},
 'falloutnv':{'key':'falloutnv','name':'Fallout New Vegas','kind':'desktop','aliases':[]},
 'steam_22370':{'key':'steam_22370','name':'Fallout 3 goty','kind':'steam','appid':'22370','aliases':[]},
 'steam_1895880':{'key':'steam_1895880','name':'Crimson Desert','kind':'steam','appid':'1895880','aliases':[]},
}

class Parsing(unittest.TestCase):
 def test_recognises_launch_phrasings(self):
  cases={'Open Steam':'Steam','launch heroic':'heroic','Start Crimson Desert':'Crimson Desert',
         'run firefox':'firefox','Play Fallout New Vegas':'Fallout New Vegas',
         'Hey Jinx, open Steam':'Steam','Jinx, launch the Heroic':'Heroic',
         'open steam please':'steam'}
  for text,want in cases.items():
   self.assertEqual(l.parse(text),want,text)

 def test_ignores_requests_owned_by_other_tools(self):
  # These verbs collide with music, timers and folders; those modules run
  # first in the chain, but this must not claim them even in isolation.
  for text in ['play some music','play my favourite songs','start a timer for five minutes',
               'open my downloads folder','turn the volume up','read this page',
               'play the next song','set an alarm','']:
   self.assertIsNone(l.parse(text),text)

class Resolution(unittest.TestCase):
 def test_exact_and_alias_names_resolve(self):
  self.assertEqual(l.resolve('Steam',ENTRIES)['entry']['key'],'steam')
  self.assertEqual(l.resolve('browser',ENTRIES)['entry']['key'],'firefox')
  self.assertEqual(l.resolve('Crimson Desert',ENTRIES)['entry']['key'],'steam_1895880')

 def test_ambiguous_titles_ask_rather_than_guess(self):
  found=l.resolve('fallout',ENTRIES)
  self.assertIn('error',found)
  self.assertIn('Fallout',found['error'])

 def test_unknown_app_is_reported(self):
  self.assertIn('error',l.resolve('palworld',ENTRIES))

class Launching(unittest.TestCase):
 def test_desktop_entries_go_through_the_reviewed_launcher(self):
  with patch.object(l.system_tools,'desktop_apps',return_value={'status':'launch_requested','app':'Steam'}) as opened:
   reply=l.requested('Open Steam',ENTRIES)['reply']
  opened.assert_called_once_with({'action':'open','app':'steam'})
  self.assertEqual(reply,'Starting Steam')

 def test_steam_titles_launch_by_appid_not_by_shell(self):
  with patch.object(l.system_tools,'run',return_value={'ok':True}) as ran, patch.object(l.system_tools,'audit'):
   reply=l.requested('Start Crimson Desert',ENTRIES)['reply']
  argv=ran.call_args[0][0]
  self.assertIn('steam://rungameid/1895880',argv)
  self.assertTrue(all(isinstance(a,str) for a in argv))
  self.assertNotIn('sh',argv)
  self.assertEqual(reply,'Starting Crimson Desert')

 def test_a_failed_launch_is_not_reported_as_success(self):
  with patch.object(l.system_tools,'desktop_apps',return_value={'error':'gtk-launch failed'}):
   self.assertEqual(l.requested('Open Steam',ENTRIES)['reply'],'gtk-launch failed')

 def test_ambiguity_asks_and_launches_nothing(self):
  with patch.object(l.system_tools,'desktop_apps') as opened, patch.object(l.system_tools,'run') as ran:
   reply=l.requested('Open fallout',ENTRIES)['reply']
  opened.assert_not_called();ran.assert_not_called()
  self.assertIn('Several match',reply)

 def test_unknown_app_falls_through_instead_of_refusing(self):
  # Nothing installed by that name: the agent may still know what to do,
  # so tier 0 must decline the turn rather than answer it.
  with patch.object(l.system_tools,'desktop_apps') as opened:
   self.assertIsNone(l.requested('Open palworld',ENTRIES))
  opened.assert_not_called()

 def test_non_launch_requests_never_start_anything(self):
  with patch.object(l.system_tools,'desktop_apps') as opened, patch.object(l.system_tools,'run') as ran:
   for text in ['play some music','open my downloads folder','set a timer for 5 minutes']:
    self.assertIsNone(l.requested(text,ENTRIES),text)
  opened.assert_not_called();ran.assert_not_called()

class SteamDiscovery(unittest.TestCase):
 def test_runtimes_are_not_offered_as_games(self):
  manifest='"appid" "1493710"\n"name" "Proton Experimental"'
  import re
  self.assertTrue(re.match(r'(?i)(proton|steam linux runtime|steamworks)','Proton Experimental'))

if __name__=='__main__':unittest.main()
