from runtime_paths import state_dir, models_dir, config_dir, runtime_dir
"""Small private ctypes adapter; loaded only in the isolated voice worker."""
import ctypes as C
import hashlib
import os
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent
MODELS = models_dir()/'breeze-cpp'
TRANSCRIPT = "It's nice to dream, but I know my whole life ain't coming back."
CALLBACK = C.CFUNCTYPE(C.c_int, C.POINTER(C.c_float), C.c_int)

class Runtime:
 def __init__(self):
  library = Path(os.environ.get('JINX_BREEZE_LIBRARY', MODELS/('jinx-breeze.dll' if os.name=='nt' else 'libjinx-breeze.so')))
  self.dll_directory = os.add_dll_directory(str(library.parent)) if os.name=='nt' else None
  self.lib = C.CDLL(str(library))
  self.lib.jinx_breeze_init.argtypes = [C.c_char_p]*4
  self.lib.jinx_breeze_init.restype = C.c_void_p
  self.lib.jinx_breeze_error.restype = C.c_char_p
  self.lib.jinx_breeze_generate.argtypes = [C.c_void_p,C.c_char_p,C.c_int,C.c_int,CALLBACK]
  self.lib.jinx_breeze_free.argtypes = [C.c_void_p]
  reference = Path(os.environ.get('JINX_VOICE_REFERENCE',ROOT/'voice-jinx/reference-short.wav'))
  digest = hashlib.sha256(reference.read_bytes()+TRANSCRIPT.encode()).hexdigest()[:20]
  cache = MODELS/('jinx-'+digest+'.breeze')
  self.context = self.lib.jinx_breeze_init(
   str(MODELS/'breeze-tts-2-q8_0.gguf').encode(), str(reference).encode(), TRANSCRIPT.encode(), str(cache).encode())
  if not self.context:raise RuntimeError(self.error())
 def error(self):return self.lib.jinx_breeze_error().decode(errors='replace')
 def generate(self,text,callback,first=4,maximum=25):
  errors=[]
  @CALLBACK
  def emit(pointer,count):
   try:
    samples=np.ctypeslib.as_array(pointer,shape=(count,)).copy()
    if not np.isfinite(samples).all():raise ValueError('Invalid Breeze audio')
    return 0 if callback(samples) is not False else 1
   except BaseException as e:errors.append(e);return 1
  rc=self.lib.jinx_breeze_generate(self.context,text.encode(),first,maximum,emit)
  if errors:raise errors[0]
  if rc:raise RuntimeError(self.error())
 def close(self):
  if self.context:self.lib.jinx_breeze_free(self.context);self.context=None
