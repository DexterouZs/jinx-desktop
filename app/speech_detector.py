from runtime_paths import state_dir, models_dir, config_dir, runtime_dir
"""Silero VAD ONNX streaming wrapper, adapted from the upstream MIT wrapper.
https://github.com/snakers4/silero-vad/blob/master/src/silero_vad/utils_vad.py
Only NumPy/ONNX Runtime are required; no Torch import in the microphone process.
"""
from pathlib import Path
from functools import lru_cache
import numpy as np
@lru_cache(maxsize=1)
def session():
 import onnxruntime as ort
 options=ort.SessionOptions();options.intra_op_num_threads=1;options.inter_op_num_threads=1
 options.add_session_config_entry('session.intra_op.allow_spinning','0')
 options.add_session_config_entry('session.inter_op.allow_spinning','0')
 return ort.InferenceSession(str(models_dir()/'silero-vad/silero_vad.onnx'),options,providers=['CPUExecutionProvider'])
class SpeechDetector:
 def __init__(self):
  self.model=session();self.state=np.zeros((2,1,128),dtype='float32');self.context=np.zeros((1,64),dtype='float32');self.pending=np.empty(0,dtype='float32')
 def probability(self,pcm):
  self.pending=np.concatenate((self.pending,np.asarray(pcm,dtype='float32')/32768))
  probabilities=[]
  while len(self.pending)>=512:
   chunk=self.pending[:512].reshape(1,-1);self.pending=self.pending[512:]
   frame=np.concatenate((self.context,chunk),axis=1)
   output,self.state=self.model.run(None,{'input':frame,'state':self.state,'sr':np.array(16000,dtype='int64')})
   self.context=frame[:,-64:];probabilities.append(float(output[0,0]))
  return float(np.median(probabilities)) if probabilities else 0.0
