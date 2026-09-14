from runtime_paths import state_dir, models_dir, config_dir, runtime_dir
"""Private, on-demand AMD GPU/CPU voice worker. JSON lines on stdin/stdout; no server.
Uses only local model files. Exits after one idle minute or parent closes pipe.
"""
import os, sys, json, select, contextlib, time
from pathlib import Path
os.environ.update(HF_HUB_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1', DO_NOT_TRACK='1',
                  OMP_WAIT_POLICY='PASSIVE', KMP_BLOCKTIME='0', TOKENIZERS_PARALLELISM='false')
ROOT=Path(__file__).resolve().parent
MODELS=models_dir()/'f5-tts'

def main():
 # Redirect library chatter, including reference text, away from the protocol.
 with contextlib.redirect_stdout(sys.stderr):
  import torch, soundfile as sf, numpy as np
  from f5_tts.api import F5TTS
  from f5_tts.infer.utils_infer import infer_batch_process, chunk_text
  device=os.environ.get('JINX_TTS_DEVICE','cpu')
  if device=='cuda' and not torch.cuda.is_available():raise RuntimeError('AMD GPU voice unavailable')
  torch.set_num_threads(4 if device=='cuda' else 8);torch.set_num_interop_threads(1)
  model=F5TTS(ckpt_file=str(MODELS/'F5TTS_v1_Base/model_1250000.safetensors'),
              vocab_file=str(MODELS/'F5TTS_v1_Base/vocab.txt'),
              vocoder_local_path=str(MODELS/'vocos'),device=device)
  # Enter autocast inside sample: upstream dispatches inference in a thread.
  model.ema_model.sample=torch.autocast(device,dtype=torch.float16 if device=='cuda' else torch.bfloat16)(model.ema_model.sample)
  samples,rate=sf.read(str(ROOT/'voice-jinx/reference-short.wav'),dtype='float32',always_2d=True)
  reference=(torch.from_numpy(samples.T.copy()),rate)
  ref_text="It's nice to dream, but I know my whole life ain't coming back. "
 while select.select([sys.stdin],[],[],60)[0]:
  line=sys.stdin.readline()
  if not line:break
  try:
   req=json.loads(line);text=str(req['text']).strip();speed=float(req['speed']);path=Path(req['path'])
   if not text or len(text)>1800 or not .85<=speed<=1.15:raise ValueError('Invalid voice request')
   start=time.monotonic();waves=[]
   with contextlib.redirect_stdout(sys.stderr):
    for chunk in chunk_text(text,max_chars=150):
     torch.manual_seed(42)
     wav,rate,_=next(infer_batch_process(reference,ref_text,[chunk],model.ema_model,model.vocoder,
                    nfe_step=8,speed=speed,device=device,progress=None))
     waves.append(wav)
   samples=np.concatenate(waves)
   if not np.isfinite(samples).all() or not len(samples):raise RuntimeError('Invalid generated audio')
   sf.write(str(path),samples,rate,subtype='PCM_16')
   response={'ok':True,'engine':device,'seconds':round(time.monotonic()-start,2),'duration':len(samples)/rate}
  except Exception as e:response={'ok':False,'error':type(e).__name__+': '+str(e)[:200]}
  print(json.dumps(response),flush=True)

if __name__=='__main__':main()
