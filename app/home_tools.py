"""Bounded Home Assistant control: read state and act on reviewed domains only.

Follows the same shape as desktop_tools/music_tools — a deterministic
`requested()` intent path that answers common phrasings without involving the
language model at all, plus a guarded tool surface for the agent.

Boundaries, deliberately narrow:
  * The token is read from a private file into memory and never logged,
    returned, or placed in an error message.
  * Only CONTROL domains can be acted on. Covers additionally require a
    curtain/blind/shade device class; locks, doors and alarms stay read-only.
    There is no
    "call any service" escape hatch.
  * Entity resolution is exact-or-unambiguous. A name matching several
    entities asks rather than guessing which of David's lights to change.
"""
import json,re,threading,time,urllib.error,urllib.request
from pathlib import Path

STATE=Path.home()/'.local/state/jinx'
CONFIG=STATE/'home-assistant.json'
TOKENFILE=STATE/'home-assistant.token'

# Actuating these is reversible, visible and low-consequence.
CONTROL={'light','switch','fan','humidifier','scene','input_boolean','media_player','cover'}
# Readable but never actuated: physical-security and safety-relevant domains.
READ_ONLY={'lock','alarm_control_panel','cover','climate','binary_sensor','sensor','person','device_tracker','weather','sun'}
READABLE=CONTROL|READ_ONLY

ON_WORDS={'on'}
OFF_WORDS={'off'}
CATALOG=Path(__file__).parent/'config/home-devices.json'
COLOURS={'red':(0,100),'orange':(30,100),'yellow':(60,100),
 'green':(120,100),'cyan':(180,100),'blue':(240,100),
 'purple':(270,100),'pink':(330,70),'white':(0,0),'warm white':(35,30)}
LIGHT_CONTEXT={}

def catalog():
 try:return json.loads(CATALOG.read_text())
 except (OSError,ValueError):return {}


def configured():
 return TOKENFILE.exists() and CONFIG.exists()


def settings():
 try:return json.loads(CONFIG.read_text())
 except Exception:return {}


def base_url():
 # homeassistant.local resolves only to link-local/IPv6 here, which is flaky
 # from a laptop that roams; the fixed LAN address answers in ~6ms.
 return settings().get('url','http://192.0.2.1:8123').rstrip('/')


def _token():
 # Read privately, use once, never retain in module state.
 return TOKENFILE.read_text().strip()


class HomeError(Exception):
 pass


def _request(path,payload=None,timeout=6):
 url=base_url()+path
 body=json.dumps(payload).encode() if payload is not None else None
 req=urllib.request.Request(url,data=body,headers={
  'Authorization':'Bearer '+_token(),'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=timeout) as r:
   return json.loads(r.read().decode() or 'null')
 except urllib.error.HTTPError as e:
  # Never echo the response body; it can repeat the Authorization header back.
  if e.code in (401,403):raise HomeError('Home Assistant rejected the access token')
  raise HomeError(f'Home Assistant returned HTTP {e.code}')
 except urllib.error.URLError:
  raise HomeError('Home Assistant is unreachable')
 except TimeoutError:
  raise HomeError('Home Assistant did not respond in time')


class Home:
 """Caches entity state briefly so a burst of spoken requests is not a burst
 of HTTP round trips. The cache is short enough that a light David just
 switched still reads correctly."""

 def __init__(self,ttl=3.0):
  self.ttl=ttl;self.lock=threading.Lock();self.at=0.0;self.cache=[]

 def states(self,force=False):
  with self.lock:
   if not force and self.cache and time.monotonic()-self.at<self.ttl:
    return self.cache
  rows=_request('/api/states') or []
  clean=[]
  for row in rows:
   entity=row.get('entity_id','')
   domain=entity.split('.')[0]
   if domain not in READABLE:continue
   clean.append({'entity_id':entity,'domain':domain,
                 'name':(row.get('attributes') or {}).get('friendly_name') or entity.split('.',1)[-1].replace('_',' '),
                 'state':row.get('state'),
                 'unit':(row.get('attributes') or {}).get('unit_of_measurement',''),
                 'attributes':{k:v for k,v in (row.get('attributes') or {}).items() if k in (
                  'device_class','supported_features','supported_color_modes','color_mode','hs_color','brightness','percentage',
                  'preset_mode','preset_modes','humidity','current_humidity','min_humidity','max_humidity',
                  'mode','available_modes','current_position')}})
  with self.lock:
   self.cache=clean;self.at=time.monotonic()
  return clean

 def resolve(self,name,domains=None):
  """Exact, then whole-word, then substring. Ambiguity is reported, not guessed."""
  return resolve(self.states(),name,domains)

 def call(self,entity_id,turn_on,brightness=None):
  return self.execute(entity_id,'set_brightness' if brightness is not None else 'turn_on' if turn_on else 'turn_off',brightness)

 def execute(self,entity_id,action,value=None):
  domain=entity_id.split('.')[0]
  if domain not in CONTROL:
   raise HomeError(f'{domain} devices are read-only in Jinx')
  if entity_id in catalog().get('read_only_entities',[]):raise HomeError('This appliance is monitored only; no power or cycle command was sent')
  entity=next((r for r in self.states(force=True) if r['entity_id']==entity_id),None)
  if not entity:raise HomeError('That device is no longer in Home Assistant')
  if entity['state'] in ('unavailable','unknown') and domain!='scene':raise HomeError(describe(entity)+'. No command was sent.')
  attrs=entity.get('attributes',{})
  if domain=='cover' and attrs.get('device_class') not in ('curtain','blind','shade'):
   raise HomeError('Only identified curtains, blinds and shades can move through Jinx; doors and gates stay read-only')
  allowed={'turn_on':CONTROL-{'cover'},'turn_off':CONTROL-{'cover','scene'},
   'set_brightness':{'light'},'set_colour':{'light'},'set_humidity':{'humidifier'},'set_fan_mode':{'fan'},
   'open_cover':{'cover'},'close_cover':{'cover'},'stop_cover':{'cover'},'set_position':{'cover'},
   'play':{'media_player'},'pause':{'media_player'}}
  if domain not in allowed.get(action,set()):raise HomeError(f'{action} is not supported for {domain}')
  service={'set_brightness':'turn_on','set_colour':'turn_on','set_fan_mode':'set_preset_mode','set_position':'set_cover_position','play':'media_play','pause':'media_pause'}.get(action,action)
  payload={'entity_id':entity_id}
  if action in ('set_brightness','set_humidity','set_position'):
   if type(value) not in (int,float) or not 0<=value<=100:raise HomeError('Choose a percentage from 0 to 100')
   value=round(value)
  if action=='set_brightness':
   if attrs.get('supported_color_modes')==['onoff']:raise HomeError('This light does not support dimming')
   payload['brightness_pct']=value
  if action=='set_colour':
   if not isinstance(value,str) or value not in COLOURS:raise HomeError('Choose a supported colour: '+', '.join(COLOURS))
   if not set(attrs.get('supported_color_modes',[]))&{'hs','xy','rgb','rgbw','rgbww'}:
    raise HomeError('This light does not support colour changes. No command was sent.')
   payload['hs_color']=list(COLOURS[value])
  if action=='set_humidity':
   if not attrs.get('min_humidity',0)<=value<=attrs.get('max_humidity',100):raise HomeError('That humidity is outside the device-supported range')
   payload['humidity']=value
  if action=='set_position':payload['position']=value
  if action=='set_fan_mode':
   if value not in attrs.get('preset_modes',[]):raise HomeError('Choose a supported purifier mode: '+', '.join(attrs.get('preset_modes',[])))
   payload['preset_mode']=value
  features=attrs.get('supported_features')
  feature={'turn_on':128,'turn_off':256,'play':16384,'pause':1}.get(action) if domain=='media_player' else {'open_cover':1,'close_cover':2,'set_position':4,'stop_cover':8}.get(action) if domain=='cover' else None
  if feature and features is not None and not features&feature:raise HomeError('Home Assistant does not expose that control for this device')
  _request(f'/api/services/{domain}/{service}',payload)
  self.at=0.0
  # A successful HTTP response only acknowledges the command. Confirm from a
  # fresh state, or explicitly report that it has not yet been verified.
  deadline=time.monotonic()+3
  while True:
   after=next((r for r in self.states(force=True) if r['entity_id']==entity_id),entity)
   state=after['state'];a=after.get('attributes',{})
   verified=False
   if action=='turn_on':verified=state not in ('off','unknown','unavailable') if domain=='media_player' else state=='on'
   elif action=='turn_off':verified=state=='off'
   elif action=='set_brightness':verified=state=='off' if value==0 else state=='on' and a.get('brightness') is not None and abs(a['brightness']*100/255-value)<=2
   elif action=='set_colour':
    actual=a.get('hs_color');target=COLOURS[value]
    if state=='on' and isinstance(actual,(list,tuple)) and len(actual)==2:
     hue=abs((actual[0]-target[0]+180)%360-180)
     verified=abs(actual[1]-target[1])<=5 and (target[1]==0 or hue<=8)
   elif action=='set_humidity':verified=a.get('humidity')==value
   elif action=='set_fan_mode':verified=a.get('preset_mode')==value
   elif action=='set_position':verified=a.get('current_position')==value
   elif action=='open_cover':verified=state=='open'
   elif action=='close_cover':verified=state=='closed'
   elif action=='stop_cover':verified=state in ('open','closed')
   elif action=='play':verified=state=='playing'
   elif action=='pause':verified=state=='paused'
   if verified or time.monotonic()>=deadline or domain=='scene':return {'verified':verified,'entity':after,'action':action}
   time.sleep(.2)


# Smart plugs and media players expose diagnostic sub-entities alongside the
# thing itself: "Lamp" comes with "Lamp Child Lock" and "Lamp Energy", and every
# Echo carries DND/Shuffle/Repeat. Matching those as if they were the device
# makes ordinary commands ambiguous, so a name ending in one of these is treated
# as secondary and only considered when nothing primary matches.
ATTRIBUTE_SUFFIXES=(
 'child lock','energy','display','dnd','do not disturb','shuffle','repeat',
 'current status','cycles','next alarm','auto off','delayed end','remaining time',
 'battery','voltage','current','signal strength','rssi','uptime','last seen',
 'firmware','update available','filter life','air quality','night light',
 'next reminder','last month','this month','today','yesterday','power factor',
)


def primary(entity):
 """False for a diagnostic sub-entity of some other device."""
 name=entity['name'].lower()
 return not any(name.endswith(' '+suffix) for suffix in ATTRIBUTE_SUFFIXES)


def resolve(rows,name,domains=None):
 want=' '.join(str(name or '').lower().split())
 if not want:return {'error':'Which device?'}
 pool=[r for r in rows if not domains or r['domain'] in domains]
 def pick(matches):
  if not matches:return None
  # Prefer the device itself over its diagnostic sub-entities.
  preferred=[m for m in matches if primary(m)] or matches
  if len(preferred)==1:return {'entity':preferred[0]}
  names=sorted({m['name'] for m in preferred})
  if len(names)==1:names=sorted(m['entity_id'] for m in preferred)
  return {'error':'Several match: '+', '.join(names[:4])}
 aliases=catalog().get('aliases',{})
 if want in aliases:
  matches=[r for r in pool if r['entity_id'] in aliases[want]]
  if not matches:return {'error':'That device is unavailable or does not support this control'}
  return pick(matches)
 exact=[r for r in pool if r['name'].lower()==want or r['entity_id'].lower()==want]
 if exact:return pick(exact)
 words=[r for r in pool if want in r['name'].lower().split(' ') or want in r['name'].lower()]
 if words:return pick(words)
 loose=[r for r in pool if all(w in r['name'].lower() for w in want.split())]
 return pick(loose) or {'error':f'No device called {name}'}


def parse(text):
 """Deterministic intent for the phrasings that must never wait on a model.

 Returns None when the request is not an unambiguous home command, so the
 caller falls through to the normal routing."""
 t=' '.join(str(text or '').lower().split()).strip(' .!?')
 if not t:return None
 # Address terms may carry punctuation ("Jinx, is the lamp on?") and may stack
 # ("Hey Jinx, could you turn on ..."), so strip repeatedly.
 for _ in range(3):
  for lead in ('hey jinx','ok jinx','please','jinx','could you','can you','would you','well','now','and'):
   if t.startswith(lead) and (len(t)==len(lead) or not t[len(lead)].isalnum()):
    t=t[len(lead):].lstrip(' ,.:');break
  else:break
 t=t.strip()

 # Named colours and explicit brightness, including natural follow-ups.
 colour=re.fullmatch(r'(?:make|set|change|turn) (.+?)(?: to)? ('+'|'.join(COLOURS)+r')',t)
 if colour:
  name=colour[1].removesuffix(' colour').removesuffix(' color')
  return {'action':'set_colour','name':name,'value':colour[2]}
 maximum=r'(?:maximum|max|full|100\s*(?:%|percent)|as bright as possible)'
 m=re.fullmatch(r'(?:make|set|turn|change) (.+?)(?: to)? '+maximum+r'(?: brightness)?',t)
 if m:
  name=m[1] if strip_article(m[1])=='brightness' else m[1].removesuffix(' brightness')
  return {'action':'set','on':True,'brightness':100,'name':name}
 m=re.fullmatch(r'(?:make|set|change|dim) (.+?)(?: brightness)? to (\d{1,3})\s*(?:%|percent)',t)
 if m and (strip_article(m[1]) in ('it','that','brightness','its brightness') or re.search(r'\b(light|lamp)\b',m[1])):
  return {'action':'set','on':int(m[2])>0,'brightness':int(m[2]),'name':m[1].removesuffix(' brightness')}

 if t in ('list home devices','list my home devices','what home devices can you control','check my home devices','home status'):
  return {'action':'list'}
 for lead in ('what is the status of ','what is the state of ','check the ','check my '):
  if t.startswith(lead):return {'action':'state','name':t[len(lead):]}
 for lead in ('open ','close ','stop '):
  if t.startswith(lead) and re.search(r'\b(curtains?|blinds?|shades?)\b',t):
   return {'action':{'open ':'open_cover','close ':'close_cover','stop ':'stop_cover'}[lead],'name':t[len(lead):]}
 if t.startswith(('pause ','resume ')) and re.search(r'\b(tv|c2|c4|television)\b',t):
  return {'action':'pause' if t.startswith('pause ') else 'play','name':t.split(' ',1)[1]}

 # "is the kitchen light on?" / "are the lights on"
 for pattern in ('is the ','is ','are the ','are '):
  if t.startswith(pattern):
   rest=t[len(pattern):]
   for suffix in (' on',' off',' open',' closed',' locked',' unlocked',' running',' finished'):
    if rest.endswith(suffix):
     return {'action':'state','name':rest[:-len(suffix)].strip()}
   return {'action':'state','name':rest.strip()}

 # "turn on the kitchen light" / "turn the kitchen light off"
 if t.startswith(('turn ','switch ')):
  rest=t.split(' ',1)[1]
  word=rest.split(' ',1)[0]
  if word in ON_WORDS|OFF_WORDS:
   return {'action':'set','on':word in ON_WORDS,'name':rest.split(' ',1)[1].strip() if ' ' in rest else ''}
  for suffix in ON_WORDS|OFF_WORDS:
   if rest.endswith(' '+suffix):
    return {'action':'set','on':suffix in ON_WORDS,'name':rest[:-len(suffix)-1].strip()}

 # "set the lamp to 40%" / "dim the lamp to 20 percent"
 if (t.startswith('set ') or t.startswith('dim ')) and ' to ' in t:
  target,_,value=t.partition(' to ')
  name=target.split(' ',1)[1].strip() if ' ' in target else ''
  if re.fullmatch(r'\d{1,3}\s*(%|percent)',value):
   amount=int(re.match(r'\d+',value)[0])
   if re.search(r'curtain|blind|shade',name):return {'action':'set_position','name':name,'value':amount}
   if 'humidifier' in name:return {'action':'set_humidity','name':name,'value':amount}
   return {'action':'set','on':amount>0,'brightness':amount,'name':name}
  if re.search(r'purifier|levoit|vital',name) and value.removesuffix(' mode') in ('auto','pet','sleep'):
   return {'action':'set_fan_mode','name':name,'value':value.removesuffix(' mode')}
 return None


def strip_article(name):
 for lead in ('the ','my ','a '):
  if name.startswith(lead):return name[len(lead):]
 return name


def describe(entity):
 value=entity['state']
 if entity['domain'] in ('sensor',) and entity['unit'] and value not in ('unavailable','unknown'):
  return f"{entity['name']} is {value}{entity['unit']}"
 spoken={'on':'on','off':'off','power_off':'powered off','unavailable':'not responding','unknown':'not reporting'}.get(value,value)
 reply=f"{entity['name']} is {spoken}"
 a=entity.get('attributes',{})
 if value not in ('unavailable','unknown'):
  if entity['domain']=='humidifier':reply+=f"; target humidity {a.get('humidity','unknown')}%, measured humidity {a.get('current_humidity','unknown')}%"
  if entity['domain']=='fan' and a.get('preset_mode'):reply+=' in '+a['preset_mode']+' mode'
 return reply

def confirmation(entity,intent,result):
 if not isinstance(result,dict) or not result.get('verified'):
  return f"Command sent to {entity['name']}, but Home Assistant has not confirmed the requested state yet."
 if intent.get('brightness') is not None:return f"{entity['name']} set to {intent['brightness']}%"
 if intent['action']=='set_colour':return f"{entity['name']} set to {intent['value']}"
 if intent['action']=='set':return f"{entity['name']} {'on' if intent['on'] else 'off'}"
 return describe(result['entity'])


HOME=Home()

def followup_request(text,home=None):
 """Called once on EVERY user turn, before desktop brightness can claim it.

 A single explicitly resolved light remains the target only through adjacent
 light requests and for two minutes. Unrelated/ambiguous turns clear it.
 """
 intent=parse(text)
 name=strip_article((intent or {}).get('name',''))
 followup=intent and (intent.get('brightness') is not None or intent['action']=='set_colour') and name in ('it','that','brightness','its brightness')
 previous=LIGHT_CONTEXT.copy();LIGHT_CONTEXT.clear()
 if not followup:return None
 if not previous or time.monotonic()-previous['at']>120:
  if name=='brightness' and re.search(r'\d',str(text)):return None
  return {'reply':'Which light do you mean? Please say its name.','_tools':['jinx_home']}
 intent={**intent,'name':previous['entity_id']}
 return requested(text,home,_intent=intent)


def requested(text,home=None,_intent=None):
 """Tier-0 entry point. Returns a reply dict, or None to fall through."""
 if not configured():return None
 intent=_intent or parse(text)
 if not intent:return None
 name=strip_article(intent.get('name',''))
 if not name and intent['action']!='list':return None
 home=home or HOME
 try:
  rows=home.states()
 except HomeError as e:
  return {'reply':str(e),'_tools':['jinx_home']}
 if intent['action']=='list':
  ids={e for values in catalog().get('aliases',{}).values() for e in values}
  chosen=[r for r in rows if r['entity_id'] in ids] or [r for r in rows if r['domain'] in CONTROL and primary(r)][:20]
  return {'reply':'; '.join(describe(r) for r in chosen), '_tools':['jinx_home']}
 known=catalog()
 if name in known.get('groups',[]) and intent['action'] in ('state','set'):
  ids=known.get('aliases',{}).get(name,[]);group=[r for r in rows if r['entity_id'] in ids]
  if len(group)!=len(ids):return {'reply':'One of those devices is missing in Home Assistant; no group command was sent.','_tools':['jinx_home']}
  if intent['action']=='state':return {'reply':'; '.join(describe(r) for r in group),'_tools':['jinx_home']}
  if any(r['state'] in ('unknown','unavailable') for r in group):return {'reply':'One of those devices is unavailable; no group command was sent.','_tools':['jinx_home']}
  if intent.get('brightness') is not None and any(r['domain']!='light' for r in group):return {'reply':'Brightness only applies to lights.','_tools':['jinx_home']}
  replies=[]
  for r in group:
   try:replies.append(confirmation(r,intent,home.call(r['entity_id'],intent['on'],intent.get('brightness'))))
   except HomeError as e:replies.append(str(e));break
  return {'reply':'; '.join(replies),'_tools':['jinx_home']}
 domains=CONTROL if intent['action']!='state' else None
 found=resolve(rows,name,domains)
 if 'error' in found:
  return {'reply':catalog().get('unavailable_devices',{}).get(name,found['error']),'_tools':['jinx_home']}
 entity=found['entity']
 if entity['domain']=='light':LIGHT_CONTEXT.update(entity_id=entity['entity_id'],at=time.monotonic())
 if intent['action']=='state':
  return {'reply':describe(entity),'_tools':['jinx_home']}
 try:
  result=home.call(entity['entity_id'],intent['on'],intent.get('brightness')) if intent['action']=='set' else home.execute(entity['entity_id'],intent['action'],intent.get('value'))
 except HomeError as e:
  return {'reply':str(e),'_tools':['jinx_home']}
 return {'reply':confirmation(entity,intent,result),'_tools':['jinx_home']}


def tool(args,home=None):
 """Guarded surface for the agent when the deterministic path did not match."""
 home=home or HOME
 action=args.get('action')
 if not configured():return {'error':'Home Assistant is not configured'}
 try:
  if action=='list':
   rows=home.states()
   domain=args.get('domain')
   if domain:rows=[r for r in rows if r['domain']==domain]
   rows=sorted(rows,key=lambda r:(r['domain'] not in CONTROL,not primary(r),r['name']))
   return {'devices':[{'entity_id':r['entity_id'],'name':r['name'],'state':r['state'],'domain':r['domain']} for r in rows[:60]],'more':len(rows)>60}
  if action=='state':
   found=home.resolve(args.get('name',''))
   if 'error' in found:return {'error':found['error']}
   return {'device':describe(found['entity'])}
  if action in ('turn_on','turn_off'):
   found=home.resolve(args.get('name',''),CONTROL)
   if 'error' in found:return {'error':found['error']}
   result=home.call(found['entity']['entity_id'],action=='turn_on',args.get('brightness'))
   reply=confirmation(found['entity'],{'action':'set','on':action=='turn_on','brightness':args.get('brightness')},result)
   return {'done' if isinstance(result,dict) and result.get('verified') else 'unconfirmed':reply}
 except HomeError as e:
  return {'error':str(e)}
 return {'error':'Unsupported action'}


def light_tool(args,user_request,home=None):
 """Model can combine light settings, but only values authorised in this turn.

 The model supplies semantic slots; the host validates the named device,
 percentage and colour against David's actual request before any write.
 """
 home=home or HOME
 text=' '.join(str(user_request).lower().split())
 check=text.replace('not so bright','less bright')
 if not re.search(r'\b(make|set|change|dim|turn|switch|give|put|lower|reduce)\b',text) or re.search(r"\b(don't|do not|never|not|if|later|tomorrow|remind|explain|instructions)\b",check):
  return {'error':'A direct request to change this light now is required. No command sent.'}
 if set(args)-{'name','brightness','colour'}:return {'error':'Unsupported light settings'}
 try:
  group=strip_article(str(args.get('name','')).lower())
  if group in catalog().get('groups',[]):
   if not re.search(r'(?<!\w)'+re.escape(group)+r'(?!\w)',text):
    return {'error':'The requested light group must be named explicitly. No command sent.'}
   ids=catalog().get('aliases',{}).get(group,[])
   rows=[r for r in home.states(force=True) if r['entity_id'] in ids]
   if not ids or len(rows)!=len(ids) or any(r['domain']!='light' or r['state'] in ('unknown','unavailable') for r in rows):
    return {'error':'The complete light group is not available. No command sent.'}
   if args.get('colour') is not None and any(not set(r.get('attributes',{}).get('supported_color_modes',[]))&{'hs','xy','rgb','rgbw','rgbww'} for r in rows):
    return {'error':'Not all of those lights support colour. Please request brightness separately.'}
   results=[]
   for row in rows:
    outcome=light_tool({**args,'name':row['entity_id']},user_request,home)
    results.append(outcome)
    if 'done' not in outcome:return {'unconfirmed':results}
   return {'done':results}
  found=home.resolve(args.get('name',''),{'light'})
  if 'error' in found:return found
  entity=found['entity'];eid=entity['entity_id']
  names=[entity['name'].lower(),eid,*[name for name,ids in catalog().get('aliases',{}).items() if eid in ids]]
  if not any(re.search(r'(?<!\w)'+re.escape(name)+r'(?!\w)',text) for name in names):
   return {'error':'Name the light explicitly for this combined command. No command sent.'}
  brightness=args.get('brightness');colour=args.get('colour')
  if brightness is None and colour is None:return {'error':'Specify brightness or colour'}
  if brightness is not None:
   values={int(v) for v in re.findall(r'\b(\d{1,3})\s*(?:%|percent|per cent)',text)}
   if re.search(r'\b(maximum|max|full brightness)\b',text):values.add(100)
   if type(brightness) is not int or not 0<=brightness<=100 or values!={brightness}:
    return {'error':'Brightness must match the single percentage David requested. No command sent.'}
  if colour is not None:
   permitted={c for c in COLOURS if re.search(r'\b'+re.escape(c)+r'\b',text)}
   if re.search(r'\b(softer tone|soft tone|softer light|soft light|warm white|warmer|warm tone)\b',text):permitted.add('warm white')
   if not isinstance(colour,str) or colour not in permitted:
    return {'error':'Colour must match the requested colour or warm/softer tone. No command sent.'}
  # All slots are validated before the first change. Each outcome is read back.
  results=[]
  if colour is not None:
   r=home.execute(eid,'set_colour',colour)
   results.append(confirmation(entity,{'action':'set_colour','value':colour},r))
   if not r.get('verified'):return {'unconfirmed':'; '.join(results)}
  if brightness is not None:
   r=home.call(eid,brightness>0,brightness)
   results.append(confirmation(entity,{'action':'set','on':brightness>0,'brightness':brightness},r))
   if not r.get('verified'):return {'unconfirmed':'; '.join(results)}
  return {'done':'; '.join(results)}
 except HomeError as error:
  return {'error':str(error),'completed':results if 'results' in locals() else []}
