import hashlib,io,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import reviewed_apps as r
import software_installer as s

class ReviewedApps(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  root=Path(self.temp.name);self.body=b'reviewed fixture binary'
  for name,value in [('APP',root/'apps/ZapZap.AppImage'),('DESKTOP',root/'applications/whatsapp.desktop'),('SIZE',len(self.body)),('SHA256',hashlib.sha256(self.body).hexdigest())]:
   patcher=patch.object(r,name,value);patcher.start();self.addCleanup(patcher.stop)
 def test_checksum_verified_before_executable_and_launcher(self):
  with patch.object(r.urllib.request,'urlopen',return_value=io.BytesIO(self.body)):r.install()
  self.assertTrue(r.verified());self.assertEqual(r.plan({})['status'],'already_installed')
 def test_bad_download_does_not_install_anything(self):
  with patch.object(r.urllib.request,'urlopen',return_value=io.BytesIO(b'wrong content')),self.assertRaises(ValueError):r.install()
  self.assertFalse(r.APP.exists());self.assertFalse(r.DESKTOP.exists())
 def test_existing_launcher_preserved(self):
  r.DESKTOP.parent.mkdir();r.DESKTOP.write_text('user owned launcher')
  with self.assertRaises(ValueError):r.plan({})
  self.assertEqual(r.DESKTOP.read_text(),'user owned launcher')
 def test_url_or_digest_substitution_rejected(self):
  plan=r.plan({})
  for field,value in [('url','https://evil.example/app'),('sha256','0'*64)]:
   with self.assertRaises(ValueError):s.validate_plan({**plan,field:value})

if __name__=='__main__':unittest.main()
