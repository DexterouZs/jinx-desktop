import unittest
import speech_text as s
class SpeechText(unittest.TestCase):
 def test_ordinary_voice_text_stays_unchanged(self):
  for text in ["Hi David, I'm here.",'There you are, David. I have 3 ideas.','Je serai là à 16 heures.']:
   self.assertEqual(s.spoken(text),text)
 def test_compact_specifications_get_time_for_pronunciation(self):
  result=s.spoken('AMD Ryzen AI MAX+395, Radeon 8060S, 16GB of GPU VRAM.')
  for part in ['ay em dee','Max plus three nine five','eight zero six zero ess','sixteen gigabytes','gee pee you','vee ar ay em']:self.assertIn(part,result)
 def test_versions_decimals_units_and_leading_zeroes_keep_digits(self):
  result=s.spoken('Kernel 7.2.3-1, with 3.5Gi and 16GB, 52°C at 3600RPM.')
  for part in ['seven point two point three dash one','three point five gibibytes','sixteen gigabytes','fifty two degrees Celsius','three thousand six hundred ar pee em']:self.assertIn(part,result)
  self.assertEqual(s.number('007'),'zero zero seven')
 def test_identifiers_are_not_rounded_and_urls_are_untouched(self):
  self.assertIn('three zero two',s.spoken('Model GZ302EA.'))
  for value in ['https://example.org/1.2.3','/usr/lib/version7.2.3']:
   self.assertIn(value,s.spoken('GPU reference '+value))
 def test_caption_weights_follow_spoken_notation(self):
  text='The GPU has 16GB.';weights=s.word_weights(text)
  self.assertEqual(len(weights),len(text.split()))
  self.assertGreater(weights[-1],len('16GB.'));self.assertGreater(weights[1],3)
 def test_punctuation_spaced_units_and_signed_values(self):
  self.assertEqual(s.spoken('Storage: (16 GB).'),'Storage: (sixteen gigabytes).')
  self.assertEqual(s.spoken('GPU: -30 steps.'),'gee pee you: minus thirty steps.')
  self.assertEqual(s.spoken('(GPU), 16GB.'),'(gee pee you), sixteen gigabytes.')
  self.assertEqual(s.spoken('There are 16Giraffes.'),'There are 16Giraffes.')
if __name__=='__main__':unittest.main()
