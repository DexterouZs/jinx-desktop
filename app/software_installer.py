from runtime_paths import state_dir, models_dir, config_dir, runtime_dir
from file_locks import fcntl
"""Reviewed repository installs. The model gets no shell or privilege credential."""
import configparser, datetime,  hashlib, json, os, re, secrets, subprocess, sys, time
from pathlib import Path
import reviewed_apps
ROOT=Path(__file__).resolve().parent
STATE=state_dir()
JOBS=STATE/'installs'
NAME=re.compile(r'[a-z0-9][a-z0-9@._+\-]{0,99}\Z')
REPO=re.compile(r'(?:cachyos(?:-[a-z0-9-]+)?|core|extra|multilib)\Z')
ALIASES={'visual studio code':'code','vs code':'code','vscode':'code','vlc media player':'vlc','gimp image editor':'gimp','obs studio':'obs-studio','obs':'obs-studio','libreoffice':'libreoffice-fresh','libre office':'libreoffice-fresh','telegram':'telegram-desktop','telegram desktop':'telegram-desktop','discord':'discord','audacity':'audacity','spotify':'spotify-launcher','spotify desktop':'spotify-launcher','spotify app':'spotify-launcher','google chrome':'google-chrome','chrome':'google-chrome','brave browser':'brave-bin','brave':'brave-bin','qalculate':'qalculate-qt','q calculate':'qalculate-qt','pdf reader':'okular'}

ALIASES.update({name:name for name in ['firefox','gimp','vlc','blender','krita','inkscape','thunderbird','kdenlive','okular','steam','kate','keepassxc']})
ALIASES.update({'whatsapp':'zapzap','whats app':'zapzap','whatsapp app':'zapzap','zapzap':'zapzap','whatsapp web':'whatsapp-web'})
WEB_DESKTOP=Path.home()/'.local/share/applications/jinx-whatsapp-web.desktop'
WEB_URL='https://web.whatsapp.com/'
WEB_CONTENT='[Desktop Entry]\nType=Application\nName=WhatsApp Web\nComment=Official WhatsApp website in your browser\nExec=/usr/bin/xdg-open https://web.whatsapp.com/\nIcon=internet-web-browser\nTerminal=false\nCategories=Network;InstantMessaging;\nKeywords=WhatsApp;Chat;\n'
GUIDE=json.loads((ROOT/'software_knowledge.json').read_text())

def one_edit(left,right):
 if left==right:return True
 if abs(len(left)-len(right))>1:return False
 if len(left)==len(right):
  positions=[i for i,(a,b) in enumerate(zip(left,right)) if a!=b]
  return len(positions)==1 or (len(positions)==2 and positions[1]==positions[0]+1 and left[positions[0]]==right[positions[1]] and left[positions[1]]==right[positions[0]])
 short,long=(left,right) if len(left)<len(right) else (right,left)
 return any(short==long[:i]+long[i+1:] for i in range(len(long)))

def canonical_query(value):
 query=clean_query(value)
 if query in ALIASES:return ALIASES[query]
 if query in GUIDE:return query
 # Preserve an explicitly named real package, even if it resembles an app:
 # spotifyd / spotify-player must never silently become Spotify desktop.
 if NAME.fullmatch(query):
  rows=records(run(['/usr/bin/pacman','-Si','--',query]).stdout)
  if any(row.get('Name')==query and REPO.fullmatch(row.get('Repository','')) for row in rows):return query
 compact=query.replace(' ','')
 matches={package for alias,package in ALIASES.items() if alias.replace(' ','')==compact}
 if len(matches)==1:return next(iter(matches))
 if len(compact)>=5:
  matches={package for alias,package in ALIASES.items() if len(alias.replace(' ',''))>=5 and one_edit(compact,alias.replace(' ',''))}
  if len(matches)==1:return next(iter(matches))
 return query

def run(args,timeout=20):
 return subprocess.run(args,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=timeout,env={**os.environ,'LC_ALL':'C'})
def atomic(path,value):
 path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
 tmp=path.with_name(path.name+'.'+secrets.token_hex(4)+'.tmp')
 with tmp.open('x') as file:os.chmod(tmp,0o600);json.dump(value,file,indent=2)
 tmp.replace(path)
def clean_query(value):
 q=str(value).strip().lower()
 if not q or len(q)>100 or not re.fullmatch(r'[a-z0-9][a-z0-9 .+_@-]*',q):raise ValueError('Use an application or package name, not a command, URL or file path.')
 return q

def requested(text):
 t=str(text).strip().rstrip('.!?').strip()
 t=re.sub(r'^(?:hey\s+)?(?:jinx)[, ]+', '',t,flags=re.I)
 # Parse the whole request, including conversational prefixes, rather than
 # searching for an install keyword inside quoted or informational content.
 t=re.sub(r'^(?:(?:and|also|well|okay|ok|alright)[, ]+)+','',t,flags=re.I)
 match=re.fullmatch(r'(?:(?:please|can you|could you|would you|will you|i want you to|at least|just|also|now)\s+)*(?:install|download and install)\s+(.+?)(?:\s+for me)?(?:[, ]+please)?',t,re.I)
 if not match:
  match=re.fullmatch(r'(?:(?:please|can you|could you)\s+)*(?:do (?:you|i|we) have|is)\s+(.+?)(?: installed)?[, ]+and if not[, ]+(?:(?:can|could|would) you )?(?:please )?install (?:it|that)(?: for me)?',t,re.I)
 if not match:return None
 value=match.group(1)
 if re.search(r'\b(?:don.t|do not|never|without|and|then|but|from|using|instead|if|unless)\b',value,re.I):return None
 try:clean_query(value)
 except ValueError:return None
 return value

def records(output):
 result=[]
 for block in output.strip().split('\n\n'):
  row={};last=''
  for line in block.splitlines():
   m=re.match(r'^([^ :][^:]*?)\s+: (.*)$',line)
   if m:last=m[1].strip();row[last]=m[2].strip()
   elif last and line.startswith(' '):row[last]+=' '+line.strip()
  if row.get('Name'):result.append(row)
 return result

def installed(name):
 if not NAME.fullmatch(name):raise ValueError('Invalid package name')
 result=run(['/usr/bin/pacman','-Q','--',name])
 return result.stdout.strip().split(maxsplit=1)[1] if result.returncode==0 else None

def search(query):
 query=clean_query(query);mapped=canonical_query(query)
 if mapped=='zapzap':
  plan=reviewed_apps.plan(GUIDE[mapped])
  return {'exact':plan,'requested_name':query,'resolved_package':mapped,'knowledge':GUIDE[mapped],'catalog':'Individually reviewed ZapZap maintainer AppImage, pinned release and SHA-256.'}
 if mapped=='whatsapp-web':
  return {'exact':{'package':mapped,'repository':'Official WhatsApp Web','version':'1','description':'Browser shortcut to official WhatsApp Web; not a native Linux client.','installed_version':'1' if web_installed() else None,'url':WEB_URL},'requested_name':query,'resolved_package':mapped,'knowledge':GUIDE[mapped],'catalog':'Reviewed browser shortcut; no repository package or third-party wrapper.'}
 if NAME.fullmatch(mapped):
  r=run(['/usr/bin/pacman','-Si','--',mapped]);items=records(r.stdout)
  items=[p for p in items if p['Name']==mapped and REPO.fullmatch(p.get('Repository',''))]
  if items:return {'exact':public(items[0]),'matches':[public(items[0])],'requested_name':query,'resolved_package':mapped,'knowledge':GUIDE.get(mapped),'catalog':'Configured CachyOS/Arch repositories; cached database, not AUR.'}
 r=run(['/usr/bin/pacman','-Ss','--',re.escape(query)])
 matches=[];seen=set()
 for line in r.stdout.splitlines():
  m=re.match(r'([^/ ]+)/([^ ]+) ([^ ]+)',line)
  if m and REPO.fullmatch(m[1]) and m[2] not in seen:
   seen.add(m[2]);matches.append({'repository':m[1],'package':m[2],'version':m[3]})
 # Give the model useful descriptions instead of an unexplained list of names.
 selected=matches[:8]
 if selected:
  details=records(run(['/usr/bin/pacman','-Si','--',*[p['repository']+'/'+p['package'] for p in selected]]).stdout)
  descriptions={(p['Repository'],p['Name']):p.get('Description','') for p in details}
  for item in selected:item['description']=descriptions.get((item['repository'],item['package']),'')
 return {'matches':selected,'catalog':'Configured CachyOS/Arch repositories; cached database, not AUR.','detail':'Use an exact package name from the results. If unavailable, a separate source/AUR review is needed.'}

def public(row):
 return {'repository':row['Repository'],'package':row['Name'],'version':row['Version'],'description':row.get('Description',''),'installed_version':installed(row['Name']),'url':row.get('URL','')}

def fingerprint():
 digest=hashlib.sha256()
 for path in [Path('/etc/pacman.conf'),*sorted(Path('/var/lib/pacman/sync').glob('*.db'))]:
  st=path.stat();digest.update(f'{path}:{st.st_size}:{st.st_mtime_ns}'.encode())
 return digest.hexdigest()

def guidance_for(text):
 words=re.findall(r"[a-z0-9@._+-]+",str(text).lower())
 for package,entry in GUIDE.items():
  aliases=[a for a,p in ALIASES.items() if p==package]+[package]
  if any(alias in words for alias in aliases) or any(len(word)>=5 and one_edit(word,entry['name'].lower()) for word in words):
   result=search(package)
   return {'reviewed_app':entry,'current_repository_result':result,'instruction':'These source-backed facts and current package metadata supersede an earlier unverified guess. Explain the normal desktop option. A knowledge question is not installation authorisation.'}
 return None

def build_plan(query):
 result=search(query)
 if not result.get('exact'):return {'status':'choose_package',**result}
 app=result['exact'];name=app['package']
 if name=='zapzap':return app
 if name=='whatsapp-web':
  if WEB_DESKTOP.is_symlink() or (WEB_DESKTOP.exists() and not web_installed()):raise ValueError('An existing WhatsApp shortcut differs from this preview. It has been preserved; review it before replacing it.')
  return {'status':'already_installed' if web_installed() else 'ready',**app,'install_kind':'web_shortcut','url':WEB_URL,'desktop_file':WEB_DESKTOP.name,'packages':[],'download_mib':0,'catalog_fingerprint':hashlib.sha256(WEB_CONTENT.encode()).hexdigest(),'created_at':time.time(),'knowledge':GUIDE[name],'method':'Create a user application-menu shortcut to official WhatsApp Web in the default browser. No administrator authentication needed.'}
 if app['installed_version']:return {'status':'already_installed',**app}
 # These requests need a system-maintenance review instead of an app install.
 if re.match(r'^(?:linux(?:$|-)|linux-firmware|amd-ucode$|intel-ucode$|nvidia|mesa$|lib32-mesa$|vulkan-|lib32-vulkan-|grub$|limine$|systemd$)',name):raise ValueError('Kernel, firmware, graphics drivers and boot components need a separate system-maintenance review.')
 if Path('/var/lib/pacman/db.lck').exists():raise ValueError('Another package operation is running. Let it finish, then ask again.')
 updates=run(['/usr/bin/pacman','-Qu'])
 if updates.returncode not in (0,1):raise ValueError('Could not check the local package database.')
 if updates.stdout.strip():raise ValueError('The current repository databases show pending system updates. Apply the normal full update in Cachy-Update first, then ask me to install this app.')
 target=app['repository']+'/'+name
 r=run(['/usr/bin/pacman','-Sp','--needed','--noconfirm','--print-format','%r/%n|%v|%s|%H|%R','--',target])
 if r.returncode:raise ValueError('Package dependency planning failed. Check the package manager before installing.')
 packages=[]
 for line in r.stdout.splitlines():
  fields=line.split('|')
  if len(fields)!=5:raise ValueError('Unexpected dependency plan; nothing installed.')
  identifier,version,size,conflicts,replaces=fields
  repo,pkg=identifier.split('/',1)
  if not REPO.fullmatch(repo) or not NAME.fullmatch(pkg):raise ValueError('Dependency came from an unreviewed repository.')
  # A conflict/replacement deserves a human package-manager transaction review.
  for conflict in (conflicts+' '+replaces).split():
   check=run(['/usr/bin/pacman','-T','--',conflict])
   if check.returncode==0:raise ValueError('This transaction conflicts with or replaces an installed package. Review it in the package manager; Jinx will not remove another package automatically.')
   if check.returncode!=127:raise ValueError('Could not check package conflicts.')
  if installed(pkg):raise ValueError('Installing this app would change an existing package. Review the transaction in the package manager first.')
  packages.append({'target':identifier,'version':version,'download_bytes':int(size)})
 if not packages:raise ValueError('The package transaction is empty; check the installed state again.')
 if len(packages)>100:raise ValueError('This needs more than100 packages. Review the larger transaction in the package manager.')
 return {'status':'ready','package':name,'repository':app['repository'],'version':app['version'],'description':app['description'],'packages':packages,'download_mib':round(sum(x['download_bytes'] for x in packages)/1048576,2),'catalog_fingerprint':fingerprint(),'created_at':time.time(),'requested_name':result.get('requested_name',query),'knowledge':GUIDE.get(name),'method':'Install from existing configured repositories with dependencies; normal KDE administrator authentication. No database refresh, full upgrade, removal or AUR build.'}

def review_text(plan):
 if plan.get('install_kind')=='reviewed_appimage':
  return '\n'.join(['WhatsApp (ZapZap) '+plan['version'],plan['knowledge']['explanation'],'',f"Download: about {plan['download_mib']} MiB",'Source: '+plan['url'],'SHA-256: '+plan['sha256'],'','Creates a standalone app in your application menu.','No administrator password required.','Jinx can connect to the local app controls for reviewed voice messages.',plan['knowledge']['first_launch']])
 if plan.get('install_kind')=='web_shortcut':
  return '\n'.join(['WhatsApp Web — browser shortcut',plan['knowledge']['explanation'],'','Website: '+WEB_URL,'Creates: '+str(WEB_DESKTOP),'Opens in your existing default browser. No native client or unofficial wrapper is installed.','No administrator password required.','',plan['knowledge']['first_launch'],'','Sources checked '+plan['knowledge']['reviewed_at']+':',*[source['url'] for source in plan['knowledge']['sources']]])
 lines=[plan.get('knowledge',{}).get('name',plan['package']) if plan.get('knowledge') else plan['package'],plan['package']+' '+plan['version'],plan['description'],'Source: '+plan['repository'],f"Download: about {plan['download_mib']} MiB",'','Packages to install:']
 lines.extend('• '+p['target']+' '+p['version'] for p in plan['packages'])
 if plan.get('knowledge'):
  lines.extend(['',plan['knowledge']['explanation'],plan['knowledge']['first_launch'],'Sources checked '+plan['knowledge']['reviewed_at']+':'])
  lines.extend(source['url'] for source in plan['knowledge']['sources'])
 lines.extend(['','Uses normal administrator authentication. No password is given to Jinx.','Existing apps will not be removed; system updates are handled separately.'])
 return '\n'.join(lines)

def validate_plan(plan):
 if not isinstance(plan,dict):raise ValueError('Invalid installation plan')
 if time.time()-float(plan.get('created_at',0))>3600:raise ValueError('This installation preview has expired. Ask for the app again.')
 fresh=build_plan(plan.get('package',''))
 if fresh.get('install_kind')=='reviewed_appimage' or plan.get('install_kind')=='reviewed_appimage':
  for field in ('install_kind','package','url','sha256','version','catalog_fingerprint'):
   if fresh.get(field)!=plan.get(field):raise ValueError('The reviewed application changed. Prepare a new preview.')
 if fresh.get('install_kind')=='web_shortcut' or plan.get('install_kind')=='web_shortcut':
  for field in ('install_kind','package','url','desktop_file','catalog_fingerprint'):
   if fresh.get(field)!=plan.get(field):raise ValueError('The shortcut plan changed. Ask for a new preview.')
 if fresh['status']=='already_installed':return fresh
 if fresh['status']!='ready':raise ValueError('Package is no longer available.')
 for field in ('package','repository','version','packages','catalog_fingerprint'):
  if fresh[field]!=plan.get(field):raise ValueError('The package plan changed. Ask Jinx to prepare a new installation preview.')
 return fresh

def register_apps(package):
 if package=='zapzap':return ['whatsapp'] if reviewed_apps.verified() else []
 if package=='whatsapp-web':return ['whatsapp'] if web_installed() else []
 r=run(['/usr/bin/pacman','-Qlq','--',package]);apps={}
 for name in r.stdout.splitlines():
  p=Path(name)
  if p.parent!=Path('/usr/share/applications') or p.suffix!='.desktop' or not p.is_file():continue
  c=configparser.ConfigParser(interpolation=None,strict=False)
  try:
   c.read(p)
   if c.get('Desktop Entry','Type',fallback='')!='Application' or c.getboolean('Desktop Entry','Hidden',fallback=False) or c.getboolean('Desktop Entry','NoDisplay',fallback=False):continue
   label=c.get('Desktop Entry','Name',fallback=package)
  except (configparser.Error,ValueError):continue
  apps[p.stem]={'name':label,'desktop':p.name,'aliases':list(dict.fromkeys([package,label.lower(),p.stem.lower(),*[alias for alias,target in ALIASES.items() if target==package]]))}
 registry=STATE/'installed-apps.json'
 try:old=json.loads(registry.read_text())
 except (OSError,ValueError):old={}
 old.update(apps);atomic(registry,old)
 return list(apps)

def web_installed():
 try:return not WEB_DESKTOP.is_symlink() and WEB_DESKTOP.read_text()==WEB_CONTENT
 except OSError:return False

def installed_message(plan):
 if plan.get('install_kind')=='reviewed_appimage':return 'WhatsApp (ZapZap) is already installed and verified. Say “Open WhatsApp” to use the standalone app.'
 if plan.get('install_kind')=='web_shortcut':return 'The WhatsApp Web browser shortcut is already installed and verified. Say “Open WhatsApp” to use it.'
 return plan['package']+' is already installed ('+plan['installed_version']+').'

def audit(kind,values):
 from system_tools import audit as record
 record(kind,values)

def jobs():
 results=[]
 for p in sorted(JOBS.glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:8]:
  try:
   row=json.loads(p.read_text())
   if row.get('state') in ('starting','authenticating','installing'):
    if time.time()-row.get('updated_at',0)>15:
     try:alive=row['id'].encode() in Path('/proc',str(row.get('pid',0)),'cmdline').read_bytes()
     except OSError:alive=False
     if not alive:
      row.update(state='failed',message='The installer exited before confirming success. Check the package manager.',updated_at=time.time());atomic(p,row)
    if row.get('state')=='authenticating':
     try:
      with p.with_suffix('.log').open() as log:started='resolving dependencies' in log.read(400)
      if started:row.update(state='installing',message='Installing packages. The result will be verified when pacman finishes.')
     except OSError:pass
   results.append({k:row.get(k) for k in ['id','proposal_id','package','state','message','version','updated_at']})
  except (OSError,ValueError):pass
 return results

def request_review(identifier):
 if not re.fullmatch(r'[a-f0-9]{16}',identifier):raise ValueError('Invalid review ID')
 ready=runtime_dir()/'jinx-install-review'/(identifier+'.ready')
 def visible():
  try:
   pid=json.loads(ready.read_text())['pid']
   return identifier.encode() in Path('/proc',str(int(pid)),'cmdline').read_bytes()
  except (OSError,ValueError,KeyError,TypeError):return False
 if visible():return True
 ready.unlink(missing_ok=True)
 result=run(['/usr/bin/systemd-run','--user','--collect','--quiet','--unit=jinx-review-'+identifier+'-'+secrets.token_hex(3),'--property=Type=exec',str(ROOT/'installer/build/jinx-installer'),identifier])
 if result.returncode:raise ValueError('The installation window could not start. Open Jinx → Software installs to review it.')
 for _ in range(60):
  if visible():return True
  time.sleep(.05)
 raise ValueError('The installation window did not appear. Open Jinx → Software installs to review it.')

def launch(plan,proposal_id=None):
 fresh=validate_plan(plan)
 if fresh['status']=='already_installed':register_apps(fresh['package']);return installed_message(fresh)
 if any(j['state'] in ('starting','authenticating','installing') for j in jobs()):raise ValueError('An installation is already running. Check its status before starting another.')
 identifier=secrets.token_hex(12)
 job={'id':identifier,'proposal_id':proposal_id,'package':fresh['package'],'state':'starting','message':'Starting the installer…','updated_at':time.time(),'plan':fresh}
 atomic(JOBS/(identifier+'.json'),job)
 audit('software_job',{'id':identifier,'proposal_id':proposal_id,'package':fresh['package'],'state':'starting'})
 unit='jinx-install-'+identifier
 r=run(['/usr/bin/systemd-run','--user','--collect','--quiet','--unit='+unit,'--property=Type=exec','--property=TimeoutStopSec=300',str(ROOT/'.venv/bin/python'),str(ROOT/'software_installer.py'),'--run-job',identifier])
 if r.returncode:
  job.update(state='failed',message='Could not launch the installer service.',updated_at=time.time());atomic(JOBS/(identifier+'.json'),job);raise ValueError(job['message'])
 if fresh.get('install_kind') in ('web_shortcut','reviewed_appimage'):return 'Installing '+fresh['package']+' for your user account. No administrator password needed. Check Software installs for the verified result.'
 return 'Installation requested for '+fresh['package']+'. Approve the normal KDE authentication prompt if shown. I will report the verified result in Software installs.'

def execute_job(identifier,privileged=subprocess.run):
 if not re.fullmatch(r'[a-f0-9]{24}',identifier):raise ValueError('Invalid installation job')
 path=JOBS/(identifier+'.json');job=json.loads(path.read_text())
 def update(state,message,**values):
  job.update(state=state,message=message,updated_at=time.time(),**values);atomic(path,job)
  if state in ('installed','cancelled','failed'):
   audit('software_result',{'id':identifier,'package':job['package'],'state':state,**values})
   try:run(['/usr/bin/notify-send','--app-name=Jinx','Jinx · Software install',message],5)
   except (OSError,subprocess.TimeoutExpired):pass
 lock=JOBS/'install.lock'
 with lock.open('a') as handle:
  try:
   fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
   if job['state']!='starting':raise ValueError('Installation job was already handled.')
   plan=validate_plan(job['plan'])
   if plan['status']=='already_installed':register_apps(plan['package']);update('installed','Already installed.',version=plan['installed_version']);return
   if plan.get('install_kind')=='reviewed_appimage':
    update('installing','Downloading and verifying the reviewed ZapZap app…',pid=os.getpid());reviewed_apps.install()
    run(['/usr/bin/update-desktop-database',str(reviewed_apps.DESKTOP.parent)])
    update('installed','WhatsApp (ZapZap) installed and checksum verified. Say “Open WhatsApp” to link your phone in the app.',version=plan['version']);return
   if plan.get('install_kind')=='web_shortcut':
    WEB_DESKTOP.parent.mkdir(parents=True,exist_ok=True)
    # Exclusive creation preserves existing files, including dangling symlinks.
    with WEB_DESKTOP.open('x') as output:output.write(WEB_CONTENT)
    if not web_installed():raise ValueError('The WhatsApp Web shortcut could not be verified.')
    run(['/usr/bin/update-desktop-database',str(WEB_DESKTOP.parent)])
    update('installed','WhatsApp Web browser shortcut created and verified. Say “Open WhatsApp”; link your phone in the browser yourself.',version='1');return
   update('authenticating','Approve KDE authentication to install '+plan['package']+'. Download/install follows automatically after approval.',pid=os.getpid())
   # Only the system pacman binary is elevated. No user script, shell, flags,
   # URL, credentials or model-authored command is passed to root.
   argv=['/usr/bin/pkexec','/usr/bin/pacman','-S','--needed','--noconfirm','--color','never','--',plan['repository']+'/'+plan['package']+'='+plan['version']]
   log=JOBS/(identifier+'.log')
   with log.open('w') as output:
    os.chmod(log,0o600)
    result=privileged(argv,stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,env={**os.environ,'LC_ALL':'C'})
   version=installed(plan['package'])
   if result.returncode==0 and version==plan['version']:
    register_apps(plan['package']);update('installed',plan['package']+' installed and verified.'+(' Open Spotify to download its desktop client on first launch.' if plan['package']=='spotify-launcher' else ''),version=version)
   elif result.returncode in (126,127):update('cancelled','Authentication was cancelled or unavailable. Nothing was reported as installed.')
   else:update('failed','Installation did not complete successfully. Check its private log or the package manager; a stale mirror/database may need a normal full update.')
  except Exception as error:update('failed',str(error)[:350])

if __name__=='__main__':
 os.umask(0o077)
 if len(sys.argv)!=3 or sys.argv[1]!='--run-job':raise SystemExit('Only --run-job <reviewed job ID> is supported.')
 execute_job(sys.argv[2])
