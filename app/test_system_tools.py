import json,unittest
from unittest.mock import patch
import system_tools as s
class SystemTools(unittest.TestCase):
 def test_no_shell_or_unlisted_app(self):
  with patch.object(s,'run') as run:
   r=s.desktop_apps({'action':'open','app':'firefox; touch /tmp/jinx-test-injection'})
   self.assertIn('error',r);run.assert_not_called()
 def test_app_launch_is_fixed_desktop_entry(self):
  with patch.object(s,'run',return_value={'ok':True}) as run,patch.object(s,'audit'):
   r=s.desktop_apps({'action':'open','app':'browser'})
   self.assertEqual(r['status'],'launch_requested');argv=run.call_args.args[0]
   self.assertEqual(argv[-2:],['/usr/bin/gtk-launch','firefox.desktop'])
   self.assertFalse(any(x in argv for x in ['sh','bash','-c']))
 def test_log_boot_injection_refused(self):
  with patch.object(s,'run') as run:
   with self.assertRaises(ValueError):s.read_logs({'topic':'kernel','boot':'0; reboot'})
   run.assert_not_called()
 def test_log_volume_capped_and_previous_boot_supported(self):
  with patch.object(s,'run',return_value={'ok':True,'output':'test'}) as run,patch.object(s,'audit'):
   s.read_logs({'topic':'gpu','boot':'previous','lines':99999})
   argv=run.call_args.args[0];self.assertEqual(argv[argv.index('-n')+1],'100');self.assertEqual(argv[argv.index('-b')+1],'-1')
 def test_maintenance_cannot_replace_commands(self):
  with patch.object(s,'run',return_value={'ok':True}) as run,patch.object(s,'audit'):
   s.maintenance({'job':'refresh_dns','commands':[['reboot']]})
   self.assertEqual(run.call_args.args[0],['resolvectl','flush-caches'])
 def test_unlisted_maintenance_refused(self):
  with self.assertRaises(ValueError):s.maintenance_preview({'job':'sudo_shell'})
 def test_failed_maintenance_not_success(self):
  with patch.object(s,'run',return_value={'ok':False,'output':'Permission denied'}),patch.object(s,'audit'):
   with self.assertRaises(RuntimeError):s.maintenance({'job':'refresh_dns'})
 def test_note_path_traversal_unavailable(self):
  self.assertIn('error',s.knowledge({'section':'../../.ssh/id_ed25519'}))
 def test_credential_redaction(self):
  result=s.scrub('Authorization: Bearer abcDEF123 token=privatekey https://user:password@example.com')
  for secret in ['abcDEF123','privatekey','user:password']:self.assertNotIn(secret,result)
if __name__=='__main__':unittest.main()

class Preflight(unittest.TestCase):
 def test_negative_app_request_does_not_launch(self):
  with patch.object(s,'desktop_apps') as launch:
   self.assertEqual(s.preflight_request('Do not open Firefox.'),{});launch.assert_not_called()
 def test_simple_app_request_has_fast_execution(self):
  with patch.object(s,'desktop_apps',return_value={'status':'launch_requested','app':'Firefox'}) as launch:
   self.assertEqual(s.preflight_request('Can you open Firefox for me?')['reply'],'Opening Firefox.')
   launch.assert_called_once_with({'action':'open','app':'firefox'})
 def test_multiple_checks_actually_run(self):
  with patch.object(s,'inspect_system',return_value={'ok':True}) as inspect,patch.object(s,'read_logs',return_value={'ok':True}) as logs:
   r=s.preflight_request('Check my actual current power profile and temperatures, then read recent GPU errors. Do not change anything.')
   inspect.assert_called_once_with({'topic':'power'})
   self.assertTrue(any(c.args[0]['topic']=='gpu' for c in logs.call_args_list));self.assertTrue(r['observations'])
