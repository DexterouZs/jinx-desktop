import unittest
from unittest.mock import patch,Mock
import network_state as n
import tempfile
from pathlib import Path
from voices import Voices
class NetworkTests(unittest.TestCase):
 def test_disconnected_skips_cloud(self):
  with patch.object(n,'_cached',(0,True)),patch.object(n.subprocess,'run',return_value=Mock(returncode=0,stdout='none\n')):
   self.assertFalse(n.online())
 def test_unknown_nm_state_still_allows_cloud_attempt(self):
  with patch.object(n,'_cached',(0,True)),patch.object(n.subprocess,'run',side_effect=FileNotFoundError):self.assertTrue(n.online())
 def test_probe_is_cached(self):
  with patch.object(n,'_cached',(0,True)),patch.object(n.subprocess,'run',return_value=Mock(returncode=0,stdout='full\n')) as run:
   self.assertTrue(n.online());self.assertTrue(n.online());run.assert_called_once()
class VoiceResidencyTests(unittest.TestCase):
 def test_breeze_failure_keeps_text_instead_of_changing_speaker(self):
  voice=Voices()
  with tempfile.TemporaryDirectory() as tmp,patch.object(voice.breeze,'synthesise',side_effect=RuntimeError('SD unavailable')),patch.object(voice.jinx,'synthesise') as other:
   with self.assertRaisesRegex(RuntimeError,'SD unavailable'):voice.synthesise('A test sentence.',Path(tmp)/'voice.wav','breeze_tts2')
   other.assert_not_called()
 def test_warming_f5_releases_previously_selected_breeze_first(self):
  voice=Voices();events=[]
  with patch.object(voice.breeze,'release',side_effect=lambda:events.append('release')),patch.object(voice.jinx,'warm',side_effect=lambda:events.append('warm')):
   voice.warm('jinx_local')
  self.assertEqual(events,['release','warm'])
if __name__=='__main__':unittest.main()
