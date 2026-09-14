"""Build the same pinned Breeze engine and Jinx C ABI for Windows or Linux."""
from pathlib import Path
import os,shutil,subprocess,sys
root=Path(__file__).resolve().parents[1]
work=root/'build/voice-source';work.mkdir(parents=True,exist_ok=True)
source=work/'upstream'
revision='a5436642d4c64304b398ceeda9b8fce4577bfdb1'
def run(args,**kw):subprocess.run(list(map(str,args)),check=True,**kw)
if not source.exists():
 run(['git','clone','--filter=blob:none','--no-checkout','https://github.com/HoppouAI/Breeze-TTS-2.cpp',source])
run(['git','-C',source,'checkout','--detach',revision])
run(['git','-C',source,'submodule','update','--init','--recursive'])
if subprocess.check_output(['git','-C',source,'rev-parse','HEAD'],text=True).strip()!=revision:raise RuntimeError('Unexpected Breeze source')
shutil.copy2(root/'windows/voice-CMakeLists.txt',work/'CMakeLists.txt')
shutil.copy2(root/'app/breeze_cpp_bridge.cpp',work/'bridge.cpp')
build=root/'build/voice'
run(['cmake','-S',work,'-B',build,'-DCMAKE_BUILD_TYPE=Release'])
run(['cmake','--build',build,'--config','Release','--parallel','4'])
target=root/'dist/voice';target.mkdir(parents=True,exist_ok=True)
for p in build.rglob('*.dll' if os.name=='nt' else '*.so*'):
 if p.is_file():shutil.copy2(p,target/p.name)
if not list(target.glob('*jinx-breeze*')):raise RuntimeError('Voice bridge was not produced')
shutil.copy2(source/'LICENSE',target/'Breeze-LICENSE.txt')
