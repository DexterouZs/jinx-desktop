"""Credential-free checks for platform boundaries and private profile imports."""
import importlib.util,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import personal_profile
import windows_shell

class ProfileTests(unittest.TestCase):
 def test_rejects_credentials_before_any_asset_is_changed(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);source=root/'source';source.mkdir()
   (source/'profile.json').write_text(json.dumps({'format':1,'files':{'openai.key':'unused'}}))
   with self.assertRaises(ValueError):personal_profile.import_folder(source,root/'data',root/'models')
   self.assertFalse((root/'data').exists())
 def test_original_assets_verified_and_previous_version_preserved(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);source=root/'source';source.mkdir();data=root/'data';(data/'assets').mkdir(parents=True)
   (data/'assets/reference-short.wav').write_bytes(b'previous fixture')
   for name in ['reference-short.wav','jinx-character.glb']:(source/name).write_bytes(b'fictional asset fixture')
   (source/'profile.json').write_text(json.dumps({'format':1,'files':{p.name:personal_profile.digest(p) for p in source.iterdir()}}))
   personal_profile.import_folder(source,data,root/'models')
   self.assertEqual((data/'assets/reference-short.wav').read_bytes(),b'fictional asset fixture')
   self.assertEqual(next((data/'profile-backups').glob('*/reference-short.wav')).read_bytes(),b'previous fixture')
 def test_bad_checksum_cannot_partially_replace_profile(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);(root/'reference-short.wav').write_bytes(b'fixture')
   (root/'profile.json').write_text(json.dumps({'format':1,'files':{'reference-short.wav':'bad'}}))
   with self.assertRaises(ValueError):personal_profile.import_folder(root,root/'out',root/'models')
   self.assertFalse((root/'out').exists())

class WindowsBoundaryTests(unittest.TestCase):
 def test_commands_cannot_chain_scripts_or_read_credentials(self):
  for text in ['powershell -EncodedCommand hidden','ipconfig & shutdown /s','Get-Content access.key','winget install unknown','ping example.org;whoami','format C:']:
   with self.subTest(text=text),patch('subprocess.Popen') as process:
    result=windows_shell.run(text)
    self.assertFalse(result['ok']);self.assertTrue(result['denied']);process.assert_not_called()

if __name__=='__main__':unittest.main()
