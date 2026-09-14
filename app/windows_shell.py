"""Bounded Windows diagnostic commands; arbitrary script evaluation is not exposed."""
import re
import subprocess
import time
import shlex
from pathlib import Path

COMMANDS={
 'ipconfig':{'/all','/displaydns'},'ping':set(),'tracert':set(),'nslookup':set(),
 'whoami':set(),'hostname':set(),'systeminfo':set(),'tasklist':set(),
 'powercfg':{'/a','/lastwake','/requests','/getactivescheme'},
 'get-process':set(),'get-service':set(),'get-netadapter':set(),'get-netipconfiguration':set(),
 'get-volume':set(),'get-physicaldisk':set(),'get-computerinfo':set(),
}

def run(command,timeout=30,cwd=None):
 from shell_tools import redact
 from windows_platform import powershell,NO_WINDOW
 start=time.monotonic();result={'ok':False,'exit_code':None,'stdout':'','stderr':'','seconds':0,'truncated':False,'denied':None}
 try:
  if not isinstance(command,str) or len(command)>400 or re.search(r'[;|&<>`$(){}\r\n]',command):raise ValueError('Use one supported Windows diagnostic command; scripts and shell chaining require separate review.')
  words=shlex.split(command);name=words[0].lower().removesuffix('.exe') if words else ''
  if name not in COMMANDS:raise ValueError('Use a Windows diagnostic command: '+', '.join(COMMANDS))
  args=words[1:]
  if name in ('ping','tracert','nslookup'):
   if len(args)!=1 or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9.:-]{0,200}',args[0]):raise ValueError('Supply one hostname or IP address')
  elif any(x.lower() not in COMMANDS[name] for x in args):raise ValueError('Unsupported command arguments')
  timeout=max(1,min(30,int(timeout)))
  if name.startswith('get-'):output=powershell(name+' | Select-Object -First 60 | Out-String -Width 160',timeout)
  else:
   with __import__('tempfile').TemporaryFile() as out:
    p=subprocess.Popen([name+'.exe',*args],cwd=str(Path.home()),stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,creationflags=NO_WINDOW)
    try:p.wait(timeout=timeout)
    except subprocess.TimeoutExpired:p.kill();p.wait();raise ValueError('Diagnostic timed out')
    out.seek(0);output=out.read(24000).decode(errors='replace')
    if p.returncode:result['stderr']='Command returned '+str(p.returncode)
    result['exit_code']=p.returncode
  result.update(ok=not result['stderr'],stdout=redact(output)[:12000],truncated=len(output)>12000)
 except Exception as e:result['denied']=str(e)
 result['seconds']=round(time.monotonic()-start,2)
 return result
