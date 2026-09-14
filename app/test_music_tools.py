import jinx_test_support  # Isolate state and memory before importing jinx.
import unittest
from unittest.mock import patch
from contextlib import ExitStack
import json
import music_tools as m
import jinx as j

class Music(unittest.TestCase):
 def test_favourites_and_typo(self):
  for text in ['Play my favorite songs on spottify','Could you play my favourite songs on Spotify?','Play my liked songs','Jinx, can you play my favourite music on Spotify?','My favorite music on Spotify, please.','Jinx, my favourite songs, please.','Please, play my favourite music on Spotify.','My liked songs on Spotify']:
   self.assertEqual(m.intent(text),{'action':'favourites'})
  self.assertEqual(m.intent('Could you please play my favourite music for me on Spotify?'),{'action':'favourites'})
  for text in ['Can you play me on a favourite music on Spotify?','Play some of my favourite songs on Spotify','Could you put on my liked music?']:
   self.assertEqual(m.intent(text),{'action':'favourites'})
 def test_spoken_fragment_is_accepted_by_the_same_model_tool_guard(self):
  with patch.dict(j.status,{'external_context':False}),patch.object(j,'current_request','My favorite music on Spotify, please.'),patch.object(m,'perform',return_value={'reply':'Playing test'}) as perform:
   self.assertEqual(j.guarded_music({'action':'favourites'}),{'reply':'Playing test'})
   perform.assert_called_once_with({'action':'favourites'})
 def test_expected_failure_becomes_a_concrete_voice_reply(self):
  with patch.object(m,'perform',side_effect=ValueError('Spotify needs sign-in.')),patch.object(m.system,'audit'):
   result=m.requested('Play my favourite music on Spotify')
   self.assertIn('Spotify needs sign-in.',result['reply']);self.assertTrue(result['music_failed'])
 def test_negated_quoted_unrelated_and_source_tasks_do_not_play(self):
  for text in ['Do not play my favourite songs','Explain the phrase play my favourite songs','Read this page and play music','Install Spotify','Shuffle my favourite songs','Do not play my favourite music on Spotify, please.','What are my favourite songs on Spotify?','Read this sentence: my favourite songs on Spotify, please.']:
   self.assertIsNone(m.intent(text))
 def test_uri_validation(self):
  good='https://open.spotify.com/track/'+'a'*22+'?si=share'
  self.assertEqual(m.normal_uri(good),'spotify:track:'+'a'*22)
  for bad in ['file:///etc/passwd','https://evil.test/track/'+'a'*22,'spotify:track:a;id']:
   with self.assertRaises(ValueError):m.normal_uri(bad)
 def test_claims_playback_only_after_advancing_position(self):
  base={'state':'Playing','title':'Test','artist':'Artist','track':'track','position_us':100}
  with patch.object(m,'ensure_started',return_value=False),patch.object(m,'call'),patch.object(m,'status',side_effect=[base,base,{**base,'position_us':500000}]),patch.object(m.time,'sleep'),patch.object(m.system,'audit'):
   self.assertEqual(m.perform({'action':'play'})['reply'],'Playing Test by Artist.')
 def test_stalled_or_empty_playback_is_failure(self):
  for state in [{'state':'Stopped','title':'','artist':'','track':'','position_us':0},{'state':'Playing','title':'Test','artist':'','track':'x','position_us':100}]:
   with patch.object(m,'ensure_started',return_value=False),patch.object(m,'call'),patch.object(m,'wait_ready'),patch.object(m,'status',return_value=state),patch.object(m.time,'sleep'),self.assertRaisesRegex(ValueError,'did not confirm playback'):
    m.perform({'action':'play'})
 def test_source_blocked_and_model_cannot_substitute_user_action(self):
  with patch.dict(j.status,{'external_context':True}),patch.object(m.system,'audit'),self.assertRaises(ValueError):j.guarded_music({'action':'play'})
  with patch.dict(j.status,{'external_context':False}),patch.object(j,'current_request','Pause music'),patch.object(m,'perform') as perform:
   j.guarded_music({'action':'next'})
   perform.assert_called_once_with({'action':'pause'})
 def test_model_play_alias_resolves_the_requested_collection_without_a_retry_loop(self):
  with patch.dict(j.status,{'external_context':False}),patch.object(j,'current_request','Can you play me on a favourite music on Spotify?'),patch.object(m,'perform') as perform:
   j.guarded_music({'action':'play'})
   perform.assert_called_once_with({'action':'favourites'})
 def test_negative_or_source_language_never_authorises_fallback(self):
  for text in ['Do not play music','Explain the phrase play music','Read this article and play music','Please do not play my favourite songs']:
   with self.assertRaises(ValueError):m.authorised({'action':'play'},text)


class FakeSpotify:
 """All process, configuration, audit and clock operations stay in memory."""
 def __init__(self, running=False, accept_play=2, ready_at=.5, advance=True):
  self.running=running;self.accept_play=accept_play;self.ready_at=ready_at
  self.advance=advance;self.now=0.;self.state='Paused';self.calls=[];self.launches=0
  self.plays=[];self.opened_at=None;self.started_at=0.;self.track='spotify:track:'+('b'*22)
 def sleep(self, seconds):self.now+=seconds
 def launch(self, args):
  self.launches+=1;self.running=True
  return {'status':'launch_requested'}
 def run(self, argv):
  self.calls.append((self.now,argv))
  if argv==['qdbus6']:output=m.BUS if self.running else ''
  else:
   assert argv[:3]==['qdbus6',m.BUS,m.PATH],argv
   member=argv[3].removeprefix(m.PLAYER)
   ready=self.now>=self.ready_at
   output=''
   if member=='CanPlay':output='true' if ready else 'false'
   elif member=='Metadata':output='xesam:title: Test\nxesam:artist: Artist\nxesam:url: '+self.track if ready else ''
   elif member=='PlaybackStatus':output=self.state
   elif member=='Position':output=str(int((self.now-self.started_at)*1000000) if self.state=='Playing' and self.advance else 100)
   elif member=='OpenUri':self.opened_at=self.now;self.state='Paused';self.track=argv[4]
   elif member=='Play':
    self.plays.append(self.now)
    if self.accept_play is not None and len(self.plays)>=self.accept_play:
     self.state='Playing';self.started_at=self.now
   else:raise AssertionError(member)
  return {'ok':True,'output':output}
 def __enter__(self):
  self.stack=ExitStack()
  for target,name,kwargs in [(m.system,'run',{'side_effect':self.run}),
                            (m.system,'desktop_apps',{'side_effect':self.launch}),
                            (m.time,'sleep',{'side_effect':self.sleep}),
                            (m.time,'monotonic',{'side_effect':lambda:self.now}),
                            (m,'CONFIG',{})]:
   mocked=self.stack.enter_context(patch.object(target,name,**kwargs))
   if name=='CONFIG':mocked.read_text.return_value=json.dumps({'favourites_uri':'spotify:user:test:collection'})
  self.audit=self.stack.enter_context(patch.object(m.system,'audit'))
  return self
 def __exit__(self,*args):return self.stack.__exit__(*args)

class SpotifyRepair(unittest.TestCase):
 def test_spoken_acknowledgements_and_qualifiers(self):
  for text in ['Alright. Can you play on Spotify in my favourite music right now?',
               'play my favourite music on spotify now','can you put on my liked songs please',
               'spotify play my favourites',
               'Okay! Well, Jinx, please play my favourites right now for me on Spotify please']:
   with self.subTest(text=text):self.assertEqual(m.intent(text),{'action':'favourites'})
  for word in ['alright','all right','okay','ok','right','so','well','hey','hi','hello','jinx']:
   self.assertEqual(m.request_text(word),word)
   self.assertEqual(m.request_text(word+'! play music'),'play music')
 def test_song_names_negation_and_unknown_artists_do_not_dispatch(self):
  for text in ['play the song called right now',"don't play my favourite music",'play favourite music by adele']:
   with self.subTest(text=text),patch.object(m,'perform') as perform:
    self.assertIsNone(m.intent(text));self.assertIsNone(m.requested(text));perform.assert_not_called()
 def test_cold_client_ignores_first_play_then_advances(self):
  with FakeSpotify() as fake:
   result=m.perform({'action':'favourites'})
   self.assertEqual(result['reading']['state'],'Playing')
   self.assertGreater(result['reading']['position_us'],0)
   self.assertEqual(fake.launches,1);self.assertEqual(len(fake.plays),2)
   self.assertEqual(fake.opened_at,0,'Send the requested collection without requiring an old track')
   self.assertAlmostEqual(fake.plays[0]-fake.opened_at,.8)
   self.assertGreaterEqual(fake.plays[1]-fake.plays[0],1.5)
   fake.audit.assert_called_once_with('spotify',{'action':'favourites','verified':True})
 def test_ignored_play_fails_and_guard_audits_reason(self):
  with FakeSpotify(accept_play=None) as fake,patch.dict(j.status,{'external_context':False}),patch.object(j,'current_request','Play my favourites'):
   with self.assertRaisesRegex(ValueError,'^Spotify playback not confirmed: Spotify did not confirm playback'):
    j.guarded_music({'action':'favourites'})
   self.assertEqual(fake.launches,1);self.assertEqual(len(fake.plays),4)
   self.assertGreaterEqual(fake.now-fake.plays[0],20)
   self.assertLess(fake.now-fake.plays[0],20.5)
   event=fake.audit.call_args.args
   self.assertEqual(event[0],'spotify');self.assertFalse(event[1]['verified'])
   self.assertEqual(event[1]['action'],'favourites');self.assertLessEqual(len(event[1]['error']),120)
   fake.audit.assert_called_once()
 def test_warm_bus_never_relaunches_and_resume_is_fast(self):
  with FakeSpotify(running=True,ready_at=0,accept_play=1) as fake:
   m.perform({'action':'play'})
   self.assertEqual(fake.launches,0);self.assertLess(fake.now,1)
   self.assertFalse(any(argv[-1]==m.PLAYER+'CanPlay' for _,argv in fake.calls))
 def test_warm_uri_retries_without_relaunch(self):
  with FakeSpotify(running=True,ready_at=0) as fake:
   m.perform({'action':'uri','uri':'spotify:track:'+'a'*22})
   self.assertEqual(fake.launches,0);self.assertEqual(len(fake.plays),2)
   self.assertAlmostEqual(fake.plays[0]-fake.opened_at,.8)
 def test_existing_bus_without_metadata_waits_for_readiness(self):
  with FakeSpotify(running=True,ready_at=1) as fake:
   m.perform({'action':'play'})
   self.assertEqual(fake.launches,0);self.assertGreaterEqual(fake.plays[0],1)
 def test_unready_client_times_out_without_play(self):
  with FakeSpotify(ready_at=100) as fake:
   with self.assertRaisesRegex(ValueError,'controls and track metadata are not ready'):m.perform({'action':'play'})
   self.assertEqual(fake.launches,1);self.assertEqual(fake.plays,[])
   self.assertAlmostEqual(fake.now,15)
 def test_playing_with_stalled_position_still_fails(self):
  with FakeSpotify(running=True,ready_at=0,accept_play=1,advance=False) as fake:
   with self.assertRaisesRegex(ValueError,'did not confirm playback'):m.perform({'action':'play'})
   fake.audit.assert_not_called()

class EmptySpotifyRegression(unittest.TestCase):
 def test_empty_player_can_receive_explicit_item(self):
  with FakeSpotify(running=True,ready_at=1,accept_play=1) as fake:
   result=m.perform({'action':'uri','uri':'spotify:track:'+'a'*22})
   self.assertEqual(fake.opened_at,0)
   self.assertEqual(result['reading']['state'],'Playing')
 def test_combined_open_play(self):
  self.assertEqual(m.intent('Open Spotify and play my liked songs'),{'action':'favourites'})

class NoKeyRegression(unittest.TestCase):
 def test_more_everyday_requests(self):
  for text in ['Launch Spotify and play my liked songs','Start Spotify and then play my favorite music','Play my music on spottify']:
   self.assertEqual(m.intent(text),{'action':'favourites'})
  for text in ['Play songs on Spotify','Start music','Put on music']:
   self.assertEqual(m.intent(text),{'action':'play'})
 def test_named_request_explains_limit_without_attempting_playback(self):
  with patch.object(m,'perform') as perform:
   result=m.requested('Play a song by Adele on Spotify')
   self.assertIn('does not need an API key',result['reply'])
   self.assertIn('Spotify link',result['reply']);perform.assert_not_called()
 def test_negative_source_and_unrelated_requests_are_not_intercepted(self):
  for text in ['Do not play Adele on Spotify','Read this page and play Spotify','Explain Spotify API keys','Install Spotify','Play chess']:
   self.assertIsNone(m.requested(text))
 def test_music_guidance_is_in_actual_prompt(self):
  import jinx_skills
  self.assertIn('Never ask for an API key',jinx_skills.brief_for_request('play music'))
