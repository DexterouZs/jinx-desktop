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
subprocess.run(command + [str(win/'jinx_windows.py')], check=True, cwd=root)
