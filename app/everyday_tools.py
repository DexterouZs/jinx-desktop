"""Exact everyday requests: no model, shell strings, accounts or implicit actions."""
import datetime as dt
from decimal import Decimal
import math,re,secrets,time
from zoneinfo import ZoneInfo
from pathlib import Path
import workbench

_SMALL=dict(zip(('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen').split(),range(20)))
_TENS=dict(zip('twenty thirty forty fifty sixty seventy eighty ninety'.split(),range(20,100,10)))
def number(text):
 text=text.strip().lower()
 if re.fullmatch(r'-?\d+(?:\.\d+)?',text):return Decimal(text)
 sign=-1 if text.startswith(('minus ','negative ')) else 1
 text=re.sub(r'^(?:minus|negative) ','',text).replace('-',' ')
 if text in ('a','an'):return Decimal(1)
 total=part=0;previous=''
 words=text.split()
 if not words:raise ValueError('Use a number.')
 for word in words:
  if word=='and' and previous in ('hundred','thousand'):continue
  if word in _SMALL:
   if previous in _SMALL or (previous in _TENS and _SMALL[word]>=10):raise ValueError('Unclear number.')
   part+=_SMALL[word]
  elif word in _TENS:
   if previous in _SMALL or previous in _TENS:raise ValueError('Unclear number.')
   part+=_TENS[word]
  elif word=='hundred' and 0<part<10:part*=100
  elif word=='thousand' and 0<part<1000 and total==0:total=part*1000;part=0
  else:raise ValueError('Use a number such as twenty three or 23.')
  previous=word
 return Decimal(sign*(total+part))

def clean(text):
 text=re.sub(r'\s+',' ',str(text).strip())
 text=re.sub(r'^(?:(?:hey )?jinx[, ]+)?(?:(?:please|can you|could you|would you)\s+)*','',text,flags=re.I)
 return re.sub(r'(?:,? please| for me)?[.!?]*$','',text).strip()

def duration(text):
 text=text.lower().strip().replace('-',' ')
 text=re.sub(r'\bhalf an? hour\b','30 minutes',text)
 text=re.sub(r'\ba quarter of an hour\b','15 minutes',text)
 matches=list(re.finditer(r'(.+?)\s+(seconds?|minutes?|hours?|days?)(?=\s|$)',text))
 end=0;seconds=Decimal(0)
 for match in matches:
  if match.start()!=end:raise ValueError('Use a duration such as five minutes or one hour and thirty minutes.')
  amount=re.sub(r'^and\s+','',match.group(1).strip())
  value=number(amount)
  if value<0:raise ValueError('Use a positive duration.')
  seconds+=value*{'second':1,'minute':60,'hour':3600,'day':86400}[match.group(2).rstrip('s')]
  end=match.end()
 if end!=len(text) or not 1<=seconds<=366*86400:raise ValueError('Choose a duration between one second and 366 days.')
 return float(seconds)

def duration_label(seconds):
 parts=[]
 for size,unit in [(86400,'day'),(3600,'hour'),(60,'minute'),(1,'second')]:
  value=math.floor(seconds/size) if size>1 else seconds
  if value:parts.append(f"{value:g} {unit}"+('s' if value!=1 else ''))
  seconds-=value*size
 return ' '.join(parts)

def local_now():
 # Preserve actual DST rules for dates after the current offset changes.
 # /etc/localtime can be a copied TZif file instead of a zoneinfo symlink.
 try:
  with Path('/etc/localtime').open('rb') as source:zone=ZoneInfo.from_file(source,key='local')
 except (OSError,ValueError):return dt.datetime.now().astimezone()
 return dt.datetime.now(zone)

def clock_time(text,now):
 text=re.sub(r'\bnoon\b','12 pm',text.lower());text=re.sub(r'\bmidnight\b','12 am',text)
 text=re.sub(r'\b([ap])\.?m\.?',r'\1m',text)
 match=re.fullmatch(r'(?:(today|tomorrow) (?:at )?)?(.+?)(?::(\d{2}))?\s*(am|pm)?(?: (today|tomorrow))?',text.strip())
 if not match:raise ValueError('Give the time, for example tomorrow at 7:30 am or today at 18:00.')
 day,hour,minute,period,tail=match.groups();hour_value=number(hour);hour=int(hour_value);minute=int(minute or 0)
 if hour!=hour_value or hour<0:raise ValueError('Use a clock time, such as 7:30 am.')
 if day and tail and day!=tail:raise ValueError('Choose today or tomorrow.')
 day=day or tail
 if minute>59 or hour>23 or (period and not 1<=hour<=12):raise ValueError('That time is not valid.')
 if not period and 1<=hour<=12 and match.group(3) is None:raise ValueError('Do you mean morning or evening? Say, for example, 7 am or 7 pm.')
 if period:hour=hour%12+(12 if period=='pm' else 0)
 date=now.date()+dt.timedelta(days=day=='tomorrow')
 due=dt.datetime.combine(date,dt.time(hour,minute),now.tzinfo)
 if due<=now:
  if day:raise ValueError('That time has already passed. Choose a future time.')
  due+=dt.timedelta(days=1)
 # Reject skipped/repeated local clock times rather than silently choosing an offset.
 if due.replace(fold=0).utcoffset()!=due.replace(fold=1).utcoffset():raise ValueError('That time crosses a daylight-saving clock change; choose an unambiguous time.')
 return due

def schedule_intent(text,now=None):
 text=clean(text);lower=text.lower();now=now or local_now()
 match=re.fullmatch(r'(?:set|start) (?:an? )?(?:timer for (.+?)|(.+?) timer)(?: (?:called|named) (.+))?',text,re.I)
 if match:
  length=re.sub(r'^for ','',match.group(1) or match.group(2),flags=re.I);seconds=duration(length)
  return {'action':'add','kind':'timer','text':match.group(3) or 'Timer','when':dt.datetime.fromtimestamp(now.timestamp()+seconds,now.tzinfo).isoformat(),'duration':seconds}
 match=re.fullmatch(r'remind me (?:in (.+?) to (.+)|to (.+) in (.+))',text,re.I)
 if match:
  length=match.group(1) or match.group(4);body=match.group(2) or match.group(3)
  return {'action':'add','kind':'reminder','text':body,'when':dt.datetime.fromtimestamp(now.timestamp()+duration(length),now.tzinfo).isoformat()}
 match=re.fullmatch(r'remind me (?:(today|tomorrow) )?at (.+?) to (.+)',text,re.I)
 if match:
  due=clock_time(((match.group(1)+' ') if match.group(1) else '')+match.group(2),now)
  return {'action':'add','kind':'reminder','text':match.group(3),'when':due.isoformat()}
 match=re.fullmatch(r'(?:set (?:an? )?alarm|wake me)(?: (?:for|at))? (.+)',text,re.I)
 if match:return {'action':'add','kind':'alarm','text':'Alarm','when':clock_time(match.group(1),now).isoformat()}
 if re.fullmatch(r'(?:list|show|what are)(?: me)? (?:my |the )?(timers|alarms|reminders)',lower):return {'action':'list','kind':lower.split()[-1].rstrip('s')}
 match=re.fullmatch(r'(?:how (?:much )?long(?: is left| left)?(?: on)?|check) (?:my |the )?timer(?: (?:called|named) (.+))?',text,re.I)
 if match:return {'action':'list','kind':'timer','name':match.group(1)}
 match=re.fullmatch(r'(?:cancel|stop|delete) (?:my |the )?(timer|alarm|reminder)(?: (?:called|named) (.+))?',text,re.I)
 if match:return {'action':'cancel','kind':match.group(1).lower(),'name':match.group(2)}
 if re.match(r'^(?:(?:set|start) (?:an? )?.*\b(?:timer|alarm)\b|wake me\b|remind me\b)',lower):
  raise ValueError('Say a complete time and task, for example: remind me in ten minutes to check the oven, or set an alarm for 7 am. Recurring reminders are not supported yet.')
 return None

def schedule(text,data,save,lock,now=None):
 args=schedule_intent(text,now)
 if not args:return None
 with lock:
  kind=args['kind'];items=[r for r in data['reminders'] if not r['done'] and r.get('kind','reminder')==kind]
  if args.get('name'):items=[r for r in items if r['text'].casefold()==args['name'].casefold()]
  if args['action']=='add':
   if len(args['text'])>1000:raise ValueError('Use a shorter reminder or timer name.')
   item={'id':secrets.token_hex(8),'kind':kind,'when':args['when'],'text':args['text'],'done':False}
   data['reminders'].append(item)
   try:save()
   except Exception:data['reminders'].remove(item);raise
   due=dt.datetime.fromisoformat(item['when'])
   label=duration_label(args['duration']) if kind=='timer' else due.strftime('%A %-d %B at %H:%M')
   detail=': '+item['text'] if item['text'] not in ('Timer','Alarm') else ''
   return {'reply':f"{kind.capitalize()} set for {label}{detail}. Jinx must be running.",'_tools':['jinx_schedule']}
  if args['action']=='cancel':
   if len(items)>1:return {'reply':f'You have {len(items)} active {kind}s. Name the one to cancel, or remove it in Memory & reminders.'}
   if not items:return {'reply':f'No matching active {kind}.'}
   item=items[0];item['done']=True;item['cancelled']=True
   try:save()
   except Exception:item['done']=False;item.pop('cancelled',None);raise
   return {'reply':kind.capitalize()+' cancelled: '+item['text']+'.','_tools':['jinx_schedule']}
  if not items:return {'reply':f'You have no active {kind}s.'}
  nowstamp=(now.timestamp() if now else time.time())
  descriptions=[]
  for item in items[:10]:
   due=dt.datetime.fromisoformat(item['when']);remaining=max(0,math.ceil(due.timestamp()-nowstamp))
   descriptions.append(item['text']+(': '+str(remaining)+' seconds left' if kind=='timer' else ' — '+due.strftime('%A %-d %B at %H:%M')))
  return {'reply':'; '.join(descriptions)+'.','_tools':['jinx_schedule']}

# Base SI factors: exact international foot/mile/pound, no ambiguous cups/gallons or money.
UNITS={}
def _units(dimension,factor,*names):
 for name in names:UNITS[name]=(dimension,Decimal(factor),names[0])
_units('length','1','metres','metre','meters','meter','m')
_units('length','1000','kilometres','kilometre','kilometers','kilometer','km')
_units('length','.01','centimetres','centimetre','centimeters','centimeter','cm')
_units('length','.001','millimetres','millimetre','millimeters','millimeter','mm')
_units('length','1609.344','miles','mile')
_units('length','.3048','feet','foot','ft')
_units('length','.0254','inches','inch')
_units('weight','1','kilograms','kilogram','kg')
_units('weight','.001','grams','gram','g')
_units('weight','.45359237','pounds','pound','lbs','lb')
_units('weight','.028349523125','ounces','ounce','oz')
_units('volume','1','litres','litre','liters','liter')
_units('volume','.001','millilitres','millilitre','milliliters','milliliter','ml')
_units('time','1','seconds','second')
_units('time','60','minutes','minute')
_units('time','3600','hours','hour')
_units('time','86400','days','day')

def calculation(text):
 text=clean(text).lower()
 match=re.fullmatch(r'(?:convert|what is|what\x27s) (.+?) (?:degrees? )?(celsius|fahrenheit|[cf]) (?:to|in) (?:degrees? )?(celsius|fahrenheit|[cf])',text)
 if match:
  value=number(match[1]);source=match[2][0];target=match[3][0]
  if source!=target:value=(value-32)*5/9 if target=='c' else value*9/5+32
  return {'reply':f'{value:.6g} degrees '+('Celsius.' if target=='c' else 'Fahrenheit.')}
 match=re.fullmatch(r'(?:convert|what is|what\x27s) (.+?) ('+'|'.join(UNITS)+r') (?:to|in) ('+'|'.join(UNITS)+r')',text)
 if match:
  value=number(match[1]);a=UNITS[match[2]];b=UNITS[match[3]]
  if a[0]!=b[0]:raise ValueError('Those units measure different things.')
  result=value*a[1]/b[1]
  return {'reply':f'{result:.8g} {b[2]}.','_tools':['jinx_calculate']}
 match=re.fullmatch(r'(?:calculate|what is|what\x27s|how much is) (.+)',text)
 if not match:return None
 expression=match[1]
 expression=re.sub(r'(?<=[a-z])-(?=[a-z])',' ',expression)
 pct=re.fullmatch(r'(.+?) (?:percent|per cent|%) of (.+)',expression)
 if pct:expression=f'({number(pct[1])}) / 100 * ({number(pct[2])})'
 else:
  expression=re.sub(r'\b(multiplied by|times)\b','*',expression)
  expression=re.sub(r'\bdivided by\b','/',expression)
  expression=re.sub(r'\bplus\b','+',expression);expression=re.sub(r'\bminus\b','-',expression)
  expression=expression.replace('×','*').replace('÷','/')
  if not re.search(r'[+*/%()-]',expression):return None
  pieces=re.split(r'([+*/%()\-])',expression)
  try:expression=''.join(p if p in '+*/%()-' or not p.strip() else str(number(p)) for p in pieces)
  except ValueError:return None
 try:result=workbench.calculate(expression)
 except (SyntaxError,ArithmeticError,ValueError) as error:raise ValueError('I could not calculate that. '+str(error)[:160])
 return {'reply':str(result['result']),'_tools':['jinx_calculate']}

def requested(text,data,save,lock):
 try:
  result=schedule(text,data,save,lock) or calculation(text)
  if result:return result
  note_request=re.sub(r'^(?:(?:hey )?jinx[, ]+)?(?:(?:please|can you|could you|would you)\s+)*','',str(text).strip(),flags=re.I)
  match=re.fullmatch(r'(?:take a note|dictation|write this down)(?:\s*:\s*|\s+)(.+)',note_request,re.I|re.S)
  if match:
   result=workbench.save_draft(match[1])
   return {'reply':'Saved your note in Documents/Jinx: '+match[1],'_tools':['jinx_note'],'note_path':result['path']}
 except ValueError as error:return {'reply':str(error)}
 return None
