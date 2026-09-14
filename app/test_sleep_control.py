import json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
import sleep_control as s

class SleepControlTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  root=Path(self.tmp.name);self.flag=root/'sleep.json'
  self.controls=Mock();self.original=[{'id':43,'plugin':'local.cybercity.afterhours','paused':False}]
  self.controls.wallpapers.return_value=self.original
  for p in [patch.object(s,'RUNTIME',root),patch.object(s,'FLAG',self.flag),patch.object(s,'desktop_controls',return_value=self.controls),patch.object(s.subprocess,'run')]:
   value=p.start();self.addCleanup(p.stop)
  self.run=value
 def test_sleep_preserves_wallpaper_choice_and_stops_ai(self):
  s.apply(True)
  self.assertEqual(json.loads(self.flag.read_text())['wallpapers'],self.original)
  self.controls.set_wallpapers.assert_called_once_with(self.original,True)
  self.assertEqual(self.run.call_args.args[0],['systemctl','--user','stop','jinx.service','jinx-model.service'])
 def test_repeated_sleep_does_not_overwrite_saved_wallpaper_state(self):
  s.apply(True);self.controls.wallpapers.return_value=[{**self.original[0],'paused':True}];s.apply(True)
  self.assertEqual(json.loads(self.flag.read_text())['wallpapers'],self.original)
 def test_wake_restores_exact_saved_state(self):
  self.flag.write_text(json.dumps({'wallpapers':self.original}));s.apply(False)
  self.controls.set_wallpapers.assert_called_once_with(self.original)
  self.assertFalse(self.flag.exists())
 def test_failed_restore_keeps_sleep_marker_and_stops_started_services(self):
  self.flag.write_text(json.dumps({'wallpapers':self.original}));self.controls.set_wallpapers.side_effect=RuntimeError('Plasma unavailable')
  with self.assertRaises(RuntimeError):s.apply(False)
  self.assertTrue(self.flag.exists());self.assertEqual(self.run.call_args.args[0][2],'stop')
 def test_wallpaper_failure_cannot_prevent_ai_shutdown(self):
  self.controls.set_wallpapers.side_effect=RuntimeError('Plasma unavailable')
  with self.assertRaises(RuntimeError):s.apply(True)
  self.assertTrue(self.flag.exists());self.assertEqual(self.run.call_args.args[0][2],'stop')

if __name__=='__main__':unittest.main()
