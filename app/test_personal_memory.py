import jinx_test_support
import tempfile,unittest,sqlite3,importlib.util,datetime,json
from pathlib import Path
from unittest.mock import patch,Mock
from long_memory import LongMemory,episode_allowed
import personal_memory as personal
import personality
import jinx as j

class PersonalMemory(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  self.memory=LongMemory(self.root/'memory.sqlite3',embed=lambda _:None)
 def tearDown(self):self.tmp.cleanup()
 def test_explicit_remember_survives_reopening_database(self):
  result=personal.requested('Remember that my favourite drink is Earl Grey tea.',self.memory)
  self.assertIn('Remembered',result['reply'])
  reopened=LongMemory(self.root/'memory.sqlite3',embed=lambda _:None)
  self.assertIn('Earl Grey tea',personal.requested('What is my favourite drink?',reopened)['reply'])
 def test_preference_corrections_replace_current_value(self):
  personal.requested('My favourite music is rock.',self.memory)
  personal.requested('My favourite music is hip hop.',self.memory)
  self.assertEqual(self.memory.count(),1)
  self.assertIn('hip hop',self.memory.pinned()[0]);self.assertNotIn('rock',self.memory.pinned()[0])
 def test_opt_out_still_allows_explicit_remember(self):
  self.assertIsNone(personal.requested('My favourite drink is tea.',self.memory,automatic=False))
  self.assertEqual(self.memory.count(),0)
  personal.requested('Remember that my favourite drink is tea.',self.memory,automatic=False)
  self.assertEqual(self.memory.count(),1)
 def test_no_learning_from_quotes_questions_or_dictated_email(self):
  for text in ('"My favourite drink is tea."','Is my favourite drink tea?','Write an email to Alex saying my favourite drink is tea.'):
   self.assertIsNone(personal.requested(text,self.memory),text)
  self.assertEqual(self.memory.count(),0)
 def test_secrets_are_not_saved_or_truncated_into_episodes(self):
  for text in ('My password is synthetic-secret','API key: synthetic-test-only','Bearer synthetic-only-token'):
   with self.assertRaises(ValueError):self.memory.add('fact',text)
   self.assertFalse(episode_allowed('A'*600+' '+text,'Acknowledged'))
  personal.requested('Remember that my password is synthetic-secret.',self.memory)
  self.assertEqual(self.memory.count(),0)
 def test_deleted_legacy_fact_does_not_reappear_on_restart(self):
  self.memory.migrate_legacy('David prefers tea.')
  identifier=self.memory.listing()['memories'][0]['id'];self.memory.delete(identifier)
  reopened=LongMemory(self.memory.path,embed=lambda _:None)
  reopened.migrate_legacy('David prefers tea.');self.assertEqual(reopened.count(),0)
 def test_fresh_session_preserves_learned_preference(self):
  personal.requested('My favourite drink is tea.',self.memory)
  with patch.object(j,'memory',self.memory),patch.object(j,'task_router',None),patch.object(j.workspace,'clear'),patch.dict(j.status,busy=False):
   j.new_voice_session()
   self.assertIn('tea',j.memory_request('What is my favourite drink?')['reply'])
 def test_direct_learning_needs_no_model_or_extra_approval(self):
  with patch.object(j,'memory',self.memory),patch.object(j,'task_router',None),patch.dict(j.data,speak=False,episodic_memory=False,learn_preferences=True),patch.object(j,'run_tiered_turn') as model:
   j.chat('Remember that my favourite artist is Mozart.',False)
   model.assert_not_called();self.assertIn('Remembered',j.status['messages'][-1]['content'])
   self.assertEqual(self.memory.count(),1)
 def test_active_message_context_is_not_passive_preference_learning(self):
  router=Mock();router.context.return_value={'kind':'message','recipient':'Alex'}
  with patch.object(j,'memory',self.memory),patch.object(j,'task_router',router),patch.dict(j.data,learn_preferences=True):
   self.assertIsNone(j.memory_request('My favourite drink is tea.'))
  self.assertEqual(self.memory.count(),0)
 def test_personality_is_loaded_from_the_ssd_file(self):
  text=personality.instructions();self.assertIn('warm',text);self.assertIn('never invent',text)
 def test_backup_reopens_consistently_without_starting_models(self):
  self.memory.add('fact','Backup test',semantic=False)
  source=Path(__file__).parent/'scripts/backup-personal-memory.py'
  spec=importlib.util.spec_from_file_location('memory_backup',source);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  identity=self.root/'PERSONALITY.md';identity.write_text('Synthetic personality')
  day=datetime.date(2026,9,14)
  target=module.backup(self.root,identity,self.root/'backups',today=day)
  with sqlite3.connect(target/'memory.sqlite3') as db:self.assertEqual(db.execute('select text from memories').fetchone()[0],'Backup test')
  self.assertEqual(module.backup(self.root,identity,self.root/'backups',today=day),target)
  self.assertEqual(json.loads((target/'manifest.json').read_text())['format'],'jinx-memory-snapshot-v1')

if __name__=='__main__':unittest.main()
