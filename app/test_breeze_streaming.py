import base64,json,subprocess,sys,tempfile,threading,time,unittest,wave
from pathlib import Path
from unittest.mock import patch,Mock
from breeze_voice import BreezeVoice
from jinx_voice import VoiceCancelled
from streamed_audio import Buffer,play,BYTES_PER_SECOND
from voices import Voices

class Protocol(unittest.TestCase):
 def worker(self,script):
  v=BreezeVoice()
  v.process=subprocess.Popen([sys.executable,'-c',script],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
  return v
 def test_coalesced_chunks_and_final_result_are_all_read(self):
  messages=[{'pcm':base64.b64encode(b'\x00\x00'*240).decode()},{'pcm':base64.b64encode(b'\x01\x00'*120).decode()},{'ok':True,'engine':'test'}]
  script='import sys,time;sys.stdin.readline();sys.stdout.write('+repr(''.join(json.dumps(m)+'\n' for m in messages))+');sys.stdout.flush();time.sleep(5)'
  v=self.worker(script);chunks=[]
  try:
   with patch.object(v,'warm'):r=v.synthesise('Hello','unused',1,lambda:False,chunks.append)
   self.assertTrue(r['ok']);self.assertEqual(list(map(len,chunks)),[480,240])
  finally:v.release()
 def test_stop_kills_blocked_worker(self):
  v=self.worker('import sys,time;sys.stdin.readline();time.sleep(60)');p=v.process;start=time.monotonic()
  with patch.object(v,'warm'),self.assertRaises(VoiceCancelled):v.synthesise('Hello','unused',1,lambda:time.monotonic()-start>.08)
  self.assertIsNotNone(p.poll());self.assertIsNone(v.process)
 def test_worker_error_does_not_switch_voice(self):
  v=self.worker('import sys;sys.stdin.readline();print(\'{"ok":false,"error":"GPU failed"}\',flush=True)')
  with patch.object(v,'warm'),self.assertRaisesRegex(RuntimeError,'GPU failed'):v.synthesise('Hello','unused',1,lambda:False)
  self.assertIsNone(v.process)

class Playback(unittest.TestCase):
 def test_buffer_prebuffers_actual_audio_not_time(self):
  b=Buffer();b.append(b'\x00'*int(BYTES_PER_SECOND*.32));self.assertFalse(b.ready())
  b.append(b'\x00'*int(BYTES_PER_SECOND*.48));self.assertTrue(b.ready())
 def test_short_finished_clip_is_ready(self):
  b=Buffer();b.append(b'\x00'*100);b.finish();self.assertTrue(b.ready())
 def test_partial_failed_synthesis_never_calls_generated(self):
  b=Buffer();b.append(b'\x00'*100);b.finish(RuntimeError('synthesis failed'));generated=Mock();ended=Mock()
  with patch('streamed_audio.subprocess.Popen') as p,self.assertRaisesRegex(RuntimeError,'synthesis failed'):
   play(b,lambda:False,Mock(),Mock(),generated,ended)
  p.assert_not_called();generated.assert_not_called();ended.assert_called_once()
 def test_cancel_while_prebuffering_never_starts_audio(self):
  b=Buffer()
  with patch('streamed_audio.subprocess.Popen') as p,self.assertRaises(VoiceCancelled):play(b,lambda:True,Mock(),Mock(),Mock(),Mock())
  p.assert_not_called()
 def test_play_drains_and_waits_for_process(self):
  b=Buffer();b.append(b'\x02\x00'*24000);b.finish();generated=Mock();chunks=[]
  real_popen=subprocess.Popen
  def sink(*args,**kwargs):return real_popen([sys.executable,'-c','import sys,time;sys.stdin.buffer.read();time.sleep(.1)'],**kwargs)
  start=time.monotonic()
  with patch('streamed_audio.subprocess.Popen',side_effect=sink):play(b,lambda:False,Mock(),lambda pcm,*args:chunks.append(len(pcm)),generated,Mock())
  self.assertGreater(time.monotonic()-start,.1);generated.assert_called_once();self.assertEqual(chunks[-1],48000)
 def test_completed_generation_is_not_completed_playback(self):
  b=Buffer();b.append(b'\x00'*48000);b.finish();pids=[];start=time.monotonic();real_popen=subprocess.Popen
  def sink(*args,**kwargs):
   p=real_popen([sys.executable,'-c','import sys,time;sys.stdin.buffer.read();time.sleep(60)'],**kwargs);pids.append(p);return p
  with patch('streamed_audio.subprocess.Popen',side_effect=sink),self.assertRaises(VoiceCancelled):
   play(b,lambda:time.monotonic()-start>.15,Mock(),Mock(),Mock(),Mock())
  self.assertIsNotNone(pids[0].poll())
 def test_streamed_cache_hit_emits_identical_audio(self):
  v=Voices();key=('breeze_tts2',1.,'Hello.');pcm=b'\x00\x01'*240
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'a.wav'
   with wave.open(str(path),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(pcm)
   v.remember(key,path,{'voice':'breeze_tts2','engine':'test','fallback':''});chunks=[]
   with patch.object(v.breeze,'synthesise') as synth,patch('quick_speech.load',return_value=None):r=v.synthesise('Hello.',path,'breeze_tts2',on_chunk=chunks.append)
   synth.assert_not_called();self.assertTrue(r['cached']);self.assertEqual(chunks,[pcm])

if __name__=='__main__':unittest.main()
