"""Run on Windows with requirements.txt installed. Produces a frozen native app."""
from pathlib import Path
import importlib.metadata
import json
import shutil
import subprocess
import sys
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QImage, QPainter, QPainterPath, QPen, QColor

root = Path(__file__).resolve().parents[1]
win = root/'windows'
if sys.platform != 'win32':
    raise SystemExit('Build Windows binaries on Windows; use the Windows installer GitHub workflow.')
web = win/'web'
web.mkdir(exist_ok=True)
shutil.copytree(root/'app/avatar3d/vendor', web/'vendor', dirs_exist_ok=True)
shutil.copytree(root/'app/avatar3d/node_modules', web/'node_modules', dirs_exist_ok=True)
shutil.copy2(root/'starter-avatar.json', win/'starter-avatar.json')
shutil.copy2(root/'docs/jinx-launcher.jpg', win/'jinx-launcher.jpg')
# Standard application-icon rasterisation of the existing portrait and circular frame.
icon = QImage(256, 256, QImage.Format.Format_ARGB32); icon.fill(Qt.GlobalColor.transparent)
painter = QPainter(icon); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
clip = QPainterPath(); clip.addEllipse(QRectF(8, 8, 240, 240)); painter.setClipPath(clip)
painter.drawImage(QRectF(8, 8, 240, 240), QImage(str(win/'jinx-launcher.jpg')))
painter.setClipping(False); painter.setPen(QPen(QColor('#80cedb'), 7)); painter.drawEllipse(QRectF(8, 8, 240, 240)); painter.end()
if not icon.save(str(win/'jinx.ico')): raise RuntimeError('Could not create Windows icon')
licenses = win/'third-party-licenses'; licenses.mkdir(exist_ok=True)
manifest = []
for dist in importlib.metadata.distributions():
    name = dist.metadata['Name']; version = dist.version
    manifest.append({'name': name, 'version': version, 'license': dist.metadata.get('License-Expression') or dist.metadata.get('License', '')})
    for file in dist.files or []:
        if any(part.lower().startswith(('license', 'copying', 'notice')) for part in file.parts) and dist.locate_file(file).is_file():
            target = licenses/name/str(file).replace('../', '')
            target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(dist.locate_file(file), target)
(licenses/'dependencies.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
shutil.copy2(root/'LICENSE', win/'LICENSE.txt')
shutil.copy2(root/'docs/WINDOWS.md', win/'WINDOWS.txt')
shutil.copy2(root/'docs/ASSETS.md', win/'ASSETS.txt')
command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--windowed', '--onedir',
    '--name', 'Jinx', '--icon', str(win/'jinx.ico'), '--distpath', str(root/'dist'), '--workpath', str(root/'build/windows'),
    '--specpath', str(root/'build'), '--collect-all', 'faster_whisper', '--collect-all', 'sounddevice',
    '--hidden-import', 'win32com.client', '--hidden-import', 'pythoncom']
for name in ('avatar.html', 'jinx.ico', 'jinx-launcher.jpg', 'starter-avatar.json', 'LICENSE.txt', 'WINDOWS.txt', 'ASSETS.txt', 'web', 'third-party-licenses'):
    command.extend(['--add-data', str(win/name) + ':' + (name if (win/name).is_dir() else '.')])
subprocess.run(command + [str(win/'desktop_host.py')], check=True, cwd=root)

# Ship a relocatable Python runtime for the unchanged shared backend/Hermes.
# Keeping this separate avoids freezing away dynamically registered agent tools.
payload=root/'dist/Jinx'
runtime=payload/'runtime';runtime.mkdir(exist_ok=True)
base=Path(sys.base_prefix)
for name in ('python.exe','pythonw.exe','python3.dll','python312.dll','vcruntime140.dll','vcruntime140_1.dll','LICENSE.txt'):
    source=base/name
    if source.is_file():shutil.copy2(source,runtime/name)
shutil.copytree(base/'DLLs',runtime/'DLLs',dirs_exist_ok=True)
shutil.copytree(base/'Lib',runtime/'Lib',dirs_exist_ok=True,ignore=shutil.ignore_patterns('site-packages','__pycache__','test','idlelib','tkinter','ensurepip'))
shutil.copytree(base/'Lib/site-packages',runtime/'Lib/site-packages',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','pip','pip-*','PyInstaller','pyinstaller*'))
# Remove editable install links and user customisations: only the pinned source is used.
for p in (runtime/'Lib/site-packages').glob('*.pth'):p.unlink()
for p in (runtime/'Lib/site-packages').glob('sitecustomize*'):p.unlink()
shutil.copytree(root/'app',payload/'app',ignore=shutil.ignore_patterns('__pycache__','test_*.py','native','installer','voice-jinx','*.wav','*.glb','*.key','*.token'),dirs_exist_ok=True)
shutil.copytree(root/'hermes',payload/'hermes',ignore=shutil.ignore_patterns('.git','.github','website','tests','__pycache__'),dirs_exist_ok=True)
shutil.copytree(root/'dist/voice',payload/'voice',dirs_exist_ok=True)
windows=payload/'windows';windows.mkdir(exist_ok=True)
for name in ('backend_main.py','setup_models.py','personal_profile.py'):shutil.copy2(win/name,windows/name)
shutil.copy2(root/'assets.json',payload/'assets.json')
shutil.copy2(root/'docs/jinx-launcher.jpg',payload/'app/avatar3d/jinx-icon.jpg')
shutil.copy2(root/'app/PERSONALITY.md',payload/'app/PERSONALITY.md')
