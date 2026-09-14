"""Exercise the native worker with a synthetic reference, never a private voice."""
from pathlib import Path
import base64,json,math,os,queue,subprocess,sys,tempfile,threading,time,wave
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'windows'))
from setup_models import download

def main():
 with tempfile.TemporaryDirectory(prefix='jinx-voice-smoke-') as tmp:
  root=Path(tmp);model=root/'models/breeze-cpp/breeze-tts-2-q8_0.gguf'
  download('https://huggingface.co/HoppouAI/Breeze-TTS-2.cpp/resolve/main/breeze-tts-2-q8_0.gguf',model,'a02bcc4b69b0601032727f8040c4942149b1b73aa0f69022fe5aaa6a8f0ef879')
  import numpy as np
  ref=root/'synthetic.wav';samples=(np.sin(np.arange(24000*2)*2*math.pi*180/24000)*.1*32767).astype('<i2')
  with wave.open(str(ref),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(samples.tobytes())
  environment={**os.environ,'JINX_MODELS_DIR':str(root/'models'),'JINX_VOICE_REFERENCE':str(ref),'JINX_BREEZE_LIBRARY':str(ROOT/'voice/jinx-breeze.dll'),'JINX_BREEZE_ALLOW_CPU':'1','PYTHONUTF8':'1'}
  p=subprocess.Popen([sys.executable,str(ROOT/'app/breeze_cpp_worker.py')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=environment)
  lines=queue.Queue();errors=[]
  def read():
   for line in p.stdout:lines.put(line)
   lines.put(None)
  def err():
   for line in p.stderr:errors.append(line[-400:]);errors[:]=errors[-12:]
  threading.Thread(target=read,daemon=True).start();threading.Thread(target=err,daemon=True).start()
  start=time.monotonic();chunks=[];result=None
  try:
   p.stdin.write(json.dumps({'text':'Hello.','speed':1,'path':str(root/'output.wav'),'stream':True})+'\n');p.stdin.flush()
   while time.monotonic()-start<360:
    try:line=lines.get(timeout=1)
    except queue.Empty:continue
    if line is None:raise RuntimeError('Voice worker exited: '+''.join(errors))
    row=json.loads(line)
    if 'pcm' in row:chunks.append(base64.b64decode(row['pcm'],validate=True))
    else:result=row;break
   if not result or not result.get('ok'):raise RuntimeError('Voice generation failed: '+str(result)+' '+''.join(errors))
   with wave.open(str(root/'output.wav'),'rb') as w:
    assert w.getnchannels()==1 and w.getframerate()==24000 and w.getnframes()>0
    assert w.readframes(w.getnframes())==b''.join(chunks)
   report={'engine':result['engine'],'stream_chunks':len(chunks),'duration':result['duration'],'elapsed':round(time.monotonic()-start,2),'reference':'synthetic test signal, not the private Jinx voice'}
   print(json.dumps(report),flush=True)
   Path(os.environ.get('JINX_VOICE_TEST_REPORT','voice-runtime-smoke.json')).write_text(json.dumps(report))
  finally:
   p.terminate()
   try:p.wait(timeout=5)
   except subprocess.TimeoutExpired:p.kill();p.wait()
if __name__=='__main__':main()
