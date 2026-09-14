from runtime_paths import state_dir, models_dir, config_dir, runtime_dir
"""Fixed Morgen API adapter. Event writes require the application's yes/no gate."""
import datetime as dt
import json,os,re,urllib.request,urllib.parse,urllib.error
from pathlib import Path
from zoneinfo import ZoneInfo
STATE=state_dir()
ZONE=ZoneInfo('Europe/Paris')
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):raise ValueError('Unexpected redirect from Morgen')
OPENER=urllib.request.build_opener(NoRedirect())

def config():
 try:
  c=json.loads((STATE/'morgen-calendar.json').read_text())
  if not all(isinstance(c.get(k),str) and c[k] for k in ['id','accountId','name']):raise ValueError()
  if not (STATE/'morgen-api.key').is_file():raise ValueError()
  return c
 except (OSError,ValueError):raise ValueError('Jinx still needs its Morgen API connection. Complete the private Morgen connection setup.')

class MorgenHTTPError(ValueError):
 def __init__(self,status):
  self.status=status
  super().__init__('Morgen rejected the request (HTTP '+str(status)+'). Check connection or plan access.')

def api(path,params=None,body=None):
 if path not in ['calendars/list','events/list','events','events/create','events/delete']:raise ValueError('Unsupported calendar operation')
 try:key=(STATE/'morgen-api.key').read_text().strip()
 except OSError:raise ValueError('Morgen API key is not configured')
 url='https://api.morgen.so/v3/'+path
 if params:url+='?'+urllib.parse.urlencode(params)
 req=urllib.request.Request(url,data=json.dumps(body).encode() if body is not None else None,headers={'Authorization':'ApiKey '+key,'Accept':'application/json','Content-Type':'application/json'})
 try:
  with OPENER.open(req,timeout=20) as r:
   if r.status==204:return {'http_status':204}
   raw=r.read(4*1024*1024+1)
   if len(raw)>4*1024*1024:raise ValueError('Morgen response is too large')
   return json.loads(raw)['data']
 except urllib.error.HTTPError as e:raise MorgenHTTPError(e.code) from None
 except (OSError,TimeoutError):raise ValueError('Morgen is unreachable. Calendar changes were not verified.') from None

def duration(value):
 m=re.fullmatch(r'P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?)?',value)
 if not m:raise ValueError('Unsupported event duration from Morgen')
 d,h,mi,s=(float(v or 0) for v in m.groups());return dt.timedelta(days=d,hours=h,minutes=mi,seconds=s)

def times(e):
 a=dt.datetime.fromisoformat(e['start'])
 if e.get('showWithoutTime'):return a.date(),(a+duration(e['duration'])).date()
 if a.tzinfo is None:
  if not e.get('timeZone'):raise ValueError('Morgen event has no timezone')
  a=a.replace(tzinfo=ZoneInfo(e['timeZone']))
 a=a.astimezone(dt.timezone.utc);return a.astimezone(ZONE),(a+duration(e['duration'])).astimezone(ZONE)

def read(args):
 c=config();day=dt.date.fromisoformat(args.get('date') or dt.datetime.now(ZONE).date().isoformat());days=args.get('days',7)
 if type(days) is not int or not 1<=days<=31:raise ValueError('Choose 1 to 31 days')
 a=dt.datetime.combine(day,dt.time(),ZONE);b=a+dt.timedelta(days=days)
 readable=STATE/'morgen-readable-calendars.json'
 calendars=json.loads(readable.read_text()) if readable.exists() else [c]
 groups={}
 for cal in calendars:groups.setdefault(cal['accountId'],[]).append(cal)
 events=[]
 for account,group in groups.items():
  result=api('events/list',{'accountId':account,'calendarIds':','.join(cal['id'] for cal in group),'start':a.isoformat(),'end':b.isoformat()})
  names={cal['id']:cal['name'] for cal in group}
  for e in result.get('events',[]):events.append((e,names.get(e.get('calendarId'),'Calendar')))
 rows=[]
 for e,name in events:
  start,end=times(e);rows.append({'title':str(e.get('title','Untitled'))[:300],'calendar':name,'start':start.isoformat(),'end':end.isoformat(),'all_day':bool(e.get('showWithoutTime'))})
 rows.sort(key=lambda e:e['start'])
 return {'default_calendar':c['name'],'calendars':[cal['name'] for cal in calendars],'provider':'Morgen','timezone':str(ZONE),'events':rows[:100],'truncated':len(rows)>100}

def create(fields,proposal_id):
 from calendar_tools import validate
 title,start,end=validate(fields);c=config()
 if not re.fullmatch('[a-f0-9]{16}',proposal_id):raise ValueError('Invalid calendar proposal')
 if fields.get('_calendar')!=c:raise ValueError('Calendar selection changed. Request a new readback before adding this appointment.')
 if start.timestamp()<=dt.datetime.now(dt.timezone.utc).timestamp():raise ValueError('Choose a future appointment time')
 # UTC avoids ambiguous repeated clock times at the end of daylight saving.
 body={'accountId':c['accountId'],'calendarId':c['id'],'title':title,'start':start.astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S'),'timeZone':'Etc/UTC','duration':'PT'+str(int((end-start).total_seconds()))+'S','showWithoutTime':False,'privacy':'private','description':str(fields.get('description',''))[:4000],'descriptionContentType':'text/plain','useDefaultAlerts':True}
 if fields.get('_reminder'):
  body.update(freeBusyStatus='free',useDefaultAlerts=False,alerts={'jinx':{'@type':'Alert','trigger':{'@type':'OffsetTrigger','offset':'PT0S','relativeTo':'start'},'action':'display'}})
 folder=STATE/'calendar-writes';folder.mkdir(exist_ok=True)
 path=folder/(proposal_id+'.json')
 try:
  fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 except FileExistsError:
  saved=json.loads(path.read_text())
  if saved.get('body')!=body or not saved.get('id'):raise ValueError('An earlier calendar write needs checking. I will not risk creating a duplicate.')
 else:
  saved={'body':body,'state':'attempting'}
  with os.fdopen(fd,'w') as f:json.dump(saved,f);f.flush();os.fsync(f.fileno())
  # Never retry a write automatically after a network interruption.
  e=api('events/create',body=body).get('event',{});saved['id']=e.get('id');saved['state']='needs_verification'
  path.write_text(json.dumps(saved))
  if not saved['id']:raise ValueError('Morgen did not return an event ID. Check the calendar before retrying.')
 e=api('events',{'id':saved['id']}).get('event',{})
 a,b=times(e)
 if e.get('title')!=title or e.get('calendarId')!=c['id'] or e.get('accountId')!=c['accountId'] or a!=start or b!=end:raise ValueError('The saved appointment did not match the request. Check Morgen before retrying.')
 if fields.get('_reminder') and not any(v.get('action')=='display' and duration(v.get('trigger',{}).get('offset','').lstrip('-'))==dt.timedelta(0) for v in e.get('alerts',{}).values()):raise ValueError('Calendar reminder saved, but its at-time alert could not be verified.')
 saved['state']='verified';path.write_text(json.dumps(saved))
 return 'Added to '+c['name']+' in Morgen: '+title+', '+start.astimezone(ZONE).strftime('%A %d %B at %H:%M')+' to '+end.astimezone(ZONE).strftime('%A %d %B at %H:%M')+'.'

def reminder(fields,identifier):
 when=dt.datetime.fromisoformat(fields['when'])
 converted={'title':fields['text'],'start':when.isoformat(),'end':(when+dt.timedelta(minutes=1)).isoformat(),'_calendar':fields['_calendar'],'_reminder':True,'description':'Jinx reminder marker, not a work shift. Work duration is not specified.'}
 create(converted,identifier)
 return 'Calendar reminder saved for '+when.astimezone(ZONE).strftime('%A %d %B at %H:%M')+': '+fields['text']+'. Phone delivery uses Morgen calendar notification settings.'
