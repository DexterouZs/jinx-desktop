"""Reachability checks for David's own network services — read-only.

Answers "is the NAS up?" without credentials and without the model. This
deliberately does not log in to anything: it opens a TCP connection, and for
HTTP services reads a public status endpoint where one exists. It cannot
change, restart or configure a service, and it only ever touches the fixed
hosts listed here — there is no "check this address" escape hatch, so a shared
document or web page cannot turn it into a port scanner.

Services are configured in private local state; no household addresses ship with the app.
"""
import json,socket,urllib.error,urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CONFIG=Path.home()/'.local/state/jinx/homelab.json'

DEFAULT_SERVICES=[]  # Configure private services in local state, never in source.


def services():
 """Configured services, overridable without editing code."""
 try:
  rows=json.loads(CONFIG.read_text())
  return rows if isinstance(rows,list) and rows else DEFAULT_SERVICES
 except (OSError,ValueError):
  return DEFAULT_SERVICES


def check(service,timeout=1.5):
 """One service: reachable, plus a version where it is offered publicly."""
 result={'key':service['key'],'name':service['name'],'up':False,'detail':''}
 try:
  with socket.create_connection((service['host'],service['port']),timeout=timeout):
   result['up']=True
 except (OSError,socket.timeout):
  result['detail']='not responding'
  return result
 probe=service.get('probe')
 if not probe:return result
 url=f"http://{service['host']}:{service['port']}{probe}"
 try:
  with urllib.request.urlopen(url,timeout=timeout) as response:
   payload=json.loads(response.read().decode() or '{}')
  version=payload.get('Version') or payload.get('version')
  name=payload.get('ServerName')
  result['detail']=' '.join(x for x in [name,('v'+version) if version else ''] if x).strip()
 except (urllib.error.URLError,OSError,ValueError,socket.timeout):
  # Port open but the API did not answer; still up as far as TCP is concerned.
  result['detail']='responding'
 return result


def check_all(timeout=1.5):
 rows=services()
 with ThreadPoolExecutor(max_workers=min(8,len(rows) or 1)) as pool:
  return list(pool.map(lambda s:check(s,timeout),rows))


def find(name):
 want=' '.join(str(name or '').lower().split())
 if not want:return None
 for service in services():
  labels=[service['key'].replace('_',' '),service['name'].lower(),*service.get('aliases',[])]
  if any(want==label or want in label.split(' ') for label in labels):return service
 for service in services():
  labels=[service['name'].lower(),*service.get('aliases',[])]
  if any(want in label for label in labels):return service
 return None


def summarise(rows):
 up=[r for r in rows if r['up']]
 down=[r for r in rows if not r['up']]
 if not down:return f"All {len(up)} services are up"
 return f"{len(down)} down: "+', '.join(r['name'] for r in down)+f"; {len(up)} up"


def describe(row):
 if not row['up']:return f"{row['name']} is not responding"
 return f"{row['name']} is up" + (f" — {row['detail']}" if row['detail'] and row['detail']!='responding' else '')


def parse(text):
 """Recognise a homelab status question; None means not one."""
 t=' '.join(str(text or '').lower().split()).strip(' .!?')
 if not t:return None
 for lead in ('hey jinx','ok jinx','please','jinx','could you','can you'):
  if t.startswith(lead) and (len(t)==len(lead) or not t[len(lead)].isalnum()):
   t=t[len(lead):].lstrip(' ,.:');break
 whole=('is everything up','are all my services up','is my homelab up','homelab status',
        'check my services','are my services up','is anything down','what is down',
        "what's down",'server status')
 if t in whole or t.rstrip('?') in whole:return {'action':'all'}
 for pattern in ('is the ','is ','are the ','are '):
  if not t.startswith(pattern):continue
  rest=t[len(pattern):]
  for suffix in (' up',' online',' running',' responding',' down',' reachable'):
   if rest.endswith(suffix):
    return {'action':'one','name':rest[:-len(suffix)].strip(),'negated':suffix==' down'}
 return None


def requested(text):
 """Tier-0 entry point. Returns a reply dict, or None to fall through."""
 intent=parse(text)
 if not intent:return None
 if intent['action']=='all':
  return {'reply':summarise(check_all()),'_tools':['jinx_homelab']}
 service=find(intent['name'])
 if not service:return None
 row=check(service)
 if intent.get('negated'):
  return {'reply':(f"{row['name']} is not responding" if not row['up'] else f"No, {row['name']} is up"),
          '_tools':['jinx_homelab']}
 return {'reply':describe(row),'_tools':['jinx_homelab']}


def tool(args):
 """Guarded surface for the agent."""
 action=args.get('action','all')
 if action=='all':
  rows=check_all()
  return {'services':[{'name':r['name'],'up':r['up'],'detail':r['detail']} for r in rows],
          'summary':summarise(rows)}
 if action=='one':
  service=find(args.get('name',''))
  if not service:return {'error':'Unknown service. Known: '+', '.join(s['name'] for s in services())}
  return {'service':describe(check(service))}
 return {'error':'Use all or one'}
