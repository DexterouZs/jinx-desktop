import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('release_check',Path(__file__).resolve().parents[1]/'scripts/check-release.py')
check=importlib.util.module_from_spec(spec);spec.loader.exec_module(check)

class ReleasePrivacy(unittest.TestCase):
 def test_private_files_rejected_even_without_recognisable_tokens(self):
  for name in ['personal-profile/profile.json','private/service.token','state.json','auth.json','contacts.json','profile/Cookies','.env.production','voice/reference.wav']:
   with self.subTest(name=name):self.assertIn('private/runtime file',check.inspect(name,b'{}'))
 def test_arbitrary_saved_credential_is_detected_without_echo(self):
  value=b'fictional-test-value-12345'
  reasons=check.inspect('app/example.py',b'password='+value,[value])
  self.assertIn('exact local credential match',reasons)
  self.assertNotIn(value.decode(),str(reasons))
 def test_source_and_installer_are_allowed(self):
  for name in ['app/morgen_tools.py','windows/profile.py','docs/WINDOWS.md','assets.json']:
   self.assertEqual(check.inspect(name,b'ordinary source'),[])
 def test_token_boundary_does_not_flag_license_names(self):
  self.assertEqual(check.inspect('LICENSE.txt',b'Asterisk-linking-protocols-exception'),[])
if __name__=='__main__':unittest.main()
