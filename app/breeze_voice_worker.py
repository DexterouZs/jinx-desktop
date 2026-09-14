from runtime_paths import state_dir, models_dir, config_dir, runtime_dir
"""On-demand Breeze TTS2; same private JSON-line protocol as the main voice."""
import os,sys,json,select,time,contextlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
SOURCE=models_dir()/'breeze-tts-2-src'
sys.path.insert(0,str(SOURCE))
def main():
 with contextlib.redirect_stdout(sys.stderr):
  import soundfile as sf
  import numpy as np
  import torch
  from breeze_infer.runtime import load_runtime,resolve_device,update_generation_config_for_breeze,set_all_seeds
  from breeze_infer.templates import prepare_inputs,get_template,select_template_name
  from models.fast_streaming import FastBreezeStreamingRuntime,FastStreamingConfig
  torch.set_num_threads(4);torch.set_num_interop_threads(1)
  tokenizer,model,codec=load_runtime(models_dir()/'breeze-tts-2',device=resolve_device(),attn_implementation='eager')
  update_generation_config_for_breeze(model)
  runtime=FastBreezeStreamingRuntime(model,codec,FastStreamingConfig(max_new_tokens=800,max_seq_len=2048,fast_all=False,repetition_penalty=1.1),tokenizer=tokenizer)
 while select.select([sys.stdin],[],[],60)[0]:
  line=sys.stdin.readline()
  if not line:break
  try:
   req=json.loads(line);text=str(req['text']).strip();speed=float(req['speed'])
   if not text or len(text)>1800 or not .85<=speed<=1.15:raise ValueError('Invalid voice request')
   started=time.monotonic()
   with contextlib.redirect_stdout(sys.stderr):
    set_all_seeds(42)
    request={'id':'jinx','text':text,'speaker':'S0','ref_audio_path':str(ROOT/'voice-jinx/reference-short.wav'),'ref_text':"It's nice to dream, but I know my whole life ain't coming back."}
    inputs=prepare_inputs(tokenizer,codec,model,[request],get_template(select_template_name(request)),guidance_scale=1.0,guidance_scale_ref=None,guidance_scale_ins=None)
    waves=[chunk.audio for chunk in runtime.iter_audio_chunks(inputs,request_id='jinx',seed=42)]
    samples=np.concatenate(waves)
    if not len(samples) or not np.isfinite(samples).all():raise ValueError('Invalid audio')
    # Preserve requested speed without changing the selected speaker.
    if speed!=1:
     import librosa
     samples=librosa.effects.time_stretch(samples,rate=speed)
    sf.write(req['path'],samples,runtime.sample_rate,subtype='PCM_16')
   result={'ok':True,'engine':'Breeze TTS2 · ROCm','seconds':round(time.monotonic()-started,2),'duration':len(samples)/runtime.sample_rate}
  except Exception as e:result={'ok':False,'error':type(e).__name__+': '+str(e)[:200]}
  print(json.dumps(result),flush=True)
if __name__=='__main__':main()
