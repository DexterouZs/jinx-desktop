"""Deterministic app and game launching — tier 0, no model involved.

Launching already worked through the `jinx_apps` agent tool, but that meant
every "open Steam" waited on the 27B: measured 3.5s at best and 9s cold, for a
request whose whole content is one verb and one name. This module recognises
those requests directly and calls the same reviewed launcher.

Nothing new is executed. Resolution and launching both go through
`system_tools.app_catalog()` and `system_tools.desktop_apps()`, so the existing
boundaries hold: only discovered `.desktop` entries, launched under
`systemd-run --user` via `gtk-launch`, never an arbitrary path or shell string.
Steam titles that have no `.desktop` entry are launched by app id through
Steam's own URL handler, which is equally not a shell.
"""
import configparser,re,secrets
from pathlib import Path

import system_tools
import request_intents
import steam_shortcuts

HOME=Path.home()
STEAM_LIBRARIES=[HOME/'.local/share/Steam/steamapps',HOME/'.steam/steam/steamapps']
LIBRARY_FOLDERS=[HOME/'.local/share/Steam/steamapps/libraryfolders.vdf']

# Verbs that mean "start this thing now". "play" is included because it is how
# games are actually asked for, but it is checked after music routing so
# "play some music" never reaches here.
VERBS=('open','launch','start','run','play','fire up','boot','öffne','starte','spiele')

# Words that mean the request is about something other than starting an app.
NOT_A_LAUNCH=re.compile(
 r'\b(music|song|songs|playlist|spotify|album|track|radio|podcast|'
 r'timer|alarm|reminder|volume|brightness|folder|screen|page|clipboard)\b')


def steam_games():
 """Installed Steam titles, from the appmanifest files Steam maintains."""
 roots=list(STEAM_LIBRARIES)
 for vdf in LIBRARY_FOLDERS:
  try:
   for path in re.findall(r'"path"\s+"([^"]+)"',vdf.read_text()):
    roots.append(Path(path)/'steamapps')
  except OSError:continue
 found={}
 for root in roots:
  try:manifests=sorted(root.glob('appmanifest_*.acf'))
  except OSError:continue
  for manifest in manifests:
   try:text=manifest.read_text(errors='replace')
   except OSError:continue
   appid=re.search(r'"appid"\s+"(\d+)"',text)
   name=re.search(r'"name"\s+"([^"]+)"',text)
   if not appid or not name:continue
   # Runtimes and tools are not things David asks to play.
   if re.match(r'(?i)(proton|steam linux runtime|steamworks)',name.group(1)):continue
   directory=re.search(r'"installdir"\s+"([^"]+)"',text)
   found[appid.group(1)]={'appid':appid.group(1),'name':name.group(1).strip(),'aliases':[directory.group(1)] if directory else []}
 found.update(steam_shortcuts.games())
 return found


def catalog():
 """Everything launchable: reviewed apps, discovered launchers, Steam titles."""
 entries={}
 for key,app in system_tools.app_catalog().items():
  entries[key]={'key':key,'name':app['name'],'kind':'desktop','aliases':list(app.get('aliases') or [])}
 for appid,game in steam_games().items():
  key='steam_'+appid
  existing=next((e for e in entries.values() if normalise(e['name'])==normalise(game['name'])),None)
  if existing:
   existing['aliases'].extend(game.get('aliases',[]));existing['game']=True
   continue
  entries[key]={'key':key,'name':game['name'],'kind':'steam','appid':appid,'aliases':game.get('aliases',[]),'game':True}
 return entries


def normalise(value):
 return re.sub(r'[^a-z0-9 ]','',str(value).lower()).strip()


def resolve(name,entries):
 """Exact, then whole-word, then subset. Ambiguity is reported, not guessed."""
 want=' '.join(normalise(name).split())
 if not want:return {'error':'Which app?'}
 def labels(entry):
  return [normalise(x) for x in [entry['name'],entry['key'],*entry['aliases']] if x]
 def pick(matches):
  if not matches:return None
  if len(matches)==1:return {'entry':matches[0]}
  names=sorted({m['name'] for m in matches})
  if len(names)==1:return {'entry':matches[0]}
  return {'error':'Several match: '+', '.join(names[:4])}
 pool=list(entries.values())
 exact=[e for e in pool if want in labels(e)]
 if exact:return pick(exact)
 words=want.split()
 whole=[e for e in pool if any(want in label.split(' ') for label in labels(e))]
 if whole:return pick(whole)
 subset=[e for e in pool if any(all(w in label.split(' ') for w in words) for label in labels(e))]
 if subset:return pick(subset)
 prefix=[e for e in pool if any(label.startswith(want) for label in labels(e))]
 return pick(prefix) or {'error':f'Nothing installed called {name}'}


def parse(text):
 """Return the requested app name, or None when this is not a launch request."""
 t=request_intents.command_text(text)
 if not t:return None
 lowered=t.lower()
 # German modal questions place the infinitive after the title.
 german=re.fullmatch(r'(.+?)\s+(öffnen|starten|spielen)',t,re.I)
 if german:
  verb={'öffnen':'öffne','starten':'starte','spielen':'spiele'}[german[2].lower()]
  t=verb+' '+german[1];lowered=t.lower()
 if re.search(r"\b(?:don't|do not|not now|nicht|and then|and (?:open|launch|start|search|play|send))\b",lowered):return None
 if re.fullmatch(r'(?:open|launch|start) spott?ify',lowered):return 'spotify'
 if NOT_A_LAUNCH.search(lowered):return None
 for verb in VERBS:
  if not lowered.startswith(verb+' '):continue
  rest=t[len(verb):].strip()
  for article in ('the ','my ','up ','a ','das ','mein ','den ','die '):
   if rest.lower().startswith(article):rest=rest[len(article):]
  rest=re.sub(r'(?i)^(?:game|spiel)\b[\s,:]*','',rest).strip()
  rest=re.sub(r'(?i)(?:\s+(?:for me|please|now|on steam|in steam|bitte))+$','',rest).strip(' ,\"')
  # "open downloads" is a folder request; desktop_tools owns those.
  return rest or None
 return None


def launch(entry):
 if entry['kind']=='steam':
  result=system_tools.run(['/usr/bin/systemd-run','--user','--collect','--quiet',
                           '--property=ExitType=cgroup','--unit=jinx-steam-'+entry['appid']+'-'+secrets.token_hex(4),
                           '/usr/bin/steam','steam://rungameid/'+entry['appid']])
  system_tools.audit('open_app',{'app':entry['key'],'ok':result['ok']})
  if not result['ok']:return result
  return {'status':'launch_requested','app':entry['name']}
 return system_tools.desktop_apps({'action':'open','app':entry['key']})

def tools(args):
 entries=catalog()
 if args.get('action','list')=='list':return {'apps':entries}
 if args.get('action')!='open':raise ValueError('Use list or open')
 found=resolve(str(args.get('app','')),entries)
 if 'error' in found:return found
 return launch(found['entry'])


def requested(text,entries=None):
 """Tier-0 entry point. Returns a reply dict, or None to fall through."""
 name=parse(text)
 if not name:return None
 entries=catalog() if entries is None else entries
 found=resolve(name,entries)
 if 'error' in found:
  # Not a known app: let the normal routing answer instead of refusing.
  if found['error'].startswith('Nothing installed'):return None
  return {'reply':found['error'],'_tools':['jinx_apps']}
 entry=found['entry']
 result=launch(entry)
 if result.get('error'):return {'reply':str(result['error'])[:200],'_tools':['jinx_apps']}
 if not result.get('status'):return {'reply':f"Could not start {entry['name']}",'_tools':['jinx_apps']}
 # A launcher accepting the request is not proof the window opened.
 return {'reply':f"Starting {entry['name']}",'_tools':['jinx_apps']}
