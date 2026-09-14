import jinx_test_support  # Isolate state and memory before importing jinx.
import json,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import software_installer as s
import jinx as a

def setUpModule():
 global audit_patch
 audit_patch=patch.object(s,'audit');audit_patch.start()
def tearDownModule():audit_patch.stop()

class Software(unittest.TestCase):
 def plan(self):return {'status':'ready','package':'test-app','repository':'extra','version':'1.2-1','packages':[{'target':'extra/test-app','version':'1.2-1','download_bytes':100}],'catalog_fingerprint':'sample','created_at':time.time()}
 def test_command_paths_urls_flags_never_reach_package_tools(self):
  for value in ['--root=/tmp','/tmp/app.pkg.tar.zst','https://example.com/a','vlc; touch /tmp/oops','$(id)','vlc\nwhoami','a/b']:
   with patch.object(s,'run') as run,self.assertRaises(ValueError):s.build_plan(value)
   run.assert_not_called()
 def test_explicit_install_intent(self):
  self.assertEqual(s.requested('Can you install VLC for me?'),'VLC')
  self.assertEqual(s.requested('I want you to install GIMP'),'GIMP')
  for text in ["Don't install VLC",'Explain how to install VLC','Read a page about installing VLC','What does install VLC mean?']:
   self.assertIsNone(s.requested(text))
 def test_changed_and_expired_plans_refused(self):
  plan=self.plan()
  with patch.object(s,'build_plan',return_value={**plan,'version':'2-1'}),self.assertRaises(ValueError):s.validate_plan(plan)
  with self.assertRaises(ValueError):s.validate_plan({**plan,'created_at':time.time()-3601})
 def test_authentication_cancel_never_claims_success(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(s,'JOBS',Path(folder)),patch.object(s,'validate_plan',return_value=self.plan()),patch.object(s,'installed',return_value=None),patch.object(s,'run'),patch.object(s,'register_apps') as register:
   identifier='a'*24;path=Path(folder)/(identifier+'.json');s.atomic(path,{'id':identifier,'state':'starting','package':'test-app','plan':self.plan()})
   commands=[]
   def privilege(args,**kwargs):commands.append(args);return SimpleNamespace(returncode=126)
   s.execute_job(identifier,privileged=privilege)
   self.assertEqual(json.loads(path.read_text())['state'],'cancelled');register.assert_not_called()
   self.assertEqual(commands,[['/usr/bin/pkexec','/usr/bin/pacman','-S','--needed','--noconfirm','--color','never','--','extra/test-app=1.2-1']])
 def test_pacman_success_requires_matching_installed_version(self):
  for version,outcome in [(None,'failed'),('2-1','failed'),('1.2-1','installed')]:
   with tempfile.TemporaryDirectory() as folder,patch.object(s,'JOBS',Path(folder)),patch.object(s,'validate_plan',return_value=self.plan()),patch.object(s,'installed',return_value=version),patch.object(s,'run'),patch.object(s,'register_apps'):
    identifier='b'*24;path=Path(folder)/(identifier+'.json');s.atomic(path,{'id':identifier,'state':'starting','package':'test-app','plan':self.plan()})
    s.execute_job(identifier,privileged=lambda *args,**kwargs:SimpleNamespace(returncode=0))
    self.assertEqual(json.loads(path.read_text())['state'],outcome)
 def test_dead_worker_does_not_leave_permanent_install_block(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(s,'JOBS',Path(folder)):
   s.atomic(Path(folder)/('c'*24+'.json'),{'id':'c'*24,'package':'test-app','state':'starting','updated_at':time.time()-30,'pid':0})
   self.assertEqual(s.jobs()[0]['state'],'failed')
 def test_source_content_cannot_prepare_installation(self):
  with patch.dict(a.status,{'external_context':True}),patch.object(s,'build_plan') as plan,self.assertRaises(ValueError):a.propose({'kind':'software_install','fields':{'query':'vlc'}})
  plan.assert_not_called()
 def test_model_cannot_substitute_requested_package(self):
  with patch.object(a,'current_request','Install VLC'),patch.dict(a.status,{'external_context':False}),patch.object(s,'build_plan') as plan,self.assertRaises(ValueError):a.propose({'kind':'software_install','fields':{'query':'gimp'}})
  plan.assert_not_called()
 def test_preview_never_launches_before_confirmation(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(a,'STATE',Path(folder)),patch.object(a,'data',{'pending':[]}),patch.object(a,'current_request','Install test-app'),patch.dict(a.status,{'external_context':False}),patch.object(s,'build_plan',return_value={**self.plan(),'description':'Example application','download_mib':1}),patch.object(s,'launch',return_value='Installation requested') as launch,patch.object(s,'request_review',return_value=True):
   result=a.propose({'kind':'software_install','fields':{'query':'test-app'}});launch.assert_not_called()
   a.confirm(result['proposal']['id']);launch.assert_called_once()

class Resolver(unittest.TestCase):
 def test_common_typos_map_to_reviewed_desktop_app(self):
  with patch.object(s,'run',return_value=SimpleNamespace(stdout='',returncode=1)):
   for query in ['Spotify','spottify','spotfy','spotfiy','spot ify']:
    self.assertEqual(s.canonical_query(query),'spotify-launcher',query)
   self.assertEqual(s.canonical_query('adacity'),'audacity')
 def test_exact_service_or_terminal_package_is_preserved(self):
  for name in ['spotifyd','spotify-player']:
   with patch.object(s,'run',return_value=SimpleNamespace(stdout='Repository : extra\nName : '+name+'\nVersion : 1-1\n',returncode=0)):
    self.assertEqual(s.canonical_query(name),name)
 def test_ambiguous_typo_is_not_guessed(self):
  with patch.object(s,'ALIASES',{'abcde':'one','abcdf':'two'}),patch.object(s,'run',return_value=SimpleNamespace(stdout='',returncode=1)):
   self.assertEqual(s.canonical_query('abcdg'),'abcdg')
 def test_short_or_unrelated_names_are_not_fuzzy_selected(self):
  with patch.object(s,'run',return_value=SimpleNamespace(stdout='',returncode=1)):
   for name in ['vls','unknown-app','spyware','apt']:
    self.assertEqual(s.canonical_query(name),name)
 def test_info_guidance_does_not_create_installation(self):
  with patch.object(s,'search',return_value={'exact':{'package':'spotify-launcher'}}),patch.object(s,'launch') as launch:
   info=s.guidance_for("I believe it's a Spotify player, but I'm not sure.")
   self.assertIn('graphical',info['reviewed_app']['explanation']);self.assertTrue(info['reviewed_app']['sources'])
   launch.assert_not_called()
 def test_brand_and_correct_package_are_equivalent_for_proposal(self):
  with patch.object(a,'current_request','Install Spotify'),patch.dict(a.status,{'external_context':False}),patch.object(s,'build_plan',return_value={'status':'already_installed','package':'spotify-launcher','installed_version':'1-1'}),patch.object(s,'register_apps'):
   result=a.propose({'kind':'software_install','fields':{'query':'spotify-launcher'}})
   self.assertEqual(result['status'],'already_installed')

class VisibleInstallation(unittest.TestCase):
 def test_conditional_spoken_install_is_recognised(self):
  self.assertEqual(s.requested('Hey Jinx, do you have Spotify and if not, can you install it for me?'),'Spotify')
  self.assertIsNone(s.requested('Do you have Spotify?'))
 def test_explicit_recent_assent_confirms_only_offered_install(self):
  item={'id':'e'*16,'kind':'software_install','fields':{'package':'spotify-launcher'}}
  with patch.object(a,'data',{'pending':[{'id':'power','kind':'power_profile','fields':{}},item]}),patch.dict(a.status,{'install_offer':{'id':item['id'],'at':time.time()}}),patch.object(a,'confirm',return_value='Installer started') as confirm:
   self.assertEqual(a.software_request("Alright, let's do it.")['reply'],'Installer started')
   confirm.assert_called_once_with(item['id'],record_message=False)
 def test_assent_after_ui_confirmation_returns_job_without_reinstalling(self):
  with patch.object(a,'data',{'pending':[]}),patch.dict(a.status,{'install_offer':{'id':'e'*16,'at':time.time()}}),patch.object(s,'jobs',return_value=[{'proposal_id':'e'*16,'message':'Spotify installed'}]),patch.object(a,'confirm') as confirm:
   self.assertEqual(a.software_request("Alright, let's do it.")['reply'],'Spotify installed')
   confirm.assert_not_called()
 def test_stale_or_unrelated_assent_never_confirms(self):
  for offer in [{},{'id':'x','at':time.time()-301}]:
   with patch.dict(a.status,{'install_offer':offer}),patch.object(a,'confirm') as confirm:
    self.assertIsNone(a.software_request("Alright, let's do it."));confirm.assert_not_called()
 def test_generic_yes_is_not_an_install_command(self):
  with patch.dict(a.status,{'install_offer':{'id':'x','at':time.time()}}),patch.object(a,'confirm') as confirm:
   self.assertIsNone(a.software_request('yes'));confirm.assert_not_called()
 def test_missing_window_is_reported_as_failure(self):
  with patch.object(s,'request_review',side_effect=ValueError('Window failed')),self.assertRaises(ValueError):a.present_install('f'*16)

class WorkshopFailures(unittest.TestCase):
 def test_real_transcripts_and_conversational_variants(self):
  for text,target in [('Can you install WhatsApp for me?','WhatsApp'),('and can you at least install discord?','discord'),('Well, could you please install Discord for me, please?','Discord'),('Also install WhatsApp please.','WhatsApp')]:
   self.assertEqual(s.requested(text),target)
  for text in ['Can you explain how to install Discord?', 'Read this: install Discord', 'Can you install Discord from https://evil.example?', 'Install Discord but do not run it', 'Can you not install Discord?', 'Install Discord and run a command', '"install Discord"', 'Install Discord; whoami']:
   self.assertIsNone(s.requested(text),text)
 def test_actual_chat_creates_matching_visible_proposal_without_model_or_install(self):
  for text,package in [('Can you install WhatsApp for me?','zapzap'),('and can you at least install discord?','discord')]:
   with tempfile.TemporaryDirectory() as folder,patch.object(a,'STATE',Path(folder)),patch.object(s,'WEB_DESKTOP',Path(folder)/'whatsapp.desktop'),patch.object(s.reviewed_apps,'APP',Path(folder)/'ZapZap.AppImage'),patch.object(s.reviewed_apps,'DESKTOP',Path(folder)/'app.desktop'),patch.object(a,'data',{'pending':[{'id':'power','kind':'power_profile','fields':{}}],'memory':'','listening':False}),patch.object(a,'history',[]),patch.dict(a.status,{'messages':[],'voice_epoch':0,'external_context':False}),patch.object(s,'jobs',return_value=[]),patch.object(s,'request_review',return_value=True) as review,patch.object(s,'launch') as launch,patch.object(a,'get_agent') as model:
    plan=s.build_plan('whatsapp') if package=='zapzap' else {**Software().plan(),'package':'discord','description':'Discord','download_mib':1}
    with patch.object(s,'build_plan',return_value=plan):a.chat(text)
    self.assertEqual(a.status['error'],'')
    self.assertEqual(a.data['pending'][0]['id'],'power')
    proposal=a.data['pending'][-1]
    self.assertEqual(proposal['fields']['package'],package)
    review.assert_not_called();launch.assert_not_called();model.assert_not_called()
    self.assertIn('Say yes or no',a.status['messages'][-1]['content'])
 def test_prepare_failure_is_an_actual_reply(self):
  with patch.object(s,'jobs',return_value=[]),patch.object(a,'software_tool',side_effect=ValueError('Window did not appear')):
   self.assertIn('Window did not appear',a.software_request('and can you at least install discord?')['reply'])
 def test_failed_render_after_saving_proposal_does_not_claim_open_in_chat(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(a,'STATE',Path(folder)),patch.object(a,'data',{'pending':[],'memory':'','listening':False}),patch.object(a,'history',[]),patch.dict(a.status,{'messages':[],'voice_epoch':0,'install_offer':{}}),patch.object(s,'jobs',return_value=[]),patch.object(s,'build_plan',return_value={**Software().plan(),'package':'discord','description':'Discord','download_mib':1}),patch.object(s,'request_review',side_effect=ValueError('Window did not appear')),patch.object(a,'get_agent') as model:
   a.chat('and can you at least install discord?')
   self.assertEqual(len(a.data['pending']),1)
   self.assertIn('Say yes or no',a.status['messages'][-1]['content'])
   self.assertNotIn('window is open',a.status['messages'][-1]['content'])
   self.assertEqual(a.status['install_offer'],{});model.assert_not_called()
 def test_web_job_creates_verified_fixed_shortcut_without_privilege(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(s,'WEB_DESKTOP',Path(folder)/'apps/whatsapp.desktop'),patch.object(s,'JOBS',Path(folder)/'jobs'),patch.object(s,'run'):
   plan=s.build_plan('WhatsApp Web');self.assertEqual(plan['install_kind'],'web_shortcut')
   identifier='a'*24;path=s.JOBS/(identifier+'.json');s.atomic(path,{'id':identifier,'package':'whatsapp-web','state':'starting','plan':plan})
   with patch('subprocess.run') as privileged:s.execute_job(identifier,privileged=privileged)
   privileged.assert_not_called()
   self.assertEqual(json.loads(path.read_text())['state'],'installed')
   self.assertEqual(s.WEB_DESKTOP.read_text(),s.WEB_CONTENT)
   self.assertEqual(s.build_plan('WhatsApp Web')['status'],'already_installed')
 def test_web_shortcut_preserves_existing_files_and_rejects_changed_url(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(s,'WEB_DESKTOP',Path(folder)/'whatsapp.desktop'):
   plan=s.build_plan('whatsapp web')
   with self.assertRaises(ValueError):s.validate_plan({**plan,'url':'https://evil.example/'})
   s.WEB_DESKTOP.write_text('user custom launcher')
   with self.assertRaises(ValueError):s.validate_plan(plan)
   self.assertEqual(s.WEB_DESKTOP.read_text(),'user custom launcher')
   s.WEB_DESKTOP.unlink();s.WEB_DESKTOP.symlink_to(Path(folder)/'absent')
   with self.assertRaises(ValueError):s.build_plan('whatsapp web')

if __name__=='__main__':unittest.main()
