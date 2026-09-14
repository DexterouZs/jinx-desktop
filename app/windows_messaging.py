"""Dedicated, visible Edge WhatsApp profile; existing exact-send guards are reused."""
import os
from pathlib import Path
import subprocess
from runtime_paths import state_dir

def install():
 import zapzap_control
 def open_app():
  try:
   if zapzap_control.targets():return
  except Exception:pass
  paths=[Path(os.environ.get('PROGRAMFILES(X86)','C:/Program Files (x86)'))/'Microsoft/Edge/Application/msedge.exe',Path(os.environ.get('PROGRAMFILES','C:/Program Files'))/'Microsoft/Edge/Application/msedge.exe']
  edge=next((p for p in paths if p.is_file()),None)
  if edge is None:raise ValueError('Microsoft Edge is required for the visible WhatsApp app. Install Edge first.')
  profile=state_dir()/'whatsapp-edge';profile.mkdir(parents=True,exist_ok=True)
  subprocess.Popen([str(edge),'--user-data-dir='+str(profile),'--remote-debugging-address=127.0.0.1','--remote-debugging-port='+str(zapzap_control.PORT),'--remote-allow-origins='+zapzap_control.ORIGIN,'--no-first-run','--app=https://web.whatsapp.com/'],creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
 zapzap_control.open_app=open_app
