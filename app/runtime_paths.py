"""One path contract for the shared Linux and Windows application."""
import os
from pathlib import Path

def state_dir():
 return Path(os.environ.get('JINX_STATE_DIR', Path(os.environ.get('LOCALAPPDATA',Path.home()))/'Jinx'/'data' if os.name=='nt' else Path.home()/'.local/state/jinx'))
def models_dir():
 return Path(os.environ.get('JINX_MODELS_DIR', Path(os.environ.get('LOCALAPPDATA',Path.home()))/'Jinx'/'models' if os.name=='nt' else Path.home()/'.local/share/jinx/models'))
def config_dir():
 return Path(os.environ.get('JINX_CONFIG_DIR', state_dir()/'connections' if os.name=='nt' else Path.home()/'.config/jinx'))
def runtime_dir():
 path=Path(os.environ.get('XDG_RUNTIME_DIR',state_dir()/'runtime' if os.name=='nt' else f'/run/user/{os.getuid()}'))
 path.mkdir(parents=True,exist_ok=True)
 return path
