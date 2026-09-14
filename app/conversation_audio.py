"""Noise-aware local endpointing for click-started conversations, 16 kHz PCM."""
from collections import deque
import re
import numpy as np
from speech_detector import SpeechDetector
class MicrophoneMuted(Exception):pass

def clean_transcript(text):
 # Whisper's non-speech annotations are never a user request.
 text=re.sub(r'\[(?:blank_audio|silence|music|noise|inaudible|applause|laughter)\]|\((?:silence|music|noise|inaudible|applause|laughter)\)','',str(text),flags=re.I).strip()
 return text if re.search(r'[A-Za-z0-9]',text) else ''

def record_utterance(stream,active,on_level,muted=lambda:False):
 """Neural VAD + sustained onset + adaptive noise floor; 900 ms endpoint.
 Keep 400 ms pre-roll, reject isolated clicks, cap each spoken turn at 60 s.
 Quiet waiting is indefinite with bounded memory. Never retain noise to disk.
 """
 vad=SpeechDetector();pre=deque(maxlen=4);onsets=deque(maxlen=4)
 chunks=[];heard=False;quiet=0;voiced=0;n=0;noise=50.0
 try:
  while active():
   if n%5==0 and muted():raise MicrophoneMuted()
   block,_=stream.read(1600);n+=1
   if not active():break
   a=np.frombuffer(block,dtype='int16').copy()
   if len(a)!=1600:raise RuntimeError('Unexpected microphone block size')
   rms=float(np.sqrt(np.mean(a.astype('float32')**2)))
   probability=vad.probability(a)
   # Adapt only on confidently non-speech frames, so a user's voice never
   # teaches the threshold to reject their own speech.
   if probability<.15:noise=.95*noise+.05*min(rms,2000)
   gate=max(160.0,noise*2.2)
   speech=probability>=(.45 if heard else .75) and rms>gate
   on_level(min(1.0,rms/1800) if probability>.35 and rms>gate else 0.0)
   pre.append(a)
   if not heard:
    onsets.append(speech)
    if sum(onsets)<3:continue
    heard=True;chunks=list(pre);voiced=sum(onsets);quiet=0
   else:
    chunks.append(a)
    if speech:voiced+=1;quiet=0
    else:quiet+=1
   if quiet>=9 or len(chunks)>=600:
    if voiced>=3:return chunks
    chunks=[];heard=False;quiet=0;voiced=0;pre.clear();onsets.clear()
  return []
 finally:on_level(0)
