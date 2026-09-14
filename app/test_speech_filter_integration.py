import jinx_test_support
import unittest
from unittest.mock import patch
import jinx as j

class SpokenPresentation(unittest.TestCase):
 def exercise(self,request='',verbatim=False):
  text='Your appointment is at 16:00. Details: https://example.org/calendar.'
  with patch.dict(j.data,{'speak':True,'voice':'breeze_tts2','voice_speed':1}),patch.object(j,'current_request',request),patch.object(j,'breeze_say') as speak:
   j.say(text,verbatim=verbatim)
   spoken=speak.call_args.args[0]
  self.assertIn('16:00',spoken)
  self.assertEqual('https://example.org' in spoken,verbatim or bool(request))
  return text,spoken
 def test_normal_breeze_speech_is_filtered_before_splitting(self):self.exercise()
 def test_confirmation_keeps_complete_payload(self):self.exercise(verbatim=True)
 def test_user_can_request_full_url(self):self.exercise('Read the full URL')
 def test_written_reply_remains_intact(self):
  text,spoken=self.exercise();self.assertIn('https://example.org',text);self.assertNotEqual(text,spoken)

if __name__=='__main__':unittest.main()
