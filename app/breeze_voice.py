"""Optional Breeze voice: isolated worker, bounded idle life, no speaker fallback."""
import os,subprocess,threading,json,time,base64,sys,queue
from jinx_voice import JinxVoice,ROOT
from jinx_voice import VoiceCancelled
class BreezeVoice(JinxVoice):
 timeout=300
 def warm(self):
  if self.process is None or self.process.poll() is not None:
   self.release()
   python=sys.executable if os.name=='nt' else ROOT/'.venv/bin/python'
   self.process=subprocess.Popen([str(python),str(ROOT/'breeze_cpp_worker.py')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,bufsize=1,env={**os.environ,'HF_HUB_OFFLINE':'1','HF_HUB_DISABLE_TELEMETRY':'1','OMP_WAIT_POLICY':'PASSIVE','KMP_BLOCKTIME':'0','PYTHONDONTWRITEBYTECODE':'1'})
   self.using_gpu=False
   threading.Thread(target=self.process.wait,daemon=True).start()
 def attach_reader(self,p):
  if getattr(self,"reader_process",None) is p:return
  self.reader_process=p
  self.lines=queue.Queue(maxsize=32)
  def read_lines(process,lines):
   try:
    for line in process.stdout:
     while True:
      try:lines.put(line,timeout=.1);break
      except queue.Full:
       if process.poll() is not None:return
   except (OSError,ValueError):pass
   finally:
    try:lines.put_nowait(None)
    except queue.Full:pass
  threading.Thread(target=read_lines,args=(p,self.lines),daemon=True).start()
 def synthesise(self,text,path,speed,cancelled,on_chunk=None):
  if cancelled():raise VoiceCancelled()
  self.warm();p=self.process;self.attach_reader(p)
  try:
   p.stdin.write(json.dumps({'text':text,'path':str(path),'speed':speed,'stream':on_chunk is not None and speed==1})+'\n');p.stdin.flush()
   deadline=time.monotonic()+self.timeout
   while time.monotonic()<deadline:
    if cancelled():raise VoiceCancelled()
    try:line=self.lines.get(timeout=.04)
    except queue.Empty:
     if p.poll() is not None:raise RuntimeError('Breeze voice worker stopped')
     continue
    if line is None:raise RuntimeError('Breeze voice worker stopped')
    if line:
     result=json.loads(line)
     if 'pcm' in result:
      pcm=base64.b64decode(result['pcm'],validate=True)
      if len(pcm)%2 or len(pcm)>480000:raise ValueError('Invalid Breeze audio chunk')
      if on_chunk:on_chunk(pcm)
     else:
      if not result.get('ok'):raise RuntimeError(result.get('error','Breeze generation failed'))
      return result
   raise TimeoutError('Breeze voice generation timed out')
  except BaseException:self.release();raise
