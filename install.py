#!/usr/bin/env python3
"""Jinx installer for Arch/CachyOS KDE. No credentials are shipped or requested."""
import argparse
import hashlib
import json
import os
import secrets
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parent
HERMES = 'b2aa855b626ff8688eb34b95c60ee8b6a4af3679'
PACKAGES = ['uv','git','cmake','ninja','nodejs','npm','qt6-webengine',
            'qt6-declarative','qt6-tools','layer-shell-qt','portaudio','pipewire',
            'wireplumber','ffmpeg','whisper-cpp','ollama','libnotify',
            'tesseract','tesseract-data-eng','vulkan-headers','vulkan-icd-loader','shaderc']


def run(argv, **kwargs):
    print('→', ' '.join(map(str, argv)), flush=True)
    return subprocess.run(list(map(str, argv)), check=True, **kwargs)


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def download(row, target):
    if target.is_file() and sha(target)==row['sha256']:return
    target.parent.mkdir(parents=True,exist_ok=True)
    temporary=target.with_suffix(target.suffix+'.download')
    print('Downloading',target.name,flush=True)
    try:
        with urllib.request.urlopen(row['url'],timeout=60) as response,temporary.open('wb') as out:
            shutil.copyfileobj(response,out)
        if sha(temporary)!=row['sha256']:raise RuntimeError('Checksum mismatch: '+target.name)
        temporary.replace(target)
    finally:temporary.unlink(missing_ok=True)


def requirements():
    if not shutil.which('pacman'):
        raise RuntimeError('This installer targets Arch/CachyOS with KDE Plasma 6. See docs/INSTALL.md for requirements.')
    missing=[]
    for name in PACKAGES:
        # -T accepts installed providers such as wl-clipboard-rs too.
        if subprocess.run(['pacman','-T',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:missing.append(name)
    return missing


def prepare(target):
    """Build in a separate directory before replacing any installed code."""
    shutil.copytree(ROOT/'app',target,dirs_exist_ok=True)
    run(['uv','venv','--python','3.12','--relocatable',target/'.venv'])
    python=target/'.venv/bin/python'
    run(['uv','pip','install','--python',python,'-r',ROOT/'requirements.lock'])
    # Hermes deliberately requires an editable checkout, not a wheel. Keep its
    # pinned source outside the staged app so moving the app cannot break .pth.
    hermes=Path.home()/'.local/share/jinx/runtimes'/('hermes-'+HERMES)
    if not hermes.exists():
        hermes.mkdir(parents=True)
        run(['git','init',hermes])
        run(['git','-C',hermes,'remote','add','origin','https://github.com/NousResearch/hermes-agent.git'])
        run(['git','-C',hermes,'fetch','--depth','1','origin',HERMES])
        run(['git','-C',hermes,'checkout','--detach','FETCH_HEAD'])
    actual=subprocess.check_output(['git','-C',hermes,'rev-parse','HEAD'],text=True).strip()
    if actual!=HERMES:raise RuntimeError('Unexpected Hermes revision; refusing to install it.')
    run(['uv','pip','install','--python',python,'--no-deps','-e',hermes])
    run(['uv','pip','check','--python',python])
    run(['npm','ci','--ignore-scripts','--no-audit','--no-fund'],cwd=target/'avatar3d')
    run(['cmake','-S',target/'avatar3d/native','-B',target/'avatar3d/build','-G','Ninja','-DCMAKE_BUILD_TYPE=Release'])
    run(['cmake','--build',target/'avatar3d/build','--parallel','4'])
    run(['cmake','-S',target/'installer','-B',target/'installer/build','-G','Ninja','-DCMAKE_BUILD_TYPE=Release'])
    run(['cmake','--build',target/'installer/build','--parallel','4'])
    run([python,'-c','import jinx_test_support; import jinx; from run_agent import AIAgent; print("Jinx isolated import: OK")'],cwd=target)


def unit_path(path):
    return '"'+str(path).replace('\\','\\\\').replace('"','\\"').replace('%','%%')+'"'


def configure(target, home, backup):
    units=home/'.config/systemd/user';units.mkdir(parents=True,exist_ok=True)
    binaries=home/'.local/bin';binaries.mkdir(parents=True,exist_ok=True)
    desktop=home/'.local/share/applications';desktop.mkdir(parents=True,exist_ok=True)
    icon=home/'.local/share/icons/hicolor/scalable/apps/jinx.svg';icon.parent.mkdir(parents=True,exist_ok=True)
    def write(path,content,mode=0o644):
        if path.exists():
            previous=backup/path.relative_to(home);previous.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,previous)
        path.write_text(content);path.chmod(mode)
    for name in ('jinx','jinx-desktop-control'):
        write(binaries/name,(ROOT/'bin'/name).read_text(),0o755)
    # No enable/autostart: the launcher starts the lightweight wake widget.
    model=f'''[Unit]
Description=Jinx local model server
[Service]
ExecStart=/usr/bin/ollama serve
Environment=OLLAMA_HOST=127.0.0.1:11435
Environment=OLLAMA_VULKAN=1
Environment=OLLAMA_IGPU_ENABLE=1
Environment=OLLAMA_NO_CLOUD=1
Environment=OLLAMA_KEEP_ALIVE=60s
Environment=OLLAMA_MAX_LOADED_MODELS=1
Environment=OLLAMA_NUM_PARALLEL=1
Environment=OLLAMA_CONTEXT_LENGTH=65536
Environment=OLLAMA_FLASH_ATTENTION=1
Environment=OLLAMA_KV_CACHE_TYPE=q4_0
Environment="OLLAMA_MODELS={home}/.local/share/jinx/models/ollama"
TimeoutStopSec=6
UMask=0077
'''
    backend=f'''[Unit]
Description=Jinx personal assistant
Requires=jinx-model.service
After=jinx-model.service
[Service]
ExecStart={unit_path(target/'.venv/bin/python')} {unit_path(target/'jinx.py')}
WorkingDirectory={unit_path(target)}
Environment=PYTHONUNBUFFERED=1
Environment=HERMES_NO_BROWSER=1
Environment=HERMES_DISABLE_TELEMETRY=1
Environment=DO_NOT_TRACK=1
NoNewPrivileges=yes
TimeoutStopSec=6
UMask=0077
Restart=on-failure
'''
    avatar=f'''[Unit]
Description=Jinx desktop companion
After=plasma-plasmashell.service
[Service]
ExecCondition={unit_path(binaries/'jinx-desktop-control')} can-run
ExecStartPre=/usr/bin/python3 {unit_path(target/'sleep_control.py')} sleep
ExecStart={unit_path(target/'avatar3d/build/jinx-desktop')}
WorkingDirectory={unit_path(target/'avatar3d')}
TimeoutStopSec=6
UMask=0077
Restart=on-failure
'''
    for name,body in [('jinx-model',model),('jinx',backend),('jinx-desktop',avatar)]:write(units/(name+'.service'),body)
    write(icon,(ROOT/'docs/jinx.svg').read_text())
    write(desktop/'jinx.desktop','[Desktop Entry]\nType=Application\nName=Jinx\nComment=Your voice-enabled desktop companion\nExec=systemctl --user start jinx-desktop.service\nIcon=jinx\nTerminal=false\nCategories=Utility;\n')
    write(desktop/'jinx-settings.desktop','[Desktop Entry]\nType=Application\nName=Jinx Settings\nExec='+str(binaries/'jinx')+' open\nIcon=jinx\nTerminal=false\nCategories=Utility;\nNoDisplay=true\n')
    state=home/'.local/state/jinx';state.mkdir(parents=True,exist_ok=True,mode=0o700)
    # The native request interceptor reads this at startup, before the sleeping
    # backend exists. Seed it once so first-run wake can authenticate too.
    if not (state/'access.key').exists():write(state/'access.key',secrets.token_hex(32)+'\n',0o600)
    # Existing credentials/settings/memory are never overwritten.
    if not (state/'state.json').exists():
        original_voice=(state/'assets/reference-short.wav').is_file() and (home/'.local/share/jinx/models/breeze-cpp/libjinx-breeze.so').is_file()
        data={'ai_mode':'local_fast','speech_engine':'cpu','voice':'breeze_tts2' if original_voice else 'piper_alba','voice_speed':1.0,
              'listening':False,'speak':True,'memory':'','reminders':[],'pending':[],
              'episodic_memory':True,'learn_preferences':True}
        write(state/'state.json',json.dumps(data,indent=2)+'\n',0o600)
    config=state/'hermes/config.yaml';config.parent.mkdir(parents=True,exist_ok=True)
    if not config.exists():write(config,'tools:\n  tool_search:\n    enabled: off\n',0o600)
    reminder=f'''[Unit]
Description=Jinx due reminders (no AI or avatar)
[Service]
Type=oneshot
ExecStart={unit_path(target/'.venv/bin/python')} {unit_path(target/'reminder_delivery.py')}
WorkingDirectory={unit_path(target)}
UMask=0077
NoNewPrivileges=yes
'''
    timer='[Unit]\nDescription=Check Jinx reminders each minute\n[Timer]\nOnCalendar=*-*-* *:*:00\nPersistent=true\nAccuracySec=5s\n[Install]\nWantedBy=timers.target\n'
    write(units/'jinx-reminders.service',reminder)
    write(units/'jinx-reminders.timer',timer)
    run(['systemctl','--user','daemon-reload'])
    run(['systemctl','--user','enable','--now','jinx-reminders.timer'])


def assets(target,home):
    models=home/'.local/share/jinx/models'
    import importlib.util
    spec=importlib.util.spec_from_file_location('jinx_model_assets',ROOT/'app/model_assets.py')
    model_assets=importlib.util.module_from_spec(spec);spec.loader.exec_module(model_assets)
    model_assets.wake_word(models)
    for row in json.loads((ROOT/'assets.json').read_text()):download(row,models/row['path'])
    private=ROOT/'personal-assets'
    if private.exists():
        # NAS-only visual/voice files, never accounts, contacts or chat history.
        for p in private.rglob('*'):
            if p.is_file():
                dest=target/p.relative_to(private);dest.parent.mkdir(parents=True,exist_ok=True)
                if not dest.exists():shutil.copy2(p,dest)
    profile=ROOT/'personal-profile'
    if (profile/'profile.json').is_file():
        import importlib.util
        spec=importlib.util.spec_from_file_location('jinx_private_profile',ROOT/'windows/personal_profile.py')
        transfer=importlib.util.module_from_spec(spec);spec.loader.exec_module(transfer)
        state=home/'.local/state/jinx'
        transfer.import_folder(profile,state,models)
        for name,relative in [('reference-short.wav','voice-jinx/reference-short.wav'),('jinx-character.glb','avatar3d/avatars/jinx-character.glb'),('wake-jinx.jpg','avatar3d/native/icons/wake-jinx.jpg'),('sleep-skull.jpg','avatar3d/native/icons/sleep-skull.jpg')]:
            source=state/'assets'/name
            if source.is_file():
                dest=target/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
        run([sys.executable,ROOT/'windows/voice-build.py'])
        voice_dir=models/'breeze-cpp';voice_dir.mkdir(parents=True,exist_ok=True)
        for library in (ROOT/'dist/voice').glob('*.so*'):shutil.copy2(library,voice_dir/library.name)
        download({'url':'https://huggingface.co/HoppouAI/Breeze-TTS-2.cpp/resolve/main/breeze-tts-2-q8_0.gguf','sha256':'a02bcc4b69b0601032727f8040c4942149b1b73aa0f69022fe5aaa6a8f0ef879'},voice_dir/'breeze-tts-2-q8_0.gguf')
        settings=state/'state.json'
        if settings.is_file():
            previous=settings.with_name('state.before-profile-import.json')
            if not previous.exists():shutil.copy2(settings,previous)
            data=json.loads(settings.read_text());data.update(voice='breeze_tts2',voice_speed=1.0)
            temporary=settings.with_suffix('.tmp');temporary.write_text(json.dumps(data,indent=2));temporary.chmod(0o600);temporary.replace(settings)
    avatar=target/'avatar3d/avatars/jinx-character.glb'
    if not avatar.exists():
        row=json.loads((ROOT/'starter-avatar.json').read_text())
        print('Installing optional starter avatar (CC BY-NC 4.0, personal/non-commercial use).')
        download(row,avatar)
    image=target/'avatar3d/jinx-icon.jpg'
    if not image.exists():
        shutil.copy2(ROOT/'docs/jinx.jpg',image)
    for name in ['wake-jinx.jpg','sleep-skull.jpg']:
        icon=target/'avatar3d/native/icons'/name;icon.parent.mkdir(parents=True,exist_ok=True)
        if not icon.exists():shutil.copy2(ROOT/'docs/jinx.jpg',icon)


def pull_models(mode):
    if mode=='none':return
    run(['systemctl','--user','start','jinx-model.service'])
    env={**os.environ,'OLLAMA_HOST':'127.0.0.1:11435'}
    try:
        for _ in range(60):
            try:urllib.request.urlopen('http://127.0.0.1:11435/api/tags',timeout=2).close();break
            except OSError:time.sleep(.5)
        run(['ollama','pull','qwen3.5:4b'],env=env)
        if mode=='full':
            source='hf.co/ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF:IQ2_S'
            run(['ollama','pull',source],env=env)
            with tempfile.NamedTemporaryFile(mode='w',suffix='.Modelfile') as f:
                f.write('FROM '+source+'\nPARAMETER num_ctx 65536\n');f.flush()
                run(['ollama','create','qwen3.8:27b-jinx','-f',f.name],env=env)
    finally:run(['systemctl','--user','stop','jinx-model.service'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true',help='Report prerequisites; do not change anything')
    parser.add_argument('--install-deps',action='store_true',help='Install missing repository packages using sudo/pacman')
    parser.add_argument('--prepare-only',type=Path,metavar='DIRECTORY',help='Build/import-check in isolation, without service changes')
    parser.add_argument('--update',action='store_true',help='Back up and update an existing ~/Jinx installation')
    parser.add_argument('--models',choices=['full','everyday','none'],default='full')
    args=parser.parse_args()
    if os.getuid()==0:raise RuntimeError('Run as your desktop user, not root.')
    os.umask(0o077)
    missing=requirements()
    if args.check:
        print(json.dumps({'missing_packages':missing,'existing_install':(Path.home()/'Jinx').exists(),
                          'models':'Downloads approximately 13GB for full local models; existing files are reused.',
                          'automatic_login_start':False},indent=2));return
    if missing:
        if not args.install_deps:raise RuntimeError('Missing packages: '+', '.join(missing)+'. Rerun with --install-deps.')
        run(['sudo','pacman','-S','--needed',*missing])
    if args.prepare_only:
        target=args.prepare_only.expanduser().resolve()
        if target.exists():raise RuntimeError('Build directory already exists; choose a new empty location.')
        prepare(target);return
    home=Path.home();target=home/'Jinx'
    if target.exists() and not args.update:raise RuntimeError('Jinx is already installed. It was left untouched. Use --update to back up and update it.')
    stage=home/('.jinx-install-'+time.strftime('%Y%m%d-%H%M%S'))
    prepare(stage)
    if target.exists():
        for name in ['avatar3d/avatars','avatar3d/native/icons','avatar3d/jinx-icon.jpg','voice-jinx']:
            source=target/name;dest=stage/name
            if source.is_dir():shutil.copytree(source,dest,dirs_exist_ok=True)
            elif source.is_file():dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
    assets(stage,home)
    backup=home/'.local/share/jinx/installer-backups'/time.strftime('%Y%m%d-%H%M%S');backup.mkdir(parents=True)
    for unit in ('jinx-desktop.service','jinx.service','jinx-model.service'):
        if subprocess.run(['systemctl','--user','is-active','--quiet',unit]).returncode==0:
            run(['systemctl','--user','stop',unit])
    if target.exists():target.rename(backup/'previous-app')
    stage.rename(target)
    try:configure(target,home,backup);pull_models(args.models)
    except Exception:
        print('Installation did not finish. Your previous app is preserved at',backup/'previous-app',file=sys.stderr)
        raise
    print('\nJinx is installed. Open Jinx from the application menu. AI and avatar start only on demand; a lightweight helper delivers reminders.\nBackup:',backup)


if __name__=='__main__':
    try:main()
    except (RuntimeError,OSError,subprocess.CalledProcessError) as error:
        print('\nInstallation stopped:',error,file=sys.stderr);sys.exit(1)
