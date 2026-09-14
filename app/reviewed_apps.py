"""Individually reviewed user applications; no caller-supplied installers."""
import hashlib, os, time, urllib.request
from pathlib import Path

VERSION='7.4.4'
URL='https://github.com/rafatosta/zapzap/releases/download/7.4.4/ZapZap-7.4.4-linux-x86_64.AppImage'
SHA256='2c2762574292fdf77bd799548bcbeb27d96456b63798491e22e842a64c93771e'
SIZE=206430899
APP=Path.home()/'.local/share/jinx/apps'/('ZapZap-'+VERSION+'-linux-x86_64.AppImage')
DESKTOP=Path.home()/'.local/share/applications/jinx-whatsapp.desktop'
ROOT=Path(__file__).resolve().parent
CONTENT=f'[Desktop Entry]\nType=Application\nName=WhatsApp (ZapZap)\nComment=Unofficial WhatsApp Web desktop client with Jinx voice review\nExec={ROOT}/.venv/bin/python {ROOT}/zapzap_control.py --open\nIcon={ROOT}/assets/zapzap.svg\nTerminal=false\nCategories=Network;InstantMessaging;\nKeywords=WhatsApp;ZapZap;Chat;\n'

def file_hash(path):
 with path.open('rb') as source:return hashlib.file_digest(source,'sha256').hexdigest()

def verified():
 try:
  return not APP.is_symlink() and not DESKTOP.is_symlink() and APP.stat().st_size==SIZE and DESKTOP.read_text()==CONTENT and os.access(APP,os.X_OK) and file_hash(APP)==SHA256
 except OSError:return False

def plan(knowledge):
 if DESKTOP.is_symlink() or (DESKTOP.exists() and DESKTOP.read_text()!=CONTENT):raise ValueError('An existing WhatsApp app launcher differs from this review. It has been preserved.')
 if APP.is_symlink():raise ValueError('The reviewed application path is a symlink; it has been preserved.')
 if APP.exists() and (APP.stat().st_size!=SIZE or file_hash(APP)!=SHA256):raise ValueError('The existing ZapZap AppImage differs from the reviewed checksum. It has been preserved.')
 installed=verified()
 return {'status':'already_installed' if installed else 'ready','install_kind':'reviewed_appimage','package':'zapzap','repository':'ZapZap maintainer GitHub release','version':VERSION,'installed_version':VERSION if installed else None,'description':'Standalone unofficial WhatsApp Web desktop app, with tray integration and notifications.','packages':[],'download_mib':round(SIZE/1048576,2),'catalog_fingerprint':SHA256,'url':URL,'sha256':SHA256,'created_at':time.time(),'knowledge':knowledge,'method':'Download the pinned maintainer AppImage, verify its SHA-256, and create a user application launcher. No administrator password.'}

def install():
 APP.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
 if not APP.exists():
  tmp=APP.with_suffix('.download-'+os.urandom(4).hex())
  try:
   with urllib.request.urlopen(URL,timeout=60) as response,tmp.open('xb') as output:
    size=0;digest=hashlib.sha256()
    while block:=response.read(1024*1024):
     size+=len(block)
     if size>SIZE:raise ValueError('The downloaded app is larger than the reviewed release.')
     output.write(block);digest.update(block)
   if size!=SIZE or digest.hexdigest()!=SHA256:raise ValueError('The ZapZap download did not match the reviewed checksum.')
   # Exclusive destination; no overwrite if another file appeared meanwhile.
   os.link(tmp,APP)
  finally:tmp.unlink(missing_ok=True)
 APP.chmod(0o700);DESKTOP.parent.mkdir(parents=True,exist_ok=True)
 if not DESKTOP.exists():
  with DESKTOP.open('x') as f:f.write(CONTENT)
 if not verified():raise ValueError('ZapZap installation could not be verified.')
