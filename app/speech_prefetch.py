"""Prepare one stable speech chunk during text generation. Never plays audio."""
import tempfile,threading,re
import speech_filter
from pathlib import Path
from workbench import speech_chunks

class FirstSpeech:
 def __init__(self,voice,choice,speed,cancelled,runtime=None):
  self.voice=voice;self.choice=choice;self.speed=speed;self.cancelled=cancelled;self.runtime=runtime
  self.thread=None;self.text=None;self.error=None
 def feed(self,text):
  if self.thread or self.cancelled():return
  text=speech_filter.for_speech(text)
  chunks=speech_chunks(text)
  # A second chunk proves that the first chunk is closed, including a complete
  # word after a length boundary. Tentative text is never played or confirmed.
  # A sentence at the stream boundary can be synthesised speculatively too.
  # Audio is only cached, never played here; say() reuses an EXACT text key
  # only after the final answer and tool checks have completed.
  if not chunks:return
  if len(chunks)<2 and not re.search(r'[.!?]["”’]?$',str(text).rstrip()):return
  self.text=chunks[0]
  self.thread=threading.Thread(target=self.prepare,daemon=True,name='jinx-first-speech')
  self.thread.start()
 def prepare(self):
  try:
   with tempfile.TemporaryDirectory(prefix='jinx-prepare-',dir=self.runtime) as d:
    self.voice.synthesise(self.text,Path(d)/'first.wav',self.choice,self.speed,cancelled=self.cancelled)
  except Exception as e:self.error=type(e).__name__
