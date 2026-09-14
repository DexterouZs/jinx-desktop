"""One-time explicit model setup; all voice assets use the Linux engine's hashes."""
import hashlib,json,os,shutil,subprocess,sys,tempfile,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'app'))
from runtime_paths import models_dir,state_dir
from personal_profile import import_folder

def download(url,path,expected):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 def sha(p):
  h=hashlib.sha256()
  with p.open('rb') as f:
   for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
  return h.hexdigest()
 if path.exists() and sha(path)==expected:return
 temp=path.with_suffix(path.suffix+'.download');h=hashlib.sha256();last=0
 try:
  with urllib.request.urlopen(url,timeout=60) as response,temp.open('wb') as out:
   length=int(response.headers.get('Content-Length',0));count=0
   while True:
    block=response.read(1024*1024)
    if not block:break
    out.write(block);h.update(block);count+=len(block)
    if count-last>=100*1024*1024:print(f'{path.name}: {count//1024**2} MB'+(f' / {length//1024**2} MB' if length else ''),flush=True);last=count
  if h.hexdigest()!=expected:raise RuntimeError('Downloaded asset checksum mismatch: '+path.name)
  os.replace(temp,path)
 finally:temp.unlink(missing_ok=True)

def main():
 models=models_dir();models.mkdir(parents=True,exist_ok=True)
 if shutil.disk_usage(models).free<20*1024**3:raise RuntimeError('Allow at least 20 GB free for voice and both local language models.')
 print('Preparing the same Jinx voice and local assistant models…',flush=True)
 for spec in json.loads((ROOT/'assets.json').read_text()):
  if spec['path']=='ggml-base.bin':continue
  download(spec['url'],models/spec['path'],spec['sha256'])
 download('https://huggingface.co/HoppouAI/Breeze-TTS-2.cpp/resolve/main/breeze-tts-2-q8_0.gguf',models/'breeze-cpp/breeze-tts-2-q8_0.gguf','a02bcc4b69b0601032727f8040c4942149b1b73aa0f69022fe5aaa6a8f0ef879')
 from model_assets import wake_word
 wake_word(models)
 print('Preparing multilingual speech recognition…',flush=True)
 from huggingface_hub import snapshot_download
 snapshot_download('Systran/faster-whisper-base',local_dir=models/'whisper-base')
 # A local Ollama instance is owned by the launcher, on Jinx's dedicated port.
 env={**os.environ,'OLLAMA_HOST':'127.0.0.1:11435'}
 ollama=shutil.which('ollama') or str(Path(os.environ.get('LOCALAPPDATA',''))/'Programs/Ollama/ollama.exe')
 if not Path(ollama).is_file():raise RuntimeError('Install Ollama first, then run setup again.')
 for model in ['qwen3.5:4b','hf.co/ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF:IQ2_S']:
  print('Downloading '+model+'…',flush=True);subprocess.run([ollama,'pull',model],env=env,check=True)
 with tempfile.TemporaryDirectory() as folder:
  p=Path(folder)/'Modelfile';p.write_text('FROM hf.co/ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF:IQ2_S\nPARAMETER num_ctx 65536\n')
  subprocess.run([ollama,'create','qwen3.8:27b-jinx','-f',str(p)],env=env,check=True)
 print('Models are ready. Import your private NAS profile for your original voice and avatar.',flush=True)
def starter():
 row=json.loads((ROOT/'starter-avatar.json').read_text())
 download(row['url'],state_dir()/'assets/jinx-character.glb',row['sha256'])
 for spec in json.loads((ROOT/'assets.json').read_text()):
  if spec['path'].startswith('en_GB-alba'):
   download(spec['url'],models_dir()/spec['path'],spec['sha256'])
 path=state_dir()/'state.json';state=json.loads(path.read_text());state['voice']='piper_alba'
 temp=path.with_suffix('.tmp');temp.write_text(json.dumps(state));os.replace(temp,path)
 print('Starter avatar and Alba voice are ready. Prepare the AI models next.',flush=True)
if __name__=='__main__':
 if '--starter' in sys.argv:starter()
 else:main()
