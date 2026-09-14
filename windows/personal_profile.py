"""Import only named, hashed visual/voice assets; never credentials or arbitrary paths."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import zipfile
import os

ALLOWED={'jinx-character.glb':100*1024**2,'reference-short.wav':10*1024**2,'wake-jinx.jpg':2*1024**2,'sleep-skull.jpg':2*1024**2,'breeze-tts-2-q8_0.gguf':4*1024**3}
BREEZE_SHA='a02bcc4b69b0601032727f8040c4942149b1b73aa0f69022fe5aaa6a8f0ef879'

def digest(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()

def import_folder(source,data,models):
 source=Path(source);data=Path(data);models=Path(models)
 manifest=json.loads((source/'profile.json').read_text(encoding='utf-8'))
 if manifest.get('format')!=1 or not isinstance(manifest.get('files'),dict):raise ValueError('Unsupported Jinx profile')
 staged=[]
 for name,expected in manifest['files'].items():
  if name not in ALLOWED:raise ValueError('Profile contains an unsupported file')
  p=source/name
  if p.is_symlink() or not p.is_file() or not 0<p.stat().st_size<=ALLOWED[name]:raise ValueError('Invalid profile asset '+name)
  if digest(p)!=expected:raise ValueError('Checksum mismatch: '+name)
  if name.endswith('.gguf') and expected!=BREEZE_SHA:raise ValueError('This is not the matching Breeze voice model')
  target=models/'breeze-cpp'/name if name.endswith('.gguf') else data/'assets'/name
  staged.append((p,target))
 if not {'reference-short.wav','jinx-character.glb'}<=set(manifest['files']):raise ValueError('This profile needs the original avatar and voice reference')
 # All input is verified before changing installed assets. Preserve previous assets.
 backup=data/'profile-backups'/__import__('datetime').datetime.now().strftime('%Y%m%d-%H%M%S')
 for source,target in staged:
  target.parent.mkdir(parents=True,exist_ok=True)
  if target.exists():
   if digest(target)==digest(source):continue
   backup.mkdir(parents=True,exist_ok=True);shutil.copy2(target,backup/target.name)
  temp=target.with_suffix(target.suffix+'.new');shutil.copyfile(source,temp);os.replace(temp,target)
 return [target.name for _,target in staged]

def import_zip(path,data,models):
 with tempfile.TemporaryDirectory(prefix='jinx-profile-') as tmp,zipfile.ZipFile(path) as z:
  selected=[i for i in z.infolist() if i.filename.startswith('Jinx-Windows/personal-profile/') and not i.is_dir()]
  if not selected:raise ValueError('Choose the Windows NAS ZIP, or its extracted personal-profile folder')
  for entry in selected:
   name=entry.filename.removeprefix('Jinx-Windows/personal-profile/')
   maximum=100000 if name=='profile.json' else ALLOWED.get(name,0)
   if not maximum or entry.file_size>maximum:raise ValueError('Unexpected profile archive content')
   with z.open(entry) as src,(Path(tmp)/name).open('xb') as dest:shutil.copyfileobj(src,dest,1024*1024)
  return import_folder(tmp,data,models)
