#!/usr/bin/env python3
"""Reject private runtime data and credentials; report paths/categories, never values."""
from pathlib import Path
import argparse
import json
import os
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
PRIVATE_DIRS={'personal-assets','personal-profile','node_modules','.venv','backups','state','whatsapp-edge','firefox-profile','.codex','.ssh','.gnupg'}
PRIVATE_NAMES={'auth.json','credentials.json','secrets.json','state.json','settings.json','contacts.json','cookies.txt','cookies.sqlite','Login Data','Cookies'}
PRIVATE_SUFFIXES={'.key','.token','.pem','.p12','.pfx','.sqlite3','.sqlite','.db','.wav','.gguf','.glb','.onnx','.breeze'}
PATTERNS={
 'GitHub credential':rb'(?<![A-Za-z0-9_-])gh[pousr]_[A-Za-z0-9]{25,}',
 'API secret':rb'(?<![A-Za-z0-9_-])sk-[A-Za-z0-9_-]{25,}',
 'private key':rb'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----[\r\n ]+[A-Za-z0-9+/=\r\n]{40,}',
 'owner home path':rb'/home/davidsflow',
 'household subnet':rb'192\.168\.178\.\d+',
}

def private_path(path):
 p=Path(path)
 return bool(set(p.parts)&PRIVATE_DIRS or p.name in PRIVATE_NAMES or p.suffix in PRIVATE_SUFFIXES or p.name=='.env' or p.name.startswith('.env.'))

def inspect(path,data,private_values=()):
 findings=[]
 if private_path(path):findings.append('private/runtime file')
 if len(data)>5*1024**2:findings.append('unexpected large source file')
 # The scanner itself contains forbidden example patterns, never real credentials.
 if str(path).replace('\\','/')!='scripts/check-release.py':
  for name,pattern in PATTERNS.items():
   if re.search(pattern,data):findings.append(name)
 if any(value in data for value in private_values if len(value)>=8):findings.append('exact local credential match')
 return findings

def local_values():
 values=[]
 home=Path.home()
 for name in ('access.key','openai.key','morgen-api.key','home-assistant.token'):
  p=home/'.local/state/jinx'/name
  if p.is_file():values.append(p.read_bytes().strip())
 for name in ('JINX_GIT_TOKEN','GH_TOKEN','GITHUB_TOKEN'):
  if os.environ.get(name):values.append(os.environ[name].encode())
 # The caller opts into this local-only comparison. No value is logged or uploaded.
 try:
  auth=json.loads((home/'.codex/auth.json').read_text())
  def walk(value,key=''):
   if isinstance(value,dict):
    for k,v in value.items():walk(v,k)
   elif isinstance(value,str) and re.search('token|key|secret|password',key,re.I):values.append(value.encode())
  walk(auth)
 except (OSError,ValueError):pass
 return [v for v in values if len(v)>=8]

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--history',action='store_true')
 parser.add_argument('--local-secrets',action='store_true',help='Compare with local Jinx/Codex credentials without printing them')
 args=parser.parse_args();values=local_values() if args.local_secrets else []
 failures=[];count=0
 def check(path,data,label=None):
  nonlocal count
  count+=1
  failures.extend((label or str(path),reason) for reason in inspect(path,data,values))
 if (ROOT/'.git').exists():
  files=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).split(b'\0')
  for name in files:
   if name:
    p=Path(os.fsdecode(name));check(p,(ROOT/p).read_bytes())
  if args.history:
   rows=subprocess.check_output(['git','rev-list','--all','--objects'],cwd=ROOT,text=True).splitlines()
   for row in rows:
    oid,_,name=row.partition(' ')
    kind=subprocess.check_output(['git','cat-file','-t',oid],cwd=ROOT,text=True).strip()
    if kind in ('blob','commit','tag'):
     payload=subprocess.check_output(['git','cat-file',kind,oid],cwd=ROOT)
     # Commit messages have no file path; still scan credential values/signatures.
     check(name or kind,payload,oid[:12]+':'+(name or kind))
 else:
  for p in ROOT.rglob('*'):
   if p.is_file() and not any(x in p.relative_to(ROOT).parts for x in ('.git','__pycache__','dist')):check(p.relative_to(ROOT),p.read_bytes())
 for path,reason in sorted(set(failures)):print(path+': '+reason)
 if failures:return 1
 print('Release hygiene passed:',count,'files/objects; no matched secrets or private runtime assets.')
 return 0
if __name__=='__main__':raise SystemExit(main())
