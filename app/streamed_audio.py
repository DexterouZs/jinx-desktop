"""Bounded sentence PCM buffer and cancellable PipeWire streaming playback."""
import os,subprocess,time,threading
from jinx_voice import VoiceCancelled

RATE=24000
BYTES_PER_SECOND=RATE*2

class Buffer:
 def __init__(self):self.pcm=bytearray();self.done=False;self.error=None;self.lock=threading.Lock()
 def append(self,pcm):
  if not isinstance(pcm,bytes) or len(pcm)%2:raise ValueError('Invalid PCM')
  with self.lock:
   if len(self.pcm)+len(pcm)>BYTES_PER_SECOND*90:raise ValueError('Speech chunk exceeds 90 seconds')
   self.pcm.extend(pcm)
 def finish(self,error=None):
  with self.lock:self.error=error;self.done=True
 def snapshot(self):
  with self.lock:return bytes(self.pcm),self.done,self.error
 def ready(self):
  with self.lock:return self.done or len(self.pcm)>=int(BYTES_PER_SECOND*.8)

def play(buffer,cancelled,started,progress,generated,ended):
 """Return only after audio drains. Never arm a read-back on partial playback."""
 if os.name=='nt':
  from windows_audio import stream_play
  return stream_play(buffer,cancelled,started,progress,generated,ended)
 process=None;notified=False;sent=0
 try:
  while not buffer.ready():
   if cancelled():raise VoiceCancelled()
   time.sleep(.02)
  pcm,done,error=buffer.snapshot()
  if error:raise error
  if cancelled():raise VoiceCancelled()
  if not pcm:raise RuntimeError('No speech audio generated')
  process=subprocess.Popen(['pw-play','--raw','--rate','24000','--channels','1','--format','s16','-'],
    stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  os.set_blocking(process.stdin.fileno(),False)
  began=time.monotonic();started(process,began);closed=False
  while True:
   if cancelled():raise VoiceCancelled()
   pcm,done,error=buffer.snapshot()
   if error:raise error
   if done and not notified:generated();notified=True
   if sent<len(pcm):
    try:sent+=os.write(process.stdin.fileno(),pcm[sent:sent+16384])
    except BlockingIOError:pass
   if done and sent==len(pcm) and not closed:
    process.stdin.close();closed=True
   progress(pcm,min(time.monotonic()-began,len(pcm)/BYTES_PER_SECOND),done)
   code=process.poll()
   if code is not None:
    if code or not done or sent!=len(pcm):raise RuntimeError('Audio playback failed')
    break
   time.sleep(.02)
 finally:
  if process:
   if process.poll() is None:process.terminate()
   try:process.wait(timeout=2)
   except subprocess.TimeoutExpired:process.kill();process.wait(timeout=2)
   if process.stdin and not process.stdin.closed:process.stdin.close()
  ended()
