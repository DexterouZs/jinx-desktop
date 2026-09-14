"""Reviewed fixed social replies, distinct from private/user-generated speech caching."""
import hashlib,json,wave,io,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent
GREETING="Hi, I'm here."

def greeting(text):
 cleaned=' '.join(re.sub(r'[.,!?]+',' ',str(text).casefold()).split())
 # Name variants are only accepted inside a complete, harmless social greeting.
 return bool(re.fullmatch(r'(?:hi|hello|hey)(?: (?:jinx|jinks|jynx|jinxer|jynxer|there))?|(?:good (?:morning|afternoon|evening))(?: jinx)?',cleaned))

def load(text,choice,speed):
 # Only this fixed, non-action sentence is eligible for persistent audio reuse.
 if text!=GREETING or choice!='jinx_local':return None
 folder=ROOT/'voice-jinx/quick-replies'
 try:
  manifest=json.loads((folder/'manifest.json').read_text())
  for entry in manifest['replies']:
   if (entry['text'],entry['voice'],entry['speed'])!=(text,choice,speed):continue
   if entry['file']!=Path(entry['file']).name:return None
   for name in ['reference-short.wav','runtime.json']:
    if hashlib.sha256((ROOT/'voice-jinx'/name).read_bytes()).hexdigest()!=manifest['source_sha256'][name]:return None
   path=folder/entry['file']
   if path.stat().st_size>2*1024*1024:return None
   audio=path.read_bytes()
   if hashlib.sha256(audio).hexdigest()!=entry['sha256']:return None
   with wave.open(io.BytesIO(audio),'rb') as w:
    if w.getnchannels()!=1 or w.getsampwidth()!=2 or w.getnframes()==0:return None
   return audio,{'voice':choice,'fallback':'','engine':'recorded','cached':True,'fixed_reply':True}
 except (OSError,ValueError,KeyError,TypeError,wave.Error):return None
 return None
