from runtime_paths import state_dir, models_dir, config_dir, runtime_dir
"""Offline cloned and British speech; AMD GPU/CPU inference with Piper fallback."""
import threading,wave
import quick_speech
import speech_text
from collections import OrderedDict
from jinx_voice import JinxVoice,VoiceCancelled
from breeze_voice import BreezeVoice
from pathlib import Path
import numpy as np
MODELS=models_dir()
CHOICES={'breeze_tts2':'Breeze TTS2 · GPU streaming','jinx_local':'Jinx · local voice clone','kokoro_emma':'Emma · natural British','kokoro_isabella':'Isabella · soft British','piper_alba':'Alba · lightweight British'}
class Voices:
 def __init__(self):self.kokoro=None;self.piper=None;self.german=None;self.jinx=JinxVoice();self.breeze=BreezeVoice();self.lock=threading.Lock();self.cache=OrderedDict();self.cache_bytes=0
 def german_voice(self):
  if self.german is None:
   import json,unicodedata,onnxruntime as ort
   from piper import PiperVoice
   from piper.config import PiperConfig
   opts=ort.SessionOptions();opts.intra_op_num_threads=2;opts.inter_op_num_threads=1
   opts.add_session_config_entry('session.intra_op.allow_spinning','0');opts.add_session_config_entry('session.inter_op.allow_spinning','0')
   path=MODELS/'de_DE-ramona-low.onnx'
   class GermanVoice(PiperVoice):
    def phonemize(self,text):
     # Current eSpeak emits c + cedilla; this voice was trained on composed ç.
     return [list(unicodedata.normalize('NFC',''.join(sentence))) for sentence in super().phonemize(text)]
   self.german=GermanVoice(config=PiperConfig.from_dict(json.loads(path.with_suffix('.onnx.json').read_text())),session=ort.InferenceSession(str(path),sess_options=opts,providers=['CPUExecutionProvider']))
  return self.german
 def warm(self,choice):
  if choice=='piper_ramona':
   with self.lock:self.german_voice()
  if choice=='breeze_tts2':
   # Defer speculative loading if a game or the 27B model occupies the GPU.
   devices=list(Path('/sys/class/drm').glob('card*/device/mem_info_vram_total'))
   if devices:
    p=devices[0]
    try:
     if int(p.read_text())-int(p.with_name('mem_info_vram_used').read_text())<5*1024**3:return
    except (OSError,ValueError):return
   with self.lock:self.jinx.release();self.breeze.warm()
  if choice=='jinx_local':
   with self.lock:self.breeze.release();self.jinx.warm()
 def release(self):
  with self.lock:self.kokoro=None;self.piper=None;self.german=None;self.jinx.release();self.breeze.release();self.cache.clear();self.cache_bytes=0
 def remember(self,key,path,result):
  # Private, bounded RAM only. Do not pin a degraded fallback voice in the cache.
  if not result.get('fallback'):
   payload=Path(path).read_bytes()
   if len(payload)<=2*1024*1024:
    if key in self.cache:self.cache_bytes-=len(self.cache.pop(key)[0])
    self.cache[key]=(payload,dict(result));self.cache_bytes+=len(payload)
    while len(self.cache)>32 or self.cache_bytes>16*1024*1024:
     self.cache_bytes-=len(self.cache.popitem(last=False)[1][0])
  return result
 def synthesise(self,text,path,choice='kokoro_emma',speed=1.0,cancelled=lambda:False,on_chunk=None):
  if choice not in CHOICES:raise ValueError('Unknown voice')
  if not .85<=speed<=1.15:raise ValueError('Speech speed must be between 0.85 and 1.15')
  fallback=''
  if cancelled():raise VoiceCancelled()
  fixed=quick_speech.load(text,choice,speed)
  if fixed:
   if cancelled():raise VoiceCancelled()
   payload,result=fixed;Path(path).write_bytes(payload)
   if on_chunk:
    with wave.open(str(path),'rb') as w:on_chunk(w.readframes(w.getnframes()))
   return result
  with self.lock:
   if cancelled():raise VoiceCancelled()
   key=(choice,float(speed),text)
   if key in self.cache:
    payload,result=self.cache.pop(key);self.cache[key]=(payload,result)
    Path(path).write_bytes(payload)
    if on_chunk:
     with wave.open(str(path),'rb') as w:on_chunk(w.readframes(w.getnframes()))
    return {**result,'cached':True}
   if choice=='breeze_tts2':
    self.jinx.release()
    pronounced=speech_text.spoken(text)
    result=self.breeze.synthesise(pronounced,path,speed,cancelled,**({'on_chunk':on_chunk} if on_chunk else {}))
    return self.remember(key,path,{'voice':choice,'fallback':'','engine':result['engine'],'spoken_text':pronounced})
   if choice=='piper_ramona':
    from piper import SynthesisConfig
    with wave.open(str(path),'wb') as w:self.german_voice().synthesize_wav(text,w,syn_config=SynthesisConfig(length_scale=1/speed))
    if cancelled():raise VoiceCancelled()
    return self.remember(key,path,{'voice':choice,'fallback':'','engine':'Piper · native German CPU','spoken_text':text})
   self.breeze.release()
   if choice=='jinx_local':
    try:
     pronounced=speech_text.spoken(text)
     result=self.jinx.synthesise(pronounced,path,speed,cancelled)
     return self.remember(key,path,{'voice':choice,'fallback':'GPU voice unavailable; using local CPU speech.' if self.jinx.gpu_failed else '', 'engine':result.get('engine','cpu'),'spoken_text':pronounced})
    except VoiceCancelled:raise
    except Exception as e:raise RuntimeError('Jinx voice is unavailable; reply kept as text instead of switching voices.') from e
   else:self.jinx.release()
   if cancelled():raise VoiceCancelled()
   if choice.startswith('kokoro_'):
    try:
     if self.kokoro is None:
      import onnxruntime as ort
      from kokoro_onnx import Kokoro
      opts=ort.SessionOptions();opts.intra_op_num_threads=4;opts.inter_op_num_threads=1
      opts.add_session_config_entry('session.intra_op.allow_spinning','0')
      opts.add_session_config_entry('session.inter_op.allow_spinning','0')
      folder=MODELS/'kokoro'
      self.kokoro=Kokoro.from_session(ort.InferenceSession(str(folder/'kokoro-v1.0.onnx'),opts,providers=['CPUExecutionProvider']),str(folder/'voices-v1.0.bin'))
     samples,rate=self.kokoro.create(text,voice='bf_'+choice.removeprefix('kokoro_'),speed=speed,lang='en-gb',sentence_pause=.22,clause_pause=.09)
     with wave.open(str(path),'wb') as w:
      w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate);w.writeframes((np.clip(samples,-1,1)*32767).astype('int16').tobytes())
     return self.remember(key,path,{'voice':choice,'fallback':''})
    except Exception as e:raise RuntimeError('Selected voice is unavailable; reply kept as text instead of switching voices.') from e
   from piper import PiperVoice,SynthesisConfig
   if self.piper is None:self.piper=PiperVoice.load(str(MODELS/'en_GB-alba-medium.onnx'))
   with wave.open(str(path),'wb') as w:self.piper.synthesize_wav(text,w,syn_config=SynthesisConfig(length_scale=1/speed))
   return self.remember(key,path,{'voice':'piper_alba','fallback':fallback})
