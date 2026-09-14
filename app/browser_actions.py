"""Requested browser navigation, separate from reading pages and launching apps."""
import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit, urlencode
import request_intents

SITES = {
 'nexus mods': ('Nexus Mods', 'https://www.nexusmods.com/'),
 'youtube': ('YouTube', 'https://www.youtube.com/'),
 'wikipedia': ('Wikipedia', 'https://www.wikipedia.org/'),
 'github': ('GitHub', 'https://github.com/'),
}
ALIASES = {'nexus':'nexus mods', 'nexus mod':'nexus mods', 'nexusmods':'nexus mods',
 'nexusmod':'nexus mods', 'nexusmort':'nexus mods', 'nexus mort':'nexus mods',
 'nexus mode':'nexus mods', 'nexus mmod':'nexus mods', 'you tube':'youtube'}

def clean(value):
 value=re.sub(r'^(?:(?:for me|me|the|my|a|an)\s+)+','',value.strip(),flags=re.I)
 value=re.sub(r'(?:\s+(?:for me|please|now|bitte))+$','',value,flags=re.I)
 value=re.sub(r'^(?:website|web site|web page|site|webpage|page)(?:\s+for me)?[\s,:]+(?:the\s+)?','',value,flags=re.I)
 value=re.sub(r'^from\s+','',value,flags=re.I)
 value=re.sub(r'\s+(?:website|web site|web page|site|webpage|homepage|page)(?:\s+from\s+nexus)?$','',value,flags=re.I)
 return value.strip(' ,')

def url(value):
 value=str(value).strip()
 if len(value)>4096 or any(ord(c)<33 for c in value):raise ValueError('Use a normal website address without spaces or control characters.')
 if '://' not in value:value='https://'+value
 p=urlsplit(value)
 if p.scheme not in ('https','http') or not p.hostname or p.username or p.password:
  raise ValueError('Only HTTP or HTTPS website addresses without embedded logins can be opened.')
 try:p.port
 except ValueError:raise ValueError('Invalid website port.')
 if not re.fullmatch(r'[\w.\-:]+',p.hostname):raise ValueError('Invalid website hostname.')
 return value

def destination(target):
 target=clean(target);key=ALIASES.get(target.casefold(),target.casefold())
 if key in SITES:
  name,address=SITES[key];return {'url':address,'label':name,'kind':'site'}
 if re.match(r'^https?://',target,re.I) or re.fullmatch(r'(?:[\w-]+\.)+[a-zA-Z]{2,}(?::\d+)?(?:/\S*)?',target):
  address=url(target);return {'url':address,'label':urlsplit(address).hostname,'kind':'site'}
 if '://' in target or re.match(r'^(?:javascript|data|file|mailto):',target,re.I):raise ValueError('That is not a website address.')
 if not target:return {'reply':'Which website would you like me to open?'}
 return {'url':'https://www.google.com/search?'+urlencode({'q':target+' official website'}),'label':target,'kind':'site_search'}

def parse(text):
 t=request_intents.command_text(text)
 if not t or re.search(r"\b(?:don't|do not|never|nicht|and then|and (?:open|send|install|play)|und (?:öffne|sende|starte))\b",t,re.I):return None
 # Explicit video searches open real YouTube results, never invented video IDs.
 m=re.fullmatch(r'(?:show|find|search(?: for)?|look for|play|watch|zeig(?:e)?|suche|spiele)\s+(.+?)\s+(?:on|in|auf)\s+(?:you\s?tube)(?:\s+for me)?',t,re.I)
 n=re.fullmatch(r'(?:show|find|search|play|watch)\s+(?:me\s+)?(?:some\s+)?you\s?tube\s+videos?(?:\s+(?:about|of|for))?\s*(.*)',t,re.I)
 o=re.fullmatch(r'(?:search|look on)\s+you\s?tube\s+for\s+(.+)',t,re.I)
 v=re.fullmatch(r'(?:show|find|play|watch)\s+(?:me\s+)?(?:(?:a|some)\s+)?videos?\s+(?:about|of|on)\s+(.+)',t,re.I)
 if m or n or o or v:
  query=clean((m or n or o or v)[1]);query=re.sub(r'^(?:some\s+)?videos?\s+(?:about|of|for)\s+','',query,flags=re.I)
  return {'url':'https://www.youtube.com/results?'+urlencode({'search_query':query}),'label':query,'kind':'video_search'} if query else {'reply':'What would you like to watch on YouTube?'}
 m=re.fullmatch(r'(?:open|visit|go to|take me to|bring up|show(?: me)?|öffne|besuche)\s+(.+)',t,re.I)
 if not m:return None
 target=clean(m[1]);key=ALIASES.get(target.casefold(),target.casefold())
 explicit=bool(re.search(r'\b(?:website|web site|web page|site|webpage|homepage|page)\b',m[1],re.I))
 if explicit or key in SITES or re.match(r'^https?://',target,re.I) or re.fullmatch(r'(?:[\w-]+\.)+[a-zA-Z]{2,}(?:/\S*)?',target):return destination(target)
 return None

def raise_browser():
 """KDE may accept a tab but leave Firefox hidden behind the current app."""
 tag='jinx-browser-raise'
 try:
  default=subprocess.run(['xdg-settings','get','default-web-browser'],capture_output=True,text=True,timeout=2).stdout.strip()
  if default!='firefox.desktop':return
  bus=['qdbus6','org.kde.KWin']
  result=subprocess.run(bus+['/Scripting','org.kde.kwin.Scripting.loadScript',str(Path(__file__).with_name('browser-raise.js')),tag],capture_output=True,text=True,timeout=2)
  index=result.stdout.strip()
  if not index.isdigit():return
  try:subprocess.run(bus+['/Scripting/Script'+index,'org.kde.kwin.Script.run'],capture_output=True,timeout=2)
  finally:subprocess.run(bus+['/Scripting','org.kde.kwin.Scripting.unloadScript',tag],capture_output=True,timeout=2)
 except (OSError,subprocess.TimeoutExpired):pass

def open_plan(plan):
 if 'reply' in plan:return plan
 address=url(plan['url'])
 try:
  result=subprocess.run(['/usr/bin/xdg-open',address],capture_output=True,text=True,timeout=8)
 except (OSError,subprocess.TimeoutExpired):return {'reply':'The browser did not accept the request in time. Please try again.','status':'failed'}
 if result.returncode:return {'reply':'The browser could not open that page.','status':'failed'}
 raise_browser()
 if plan['kind']=='video_search':reply='Opening YouTube results for '+plan['label']+'.'
 elif plan['kind']=='site_search':reply='Opening browser search results for '+plan['label']+'; I have not guessed its address.'
 else:reply='Opening '+plan['label']+'.'
 return {'reply':reply,'status':'launch_requested','url':address}

def requested(text,enabled=True):
 try:plan=parse(text)
 except ValueError as e:return {'reply':str(e),'_tools':[]}
 if plan is None:return None
 if not enabled:return {'reply':'Web access is switched off in my options.','_tools':[]}
 return {**open_plan(plan),'_tools':['jinx_browser']}
