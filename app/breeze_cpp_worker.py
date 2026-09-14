"""On-demand GPU speech over private pipes; expires after 60 idle seconds."""
import os,sys,json,time,wave,base64,threading,queue

def main():
 # Native libraries use printf too. Reserve a separate FD for the JSON protocol.
 protocol=os.fdopen(os.dup(1),'w',buffering=1)
 os.dup2(2,1)
 os.umask(0o077)
 import numpy as np
 from breeze_cpp_runtime import Runtime
 runtime=Runtime()
 try:
  requests=queue.Queue(maxsize=4)
  def read_requests():
   for line in sys.stdin:requests.put(line)
   requests.put(None)
  threading.Thread(target=read_requests,daemon=True).start()
  while True:
   try:line=requests.get(timeout=60)
   except queue.Empty:break
   if not line:break
   try:
    req=json.loads(line);text=str(req['text']).strip();speed=float(req['speed'])
    if not text or len(text)>1800 or not .85<=speed<=1.15:raise ValueError('Invalid voice request')
    started=time.monotonic();chunks=[];first=None
    def emit(samples):
     nonlocal first
     if first is None:first=time.monotonic()-started
     pcm=(np.clip(samples,-1,1)*32767).astype('<i2').tobytes();chunks.append(pcm)
     if req.get('stream') and speed==1:
      protocol.write(json.dumps({'pcm':base64.b64encode(pcm).decode()})+'\n')
    runtime.generate(text,emit,first=4,maximum=12)
    pcm=b''.join(chunks)
    if not pcm:raise ValueError('Breeze generated no audio')
    if speed!=1:
     # Apply rate to the entire waveform, preserving pitch and chunk boundaries.
     import subprocess
     pcm=subprocess.run(['ffmpeg','-v','error','-f','s16le','-ar','24000','-ac','1','-i','pipe:0',
      '-af','atempo='+str(speed),'-f','s16le','pipe:1'],input=pcm,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,check=True,timeout=30).stdout
    with wave.open(req['path'],'wb') as w:
     w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(pcm)
    result={'ok':True,'engine':'Breeze TTS2 · Vulkan Q8','seconds':round(time.monotonic()-started,3),
     'first_chunk_seconds':round(first,3),'duration':len(pcm)/48000}
   except Exception as e:result={'ok':False,'error':type(e).__name__+': '+str(e)[:200]}
   protocol.write(json.dumps(result)+'\n')
 finally:runtime.close()
if __name__=='__main__':main()
