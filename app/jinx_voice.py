"""Cancellable bridge to the isolated local F5 voice environment."""
import json, os, select, subprocess, time, threading
from pathlib import Path
ROOT=Path(__file__).resolve().parent
class VoiceCancelled(Exception):pass
class JinxVoice:
 def __init__(self):self.process=None;self.gpu_failed=False;self.using_gpu=False
 def release(self):
  p=self.process;self.process=None
  if p is None:return
  if p.poll() is None:
   p.terminate()
   try:p.wait(timeout=2)
   except subprocess.TimeoutExpired:p.kill();p.wait(timeout=2)
  if p.stdin:p.stdin.close()
  if p.stdout:p.stdout.close()
 def warm(self):
  if self.process is None or self.process.poll() is not None:
   self.release()
   env={**os.environ,'HF_HUB_OFFLINE':'1','HF_HUB_DISABLE_TELEMETRY':'1','OMP_WAIT_POLICY':'PASSIVE','KMP_BLOCKTIME':'0'}
   config=json.loads((ROOT/'voice-jinx/runtime.json').read_text()) if (ROOT/'voice-jinx/runtime.json').exists() else {}
   self.using_gpu=config.get('device')=='cuda' and not self.gpu_failed
   python=ROOT/('.voice-gpu-venv/bin/python' if self.using_gpu else '.voice-venv/bin/python')
   env['JINX_TTS_DEVICE']='cuda' if self.using_gpu else 'cpu'
   self.process=subprocess.Popen([str(python),str(ROOT/'jinx_voice_worker.py')],
     stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,bufsize=1,env=env)
  p=self.process
  # Reap even when the worker exits during a long idle period. Popen serialises wait/poll.
  if not getattr(p,'jinx_reaper',False):
   p.jinx_reaper=True
   threading.Thread(target=p.wait,daemon=True,name='jinx-voice-reaper').start()
 def synthesise(self,text,path,speed,cancelled):
  try:return self._synthesise_once(text,path,speed,cancelled)
  except VoiceCancelled:raise
  except Exception:
   if not self.using_gpu:raise
   self.gpu_failed=True;self.release()
   return self._synthesise_once(text,path,speed,cancelled)
 def _synthesise_once(self,text,path,speed,cancelled):
  if cancelled():raise VoiceCancelled()
  self.warm();p=self.process
  try:
   p.stdin.write(json.dumps({'text':text,'path':str(path),'speed':speed})+'\n');p.stdin.flush()
   deadline=time.monotonic()+getattr(self,'timeout',120)
   while time.monotonic()<deadline:
    if cancelled():raise VoiceCancelled()
    if select.select([p.stdout],[],[],.08)[0]:
     line=p.stdout.readline()
     if not line:raise RuntimeError('Jinx voice worker stopped')
     result=json.loads(line)
     if not result.get('ok'):raise RuntimeError(result.get('error','Jinx voice generation failed'))
     return result
    if p.poll() is not None:raise RuntimeError('Jinx voice worker stopped')
   raise TimeoutError('Jinx voice generation timed out')
  except Exception:
   self.release();raise
