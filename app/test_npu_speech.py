import tempfile,threading,time,unittest,subprocess
from pathlib import Path
from unittest.mock import patch,MagicMock
from npu_speech import NpuSpeech,NpuUnavailable,SpeechCancelled

class NpuTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'audio.wav';self.path.write_bytes(b'RIFF-test')
  self.speech=NpuSpeech(idle_seconds=60,request_timeout=.1)
 def tearDown(self):self.speech.release();self.temp.cleanup()
 def test_transcribes_audio_only_to_local_endpoint(self):
  with patch.object(self.speech,'_start'),patch.object(self.speech,'_request',return_value={'text':' Hallo David. '}) as req:
   self.assertEqual(self.speech.transcribe(self.path),'Hallo David.')
   args=req.call_args.args;self.assertEqual(args[0],'/v1/audio/transcriptions');self.assertIn(b'RIFF-test',args[1]);self.assertIn(b'whisper-v3',args[1]);self.assertIsNotNone(self.speech.idle_timer)
 def test_empty_transcript_is_valid_not_an_action(self):
  with patch.object(self.speech,'_start'),patch.object(self.speech,'_request',return_value={'text':''}):self.assertEqual(self.speech.transcribe(self.path),'')
 def test_server_error_stops_worker_and_cools_down(self):
  process=MagicMock();process.poll.return_value=None;self.speech.process=process
  with patch.object(self.speech,'_start'),patch.object(self.speech,'_request',return_value={'error':{'message':'bad'}}):
   with self.assertRaises(NpuUnavailable):self.speech.transcribe(self.path)
  process.terminate.assert_called_once();self.assertGreater(self.speech.retry_after,time.monotonic());self.assertIsNone(self.speech.process)
 def test_driver_blocked_cleanup_keeps_fallback_and_prevents_new_worker(self):
  process=MagicMock();process.poll.return_value=None
  process.wait.side_effect=subprocess.TimeoutExpired('synthetic-flm',2)
  self.speech.process=process
  with patch.object(self.speech,'_start',side_effect=NpuUnavailable('driver failed')):
   with self.assertRaises(NpuUnavailable):self.speech.transcribe(self.path)
  self.assertEqual(self.speech.stuck_processes,[process])
  with patch('npu_speech.subprocess.Popen') as spawn:
   with self.assertRaises(NpuUnavailable):self.speech._start(lambda:False)
   spawn.assert_not_called()
  self.speech.release()  # Must also be safe when called by idle/shutdown.
 def test_cancelled_request_does_not_return_transcript(self):
  stop=threading.Event()
  def reply(*a,**kw):stop.set();return {'text':'send it'}
  with patch.object(self.speech,'_start'),patch.object(self.speech,'_request',side_effect=reply):
   with self.assertRaises(SpeechCancelled):self.speech.transcribe(self.path,stop.is_set)
 def test_missing_runtime_falls_back_promptly(self):
  with patch('npu_speech.shutil.which',return_value=None):
   with self.assertRaises(NpuUnavailable):self.speech.transcribe(self.path)
 def test_old_idle_timer_cannot_stop_new_request(self):
  self.speech.generation=2
  with patch.object(self.speech,'_stop') as stop:
   self.speech._expire(1);stop.assert_not_called();self.speech._expire(2);stop.assert_called_once()
 def test_request_ignores_environment_proxy(self):
  self.speech.port=12345
  response=MagicMock();response.__enter__.return_value.read.return_value=b'{"text":"ok"}'
  with patch('npu_speech.urllib.request.ProxyHandler') as proxy,patch('npu_speech.urllib.request.build_opener') as opener:
   opener.return_value.open.return_value=response
   self.assertEqual(self.speech._request('/v1/models'),{'text':'ok'});proxy.assert_called_once_with({})
 def test_timeout_releases_worker(self):
  release=threading.Event()
  def stalled(*a,**kw):release.wait(3);return {'text':'late'}
  try:
   with patch.object(self.speech,'_start'),patch.object(self.speech,'_request',side_effect=stalled):
    with self.assertRaises(NpuUnavailable):self.speech.transcribe(self.path)
  finally:release.set()

if __name__=='__main__':unittest.main()
