"""Windows PCM playback with cancellation and completion after the device drains."""
import threading
import time
import wave
from jinx_voice import VoiceCancelled

class WavePlayer:
 def __init__(self,path):
  self.stop=threading.Event();self.returncode=None;self.stream=None
  def run():
   try:
    import sounddevice as sd
    with wave.open(str(path),'rb') as wav:
     if wav.getsampwidth()!=2:raise ValueError('Expected 16-bit PCM')
     with sd.RawOutputStream(samplerate=wav.getframerate(),channels=wav.getnchannels(),dtype='int16') as stream:
      self.stream=stream
      while not self.stop.is_set():
       block=wav.readframes(1024)
       if not block:break
       stream.write(block)
      if self.stop.is_set():stream.abort()
     self.returncode=1 if self.stop.is_set() else 0
   except Exception:self.returncode=1
  self.thread=threading.Thread(target=run,daemon=True);self.thread.start()
 def poll(self):return self.returncode
 def terminate(self):self.stop.set()
 kill=terminate
 def wait(self,timeout=None):
  self.thread.join(timeout)
  if self.thread.is_alive():
   import subprocess
   raise subprocess.TimeoutExpired('Windows audio',timeout)
  return self.returncode

class Playback:
 def __init__(self):self.stopped=False;self.returncode=None
 def terminate(self):self.stopped=True
 kill=terminate
 def poll(self):return self.returncode

def stream_play(buffer,cancelled,started,progress,generated,ended):
 import sounddevice as sd
 rate=24000;sent=0;notified=False;player=Playback()
 try:
  while not buffer.ready():
   if cancelled():raise VoiceCancelled()
   time.sleep(.02)
  pcm,done,error=buffer.snapshot()
  if error:raise error
  if not pcm:raise RuntimeError('No speech audio generated')
  with sd.RawOutputStream(samplerate=rate,channels=1,dtype='int16',latency='low') as stream:
   began=time.monotonic();started(player,began)
   try:
    while True:
     if cancelled() or player.stopped:raise VoiceCancelled()
     pcm,done,error=buffer.snapshot()
     if error:raise error
     if done and not notified:generated();notified=True
     if sent<len(pcm):
      block=pcm[sent:sent+2048];stream.write(block);sent+=len(block)
     elif done:break
     else:time.sleep(.015)
     progress(pcm,min(time.monotonic()-began,len(pcm)/48000),done)
   except BaseException:stream.abort();raise
  player.returncode=0
 finally:ended()
