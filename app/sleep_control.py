from runtime_paths import state_dir, models_dir, config_dir, runtime_dir
from file_locks import fcntl
"""Skull control: stop AI and pause wallpaper, with a light native wake button."""
import importlib.machinery,importlib.util,json,os,subprocess,sys
from pathlib import Path
os.umask(0o077)
RUNTIME=runtime_dir()
FLAG=RUNTIME/'jinx-skull-sleep.json'
def desktop_controls():
 loader=importlib.machinery.SourceFileLoader('desktop_controls',str(Path.home()/'.local/bin/jinx-desktop-control'))
 spec=importlib.util.spec_from_loader('desktop_controls',loader);module=importlib.util.module_from_spec(spec);loader.exec_module(module);return module
def apply(sleep):
 controls=desktop_controls()
 with (RUNTIME/'jinx-skull-control.lock').open('w') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  if sleep:
   if not FLAG.exists():
    try:wallpapers=controls.wallpapers()
    except Exception:wallpapers=[]
    temp=FLAG.with_suffix('.tmp');temp.write_text(json.dumps({'wallpapers':wallpapers}));temp.replace(FLAG)
   saved=json.loads(FLAG.read_text())
   try:controls.set_wallpapers(saved['wallpapers'],True)
   finally:subprocess.run(['systemctl','--user','stop','jinx.service','jinx-model.service'],check=True,timeout=30)
  else:
   subprocess.run(['systemctl','--user','start','jinx.service','jinx-model.service'],check=True,timeout=30)
   try:
    if FLAG.exists():
     saved=json.loads(FLAG.read_text());controls.set_wallpapers(saved['wallpapers']);FLAG.unlink()
   except Exception:
    subprocess.run(['systemctl','--user','stop','jinx.service','jinx-model.service'],check=True,timeout=30)
    raise
if __name__=='__main__':
 if len(sys.argv)!=2 or sys.argv[1] not in ('sleep','wake'):raise SystemExit('Use sleep or wake')
 apply(sys.argv[1]=='sleep')
