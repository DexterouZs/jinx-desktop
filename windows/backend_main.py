"""Start the bundled shared backend with native Windows primitives."""
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(ROOT/'app'),str(ROOT/'hermes')]
os.environ.setdefault('JINX_BREEZE_LIBRARY',str(ROOT/'voice/jinx-breeze.dll'))
os.environ.setdefault('JINX_BREEZE_ALLOW_CPU','1')
from runtime_paths import state_dir,runtime_dir
os.environ['XDG_RUNTIME_DIR']=str(runtime_dir())
os.environ['JINX_VOICE_REFERENCE']=str(state_dir()/'assets/reference-short.wav')
import jinx
import windows_platform
windows_platform.install(jinx)
if '--check' in sys.argv:
 import sounddevice,faster_whisper,onnxruntime
 from run_agent import AIAgent
 from tools.registry import registry
 from breeze_cpp_runtime import C
 dll=C.CDLL(os.environ['JINX_BREEZE_LIBRARY'])
 for name in ['jinx_breeze_init','jinx_breeze_generate','jinx_breeze_free','jinx_breeze_error']:getattr(dll,name)
 print('Shared backend, Hermes, Windows speech and Breeze ABI imported.',flush=True)
else:jinx.main()
