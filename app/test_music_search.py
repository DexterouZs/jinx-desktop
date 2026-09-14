import unittest,json
from unittest.mock import patch,Mock
from music_search import Search,metadata
from test_task_understanding import TasksTest,plan
from test_music_tools import FakeSpotify
import music_tools
TRACK={'title':'Call on Me','artist':'Eric Prydz','uri':'spotify:track:'+'a'*22,'url':'https://open.spotify.com/track/'+'a'*22}
class SearchTests(unittest.TestCase):
 def find(self,artist,tracks):
  urls=['https://open.spotify.com/track/'+str(i)*22 for i in range(len(tracks))]
  with patch('music_search.subprocess.run',return_value=Mock(returncode=0,stdout=json.dumps(urls))),patch('music_search.metadata',side_effect=tracks):return Search().find('Call on Me',artist)
 def test_exact_artist_is_ready(self):self.assertFalse(self.find('Eric Prydz',[TRACK])['confirm_artist'])
 def test_transcribed_artist_needs_confirmation(self):self.assertTrue(self.find('Eric Price',[TRACK])['confirm_artist'])
 def test_wrong_artist_not_played(self):
  with self.assertRaises(ValueError):self.find('Adele',[TRACK])
 def test_multiple_artists_not_guessed(self):
  with self.assertRaisesRegex(ValueError,'more than one'):self.find('',[TRACK,{**TRACK,'artist':'Other Artist'}])
 def test_non_spotify_urls_never_fetched(self):
  with patch('music_search.urllib.request.urlopen') as fetch:
   for url in ['http://127.0.0.1/track/'+('a'*22),'https://open.spotify.com.evil.test/track/'+('a'*22)]:
    with self.assertRaises(ValueError):metadata(url)
   fetch.assert_not_called()
 def test_old_playing_track_cannot_verify_new_requested_track(self):
  with FakeSpotify(running=True,ready_at=0,accept_play=1) as fake:
   real=fake.run
   def ignore_uri(argv):
    result=real(argv)
    if argv[3:] and argv[3].endswith('OpenUri'):fake.track='spotify:track:'+('b'*22)
    return result
   with patch.object(music_tools.system,'run',side_effect=ignore_uri):
    with self.assertRaisesRegex(ValueError,'did not confirm playback'):music_tools.perform({'action':'uri','uri':TRACK['uri']})
   fake.audit.assert_not_called()
class MusicDialogue(TasksTest):
 def test_artist_clarification_then_yes_plays_only_verified_uri(self):
  self.tasks.search.find.return_value={**TRACK,'confirm_artist':True}
  result=self.request('Play Call on Me from Eric Price on Spotify',plan('music',music_action='search',song='Call on Me',artist='Eric Price'))
  self.assertIn('Eric Prydz',result['reply']);self.music.perform.assert_not_called()
  self.tasks.requested('yes','auto',lambda:False)
  self.music.perform.assert_called_once_with({'action':'uri','uri':TRACK['uri']})
 def test_cancelled_match_never_plays(self):
  self.tasks.search.find.return_value={**TRACK,'confirm_artist':True}
  self.request('Play Call on Me',plan('music',music_action='search',song='Call on Me'))
  self.tasks.requested('cancel','auto',lambda:False)
  self.tasks.requested('yes','auto',lambda:False)
  self.music.perform.assert_not_called()

class NamedPlanConsistency(unittest.TestCase):
 def test_model_play_label_with_song_is_search_not_resume(self):
  from task_understanding import validate
  p=validate(plan('music',music_action='play',song='Call on Me',artist='Eric Price'))
  self.assertEqual(p['music_action'],'search')
