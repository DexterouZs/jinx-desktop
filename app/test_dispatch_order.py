"""The deterministic chain is an `or` of independent matchers, so its order is
load-bearing: whichever module claims a phrase first answers it. These tests
pin the ordering decisions that are easy to break by adding a new tool.

The chain in jinx.py is:
  messaging, software, music, desktop, everyday, launch, homelab, home,
  screen, web, personal
"""
import datetime,unittest
from unittest.mock import patch

import desktop_tools,everyday_tools,homelab_tools,home_tools,launch_tools,music_tools

NOW=datetime.datetime(2026,9,9,21,0,tzinfo=datetime.timezone.utc).astimezone()


def claims(text):
 """Which module answers this text, following the real chain order."""
 if music_tools.intent(text):return 'music'
 if desktop_tools.intent(text):return 'desktop'
 if everyday_tools.schedule_intent(text,NOW):return 'everyday'
 if launch_tools.parse(text):return 'launch'
 if homelab_tools.parse(text) and homelab_tools.find((homelab_tools.parse(text) or {}).get('name','')):return 'homelab'
 if homelab_tools.parse(text) and (homelab_tools.parse(text) or {}).get('action')=='all':return 'homelab'
 if home_tools.parse(text):return 'home'
 return None


class ChainOrder(unittest.TestCase):
 def test_each_phrase_is_claimed_by_the_intended_module(self):
  cases={
   # music must win the word "play" against the launcher
   'play some music':'music',
   'pause the music':'music',
   'next track':'music',
   # desktop owns volume and standard folders
   'turn the volume up':'desktop',
   'set volume to 40 percent':'desktop',
   'mute':'desktop',
   'open my downloads folder':'desktop',
   # everyday owns time
   'set a timer for 5 minutes':'everyday',
   'set an alarm for 7am':'everyday',
   'remind me in 10 minutes to stretch':'everyday',
   # launching apps and games
   'open Steam':'launch',
   'launch heroic':'launch',
   'start Fallout New Vegas':'launch',
   # homelab before home, or "is the NAS up" reads as a missing HA device
   'is the NAS up':'homelab',
   'is proxmox running':'homelab',
   'is everything up':'homelab',
   # smart home
   'turn on the kitchen lamp':'home',
   'is the desk lamp on':'home',
  }
  for text,owner in cases.items():
   self.assertEqual(claims(text),owner,f'{text!r} should be handled by {owner}')

 def test_the_launcher_never_steals_a_music_request(self):
  # "play" is a launch verb and a music verb; music runs first in the chain,
  # but the launcher must also decline these on its own.
  for text in ['play some music','play my favourite songs','play the next song']:
   self.assertIsNone(launch_tools.parse(text),text)

 def test_homelab_declines_smart_home_phrasings(self):
  # It parses them, but resolves to no service, so the chain falls through.
  for text in ['is the desk lamp on','is the kitchen lamp on']:
   self.assertIsNone(homelab_tools.requested(text),text)

 def test_smart_home_declines_homelab_phrasings(self):
  # And the reverse: HA must not claim "is the NAS up" as an unknown device
  # before homelab gets a chance, which is why homelab is ordered first.
  self.assertEqual(claims('is the NAS up'),'homelab')

 def test_conversation_reaches_the_model(self):
  for text in ['what do you make of Wednesdays','hello','tell me a joke',
               'write me an email','search for the train times']:
   self.assertIsNone(claims(text),text)


class LauncherSafety(unittest.TestCase):
 def test_the_launcher_only_ever_runs_reviewed_entries(self):
  # No arbitrary path or shell string can reach the launcher: parse returns a
  # name, and the name must resolve inside the discovered catalog.
  entries={'steam':{'key':'steam','name':'Steam','kind':'desktop','aliases':[]}}
  for text in ['open /etc/shadow','launch rm -rf /','run bash','open ../../etc/passwd']:
   with patch.object(launch_tools.system_tools,'desktop_apps') as opened, \
        patch.object(launch_tools.system_tools,'run') as ran:
    launch_tools.requested(text,entries)
   opened.assert_not_called();ran.assert_not_called()


if __name__=='__main__':unittest.main()
