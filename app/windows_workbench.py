"""Explicit document sharing, clipboard and desktop notifications on Windows."""
import json
import os
from pathlib import Path
import secrets
import time
from runtime_paths import runtime_dir

def ui_request(kind,fields=None,timeout=300):
 from software_installer import atomic
 folder=runtime_dir()/'ui-requests';folder.mkdir(parents=True,exist_ok=True)
 identifier=secrets.token_hex(16);request=folder/(identifier+'.json');reply=folder/(identifier+'.reply')
 atomic(request,{'kind':kind,'fields':fields or {},'expires':time.time()+timeout})
 try:
  deadline=time.monotonic()+timeout
  while time.monotonic()<deadline:
   if reply.exists():
    result=json.loads(reply.read_text())
    if result.get('error'):raise ValueError(result['error'])
    return result
   time.sleep(.05)
  raise ValueError('The Jinx desktop window did not respond. No action was confirmed.')
 finally:request.unlink(missing_ok=True);reply.unlink(missing_ok=True)

def install(backend,workbench,reminders):
 def clipboard(self):
  import win32clipboard
  win32clipboard.OpenClipboard()
  try:text=win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
  finally:win32clipboard.CloseClipboard()
  return self.set_text(text,'Copied text')
 def choose_file(self):
  result=ui_request('document')
  return self.load_file(result['path']) if result.get('path') else {'cancelled':True}
 load=workbench.Workbench.load_file
 def load_file(self,path):
  path=Path(path).resolve(strict=True)
  if path.suffix.lower()!='.pdf':return load(self,path)
  if not path.is_file() or path.stat().st_size>workbench.MAX_FILE:raise ValueError('Choose a document smaller than 16 MB')
  from pypdf import PdfReader
  reader=PdfReader(path)
  if reader.is_encrypted:raise ValueError('Unlock the PDF before sharing it')
  text='\n'.join(page.extract_text() or '' for page in reader.pages[:200])
  self.set_text(text,path.name);self.source_note='First 200 PDF pages; scanned pictures are not included.'
  return self.metadata()
 workbench.Workbench.clipboard=clipboard;workbench.Workbench.choose_file=choose_file;workbench.Workbench.load_file=load_file
 original=backend.subprocess
 # Only this module's desktop bridge uses the adapter; subprocess globally stays untouched.
 class DesktopSubprocess:
  def __getattr__(self,name):return getattr(original,name)
  def run(self,args,**kw):
   if args and args[0]=='qdbus6' and args[-2:] and 'setClipboardContents' in ' '.join(args[:-1]):
    import win32clipboard
    win32clipboard.OpenClipboard()
    try:win32clipboard.EmptyClipboard();win32clipboard.SetClipboardText(args[-1],win32clipboard.CF_UNICODETEXT)
    finally:win32clipboard.CloseClipboard()
    return original.CompletedProcess(args,0,'','')
   return original.run(args,**kw)
 backend.subprocess=DesktopSubprocess()
 class Notifications:
  def __getattr__(self,name):return getattr(original,name)
  def run(self,args,**kwargs):
   if args and args[0]=='notify-send':
    result=ui_request('notification',{'title':args[-2],'text':args[-1]},timeout=4)
    if not result.get('delivered'):raise RuntimeError('Desktop notification was not accepted')
    return original.CompletedProcess(args,0,'','')
   return original.run(args,**kwargs)
 reminders.subprocess=Notifications()
