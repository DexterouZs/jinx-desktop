import jinx_test_support
import json,struct,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
import jinx as j
import launch_tools as launch
import request_intents as intent
import routing,steam_shortcuts
from task_understanding import Tasks,relevant_apps
from test_task_understanding import plan

ENTRIES={
 'crimson':{'key':'crimson','name':'Crimson Desert Enhanced','kind':'steam','appid':'3321460','aliases':['Crimson Desert'],'game':True},
 'dmm':{'key':'dmm','name':'Crimson Desert Mod Manager','kind':'desktop','aliases':[]},
}

class Actions(unittest.TestCase):
 def test_actual_failed_phrase_and_polite_variants_resolve_game(self):
  for text in ('Jinx, can you start the game, Crimson Desert?',
               'Hey Jinx, could you please launch Crimson Desert for me?',
               'Please start the game Crimson Desert on Steam',
               'Jinx, kannst du bitte starte Crimson Desert'):
   with self.subTest(text=text):
    name=launch.parse(text)
    self.assertEqual(launch.resolve(name,ENTRIES)['entry']['key'],'crimson')

 def test_negations_quotes_and_compound_actions_do_not_launch(self):
  for text in ('Do not open Crimson Desert', 'Jinx, please do not launch Crimson Desert',
               'He said open Crimson Desert', '"open Crimson Desert"',
               'Open Crimson Desert and then send a message', 'Open Crimson Desert but not now'):
   with patch.object(launch,'launch') as opened:
    self.assertIsNone(launch.requested(text,ENTRIES),text)
    opened.assert_not_called()

 def test_web_phrasing_is_normalised_without_searching_quotes(self):
  for text in ('Hey Jinx, can you please search the web for Python asyncio?',
               'Jinx, look up Python asyncio online', 'Please google Python asyncio',
               'Jinx, kannst du bitte suche im Internet nach Python asyncio?'):
   self.assertEqual(intent.search_query(text),'Python asyncio',text)
  self.assertEqual(intent.search_query('Can you search the web?'),'')
  for text in ('Do not search the web for cats', 'Tell Alex search the web for cats',
               'The article says search the web for cats', '"search the web for cats"'):
   self.assertIsNone(intent.search_query(text))

 def test_disabled_web_and_missing_topic_never_send_network_requests(self):
  with patch.object(j,'search_web') as search:
   with patch.dict(j.data,web_enabled=False):self.assertIn('switched off',j.explicit_web_request('search for cats')['reply'])
   with patch.dict(j.data,web_enabled=True):self.assertIn('What would you like',j.explicit_web_request('can you search the web?')['reply'])
   search.assert_not_called()

 def test_direct_command_reaches_launcher_before_general_planner(self):
  with patch.dict(j.data,speak=False,episodic_memory=False),patch.object(launch,'catalog',return_value=ENTRIES),patch.object(launch,'launch',return_value={'status':'launch_requested'}) as opened,patch.object(j,'understood_task') as planner,patch.object(j.memory,'prompt_block',return_value=''),patch.object(j,'say'):
   j.chat('Jinx, can you start the game, Crimson Desert?',spoken=False)
  opened.assert_called_once_with(ENTRIES['crimson'])
  planner.assert_not_called()
  self.assertEqual(j.status['messages'][-1]['content'],'Starting Crimson Desert Enhanced')

 def test_failed_launcher_is_never_reported_as_started(self):
  with patch.object(launch,'launch',return_value={'ok':False,'output':'missing device'}):
   result=launch.requested('Play Crimson Desert',ENTRIES)
  self.assertIn('Could not start',result['reply'])

 def test_capability_denial_and_false_narration_escalate(self):
  for reply in ("I can't actually launch games or browse the web from here.",
                "I'll launch Crimson Desert for you right away.",
                'I cannot search the web.'):
   self.assertTrue(routing.handoff_reason(reply),reply)
  self.assertFalse(routing.handoff_reason('Penguins are birds.'))
  for text in ('Can you launch my game?', "You didn't launch anything yet", 'Browse the internet for me'):
   self.assertEqual(routing.model_for(text)[0],routing.DEEP)

 def test_model_tool_catalog_includes_games_and_preserves_source_guard(self):
  with patch.object(launch,'catalog',return_value=ENTRIES):
   self.assertEqual(launch.tools({'action':'list'})['apps'],ENTRIES)
  with patch.dict(j.status,external_context=True),patch.object(launch,'tools') as tools:
   self.assertIn('error',j.guarded_apps({'action':'open','app':'crimson'}))
   tools.assert_not_called()

 def test_semantic_planner_uses_the_same_game_catalog(self):
  messages=Mock(draft=None);music=Mock();music.intent.return_value=None
  launcher=Mock();launcher.catalog.return_value=ENTRIES;launcher.tools.return_value={'status':'launch_requested'}
  interpret=Mock(return_value=plan('app',app='crimson'))
  tasks=Tasks(interpret,messages,music,Mock(),launcher=launcher)
  result=tasks.requested("Let's play Crimson Desert",'local_fast',lambda:False)
  self.assertIn('Crimson Desert Enhanced',result['reply'])
  launcher.tools.assert_called_once_with({'action':'open','app':'crimson'})
  self.assertIn('Crimson Desert',interpret.call_args.args[2][0]['aliases'])

 def test_literal_game_match_excludes_mod_manager_and_unrelated_apps(self):
  apps=[{'id':k,'name':v['name'],'aliases':v['aliases']} for k,v in ENTRIES.items()]
  apps.append({'id':'kernel','name':'CachyOS Kernel Manager'})
  self.assertEqual([a['id'] for a in relevant_apps('I fancy a game of Crimson Desert',apps)],['crimson'])
  self.assertEqual(relevant_apps('tell me a joke',apps),[])

 def test_even_an_installed_app_is_rejected_when_not_relevant(self):
  messages=Mock(draft=None);music=Mock();music.intent.return_value=None
  launcher=Mock();launcher.catalog.return_value=ENTRIES
  interpret=Mock(return_value=plan('app',app='dmm'))
  tasks=Tasks(interpret,messages,music,Mock(),launcher=launcher)
  result=tasks.requested('I fancy a game of Crimson Desert','local_fast',lambda:False)
  self.assertIn('did not match',result['reply']);launcher.tools.assert_not_called()

 def test_large_agent_cannot_substitute_mod_manager_for_named_game(self):
  with patch.object(j,'current_request','Start Crimson Desert'),patch.dict(j.status,external_context=False),patch.object(launch,'catalog',return_value=ENTRIES),patch.object(launch,'tools') as tools:
   self.assertIn('error',j.guarded_apps({'action':'open','app':'dmm'}))
   tools.assert_not_called()

class Shortcuts(unittest.TestCase):
 def test_saved_unsigned_appid_becomes_steam_gameid(self):
  raw=b'\0shortcuts\0\x000\0\x02appid\0'+struct.pack('<I',3500846935)+b'\x01AppName\0Begin Again\0\x01Exe\0untrusted command never exposed\0\x08\x08\x08'
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'user/config';p.mkdir(parents=True);(p/'shortcuts.vdf').write_bytes(raw)
   result=steam_shortcuts.games(Path(d))
  gameid=str((3500846935<<32)|0x02000000)
  self.assertEqual(result[gameid]['name'],'Begin Again')
  self.assertNotIn('command',json.dumps(result))

 def test_truncated_and_unsupported_catalogues_do_not_produce_games(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'user/config';p.mkdir(parents=True)
   for raw in (b'\0shortcuts\0\x000\0\x02appid\0\xff',b'\0shortcuts\0\x0fno\0'):
    (p/'shortcuts.vdf').write_bytes(raw);self.assertEqual(steam_shortcuts.games(Path(d)),{})

if __name__=='__main__':unittest.main()
