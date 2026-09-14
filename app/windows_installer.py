"""Exact WinGet app selection, user review, version revalidation and install readback."""
import hashlib
import json
from pathlib import Path
import re
import secrets
import subprocess
import threading
import time
from runtime_paths import state_dir

PACKAGES={'spotify':'Spotify.Spotify','firefox':'Mozilla.Firefox','blender':'BlenderFoundation.Blender','vlc':'VideoLAN.VLC','steam':'Valve.Steam','discord':'Discord.Discord','gimp':'GIMP.GIMP.3','krita':'KDE.Krita','libreoffice':'TheDocumentFoundation.LibreOffice','thunderbird':'Mozilla.Thunderbird','visual studio code':'Microsoft.VisualStudioCode','obs studio':'OBSProject.OBSStudio','audacity':'Audacity.Audacity','inkscape':'Inkscape.Inkscape','7zip':'7zip.7zip','proton vpn':'Proton.ProtonVPN','edge':'Microsoft.Edge','google chrome':'Google.Chrome'}
ALIASES={'spottify':'spotify','spotify desktop':'spotify','libre office':'libreoffice','vlc media player':'vlc','vscode':'visual studio code','vs code':'visual studio code','code':'visual studio code','obs':'obs studio','chrome':'google chrome'}
LOCK=threading.Lock()

def canonical(query):
 q=str(query).strip().lower();q=ALIASES.get(q,q)
 if q in PACKAGES:return PACKAGES[q]
 match=next((p for p in PACKAGES.values() if p.lower()==q),None)
 return match or q

def winget(args,timeout=45):
 p=subprocess.run(['winget.exe',*args,'--disable-interactivity','--accept-source-agreements'],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
 return p

def installed(package):
 p=winget(['list','--id',package,'--exact','--source','winget'])
 if p.returncode:return None
 for line in p.stdout.splitlines():
  m=re.search(r'\s'+re.escape(package)+r'\s+(\S+)',line,re.I)
  if m:return m[1]
 return None

def plan(query):
 package=canonical(query)
 if package not in PACKAGES.values():return {'status':'choose_package','matches':[],'query':query,'detail':'Choose a known Windows app or review a new source separately.'}
 version=installed(package)
 if version:return {'status':'already_installed','package':package,'installed_version':version,'query':query}
 p=winget(['show','--id',package,'--exact','--source','winget'])
 if p.returncode:raise ValueError('WinGet could not resolve '+package+'. Open Microsoft App Installer and check its sources.')
 match=re.search(r'(?im)^Version:\s*(\S+)\s*$',p.stdout)
 if not match:raise ValueError('Could not verify the app version in WinGet output. No installation was started.')
 version=match[1]
 return {'status':'ready','query':query,'package':package,'repository':'Microsoft WinGet community repository','version':version,'packages':[package],'catalog_fingerprint':hashlib.sha256((package+'|'+version).encode()).hexdigest(),'description':p.stdout[-6000:],'install_kind':'winget'}

def review(plan):
 return 'Install '+plan['package']+' version '+plan['version']+' from the WinGet community repository. Windows may ask for normal UAC approval.\n\n'+plan['description']

def install(module):
 def jobs():
  results=[]
  for p in sorted(module.JOBS.glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:8]:
   try:
    row=json.loads(p.read_text())
    if row.get('state') in ('starting','installing'):
     import psutil
     if not psutil.pid_exists(row.get('pid',0)):
      row.update(state='uncertain',message='The installer stopped before verification. Check installed apps before retrying.');module.atomic(p,row)
    results.append({k:row.get(k) for k in ('id','proposal_id','package','state','message','version','updated_at')})
   except (OSError,ValueError):pass
  return results
 def launch(saved,proposal_id=None):
  if not LOCK.acquire(blocking=False):raise ValueError('An installation is already running')
  try:
   fresh=plan(saved['query'])
   if fresh['status']=='already_installed':return module.installed_message(fresh)
   if fresh.get('catalog_fingerprint')!=saved.get('catalog_fingerprint'):raise ValueError('The package version changed. Ask for a new installation preview.')
   identifier=secrets.token_hex(12);path=module.JOBS/(identifier+'.json')
   import os
   job={'id':identifier,'proposal_id':proposal_id,'package':fresh['package'],'state':'starting','message':'Starting the Windows installer…','updated_at':time.time(),'pid':os.getpid()}
   module.atomic(path,job)
   def work():
    def update(state,message):job.update(state=state,message=message,updated_at=time.time());module.atomic(path,job)
    try:
     update('installing','Installing the reviewed version; respond to Windows UAC if shown.')
     process=subprocess.Popen(['winget.exe','install','--id',fresh['package'],'--exact','--source','winget','--version',fresh['version'],'--interactive','--accept-source-agreements','--accept-package-agreements'],creationflags=getattr(subprocess,'CREATE_NEW_CONSOLE',0))
     job['pid']=process.pid;module.atomic(path,job)
     code=process.wait();found=installed(fresh['package'])
     if code or found is None:raise ValueError('WinGet finished without verifying this app. Check the installer window before retrying.')
     if found!=fresh['version']:raise ValueError('The installed version differs from the reviewed version; check Software installs.')
     job['version']=found;update('installed',fresh['package']+' installed and version verified.')
    except Exception as e:update('failed',str(e))
    finally:LOCK.release()
   threading.Thread(target=work,daemon=True).start()
   return 'Installing '+fresh['package']+'. Windows may ask for UAC approval. Check Software installs for verification.'
  except BaseException:LOCK.release();raise
 def request_review(identifier):
  from windows_workbench import ui_request
  result=ui_request('settings',{'review':identifier},timeout=4)
  return bool(result.get('shown'))
 module.canonical_query=canonical;module.build_plan=plan;module.review_text=review
 module.installed=installed;module.jobs=jobs;module.launch=launch;module.request_review=request_review
 module.register_apps=lambda package:[] # Start menu catalogue is rediscovered on every launch.
 module.search=lambda query:plan(query)
 module.installed_message=lambda p:p['package']+' is installed ('+p['installed_version']+').'
