import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('installer',ROOT/'install.py')
installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)


class InstallerTests(unittest.TestCase):
    def test_fresh_install_seeds_private_auth_before_widget_start(self):
        with tempfile.TemporaryDirectory() as folder:
            home=Path(folder)
            with patch.object(installer,'run'):
                installer.configure(home/'Jinx',home,home/'backup')
            key=home/'.local/state/jinx/access.key'
            self.assertEqual(len(key.read_text().strip()),64)
            self.assertEqual(key.stat().st_mode & 0o777,0o600)

    def test_configure_preserves_private_settings_and_backs_up_existing_units(self):
        with tempfile.TemporaryDirectory() as folder:
            home=Path(folder);state=home/'.local/state/jinx';state.mkdir(parents=True)
            saved={'voice':'breeze_tts2','memory':'Synthetic retained fact'}
            (state/'state.json').write_text(json.dumps(saved))
            key=state/'access.key';key.write_text('synthetic-local-access')
            unit=home/'.config/systemd/user/jinx.service';unit.parent.mkdir(parents=True);unit.write_text('previous unit')
            backup=home/'backup'
            with patch.object(installer,'run') as run:
                installer.configure(home/'Jinx',home,backup)
            self.assertEqual(json.loads((state/'state.json').read_text()),saved)
            self.assertEqual(key.read_text(),'synthetic-local-access')
            self.assertEqual((backup/'.config/systemd/user/jinx.service').read_text(),'previous unit')
            commands=[list(call.args[0]) for call in run.call_args_list]
            self.assertEqual(commands,[['systemctl','--user','daemon-reload'],['systemctl','--user','enable','--now','jinx-reminders.timer']])
            reminder=(home/'.config/systemd/user/jinx-reminders.service').read_text()
            self.assertIn('reminder_delivery.py',reminder)
            self.assertNotIn('jinx.py',reminder)
            self.assertNotIn('WantedBy',unit.read_text())

    def test_failed_asset_download_preserves_existing_asset(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'model.bin';target.write_bytes(b'existing')
            with patch.object(installer.urllib.request,'urlopen',side_effect=OSError('offline')):
                with self.assertRaises(OSError):installer.download({'url':'https://example.invalid/model','sha256':'0'*64},target)
            self.assertEqual(target.read_bytes(),b'existing')
            self.assertFalse(target.with_suffix('.bin.download').exists())

    def test_incomplete_payload_is_detectable(self):
        for filename in ('app/ui.html','app/avatar3d/native/main.qml','app/avatar3d/native/attention.qml',
                         'app/installer/main.qml','app/software_knowledge.json','docs/jinx.jpg','assets.json','starter-avatar.json'):
            self.assertTrue((ROOT/filename).is_file(),filename)


if __name__=='__main__':unittest.main()
