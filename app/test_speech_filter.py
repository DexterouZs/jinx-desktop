import unittest
import speech_filter as f

class SpeechFilter(unittest.TestCase):
 def test_prose_numbers_and_important_failures_survive(self):
  for text in ['Your appointment is today at 16:00. Reminder at 13:00.',
               'Battery is 42%, CPU is 60°C and the price is €35.50.',
               'Version 7.2.3 failed. Do not reboot yet.',
               'Dein Termin ist um 16:00. Der Akku hat 42%.']:
   self.assertEqual(f.for_speech(text),text)
 def test_link_title_survives_without_address(self):
  self.assertEqual(f.for_speech('See [CachyOS documentation](https://example.org/docs?q=1).'), 'See CachyOS documentation.')
 def test_bare_urls_keep_punctuation_without_spelling_query(self):
  text=f.for_speech('Open https://example.org/a?long=query. It works.')
  self.assertEqual(text,'Open the link shown on screen. It works.')
  self.assertNotIn('example',f.for_speech('Visit www.example.org.'))
 def test_reference_appendix_does_not_eat_following_answer(self):
  text='It works. [1]\n\n## Sources\n- [Docs](https://example.org)\n- https://example.net\n\nRestart the app.'
  self.assertEqual(f.for_speech(text),'It works.\nRestart the app.')
 def test_code_stays_on_screen_and_surrounding_explanation_survives(self):
  text='Use the following command.\n```bash\nprintf hello\n```\nIt prints a greeting.'
  self.assertEqual(f.for_speech(text),'Use the following command.\nThe code is shown on screen.\nIt prints a greeting.')
 def test_hash_and_path_are_not_read_as_a_string_of_digits(self):
  text=f.for_speech('File /home/david/logs/test.log. ID 12345678-1234-1234-1234-123456789abc.')
  self.assertEqual(text,'File the path shown on screen. ID the identifier shown on screen.')
 def test_preserve_verbatim_message_and_confirmation_contents(self):
  text='Send https://example.org at 16:00.\n```text\n[1]\n```'
  self.assertEqual(f.for_speech(text,verbatim=True),text)
 def test_explicit_full_reading_override_and_negative_request(self):
  for request in ['Read the full URL','Please read it exactly as written','Read the entire command','Lies den Link vor','Lies das wörtlich']:
   self.assertTrue(f.explicit_details(request),request)
  for request in ['What is this website?','Do not read the URL','Please don\'t read the code','Explain exactly how this works']:
   self.assertFalse(f.explicit_details(request),request)
 def test_only_references_get_a_short_response(self):
  self.assertEqual(f.for_speech('Sources:\n- https://example.org'),'The details are shown on screen.')
 def test_citation_token_does_not_reach_tts(self):
  self.assertEqual(f.for_speech('It works. citeturn0search0'),'It works.')

if __name__=='__main__':unittest.main()
