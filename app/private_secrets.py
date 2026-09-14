"""Provider credentials stay local; Windows stores new keys in Credential Manager."""
import os
from pathlib import Path

def read(path):
 path=Path(path)
 if os.name=='nt':
  import win32cred
  try:
   value=win32cred.CredRead('Jinx/'+path.name,win32cred.CRED_TYPE_GENERIC)['CredentialBlob']
   return value.decode('utf-8') if isinstance(value,bytes) else value
  except Exception:pass
 return path.read_text().strip()

def exists(path):
 try:return bool(read(path))
 except OSError:return False

def write(path,value):
 path=Path(path);value=str(value).strip()
 if not value or len(value)>16000:raise ValueError('Enter a non-empty credential')
 if os.name=='nt':
  import win32cred
  win32cred.CredWrite({'Type':win32cred.CRED_TYPE_GENERIC,'TargetName':'Jinx/'+path.name,'CredentialBlob':value.encode('utf-8'),'Persist':win32cred.CRED_PERSIST_LOCAL_MACHINE,'UserName':'Jinx'},0)
 else:
  path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix('.new')
  fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
  with os.fdopen(fd,'w') as f:f.write(value)
  os.replace(temp,path)
