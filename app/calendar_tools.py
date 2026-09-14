from runtime_paths import state_dir, models_dir, config_dir, runtime_dir
"""Local Merkuro/Akonadi calendar, with confirmed idempotent event creation."""
import datetime as dt
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
from zoneinfo import ZoneInfo
import icalendar
import recurring_ical_events

CONFIG=state_dir()/'calendar.json'
CALENDAR_FILE=Path.home()/'.local/share/jinx/calendar/Jinx Calendar.ics'
ZONE=ZoneInfo('Europe/Paris')

def contents():
 if CALENDAR_FILE.stat().st_size>16*1024*1024:raise ValueError('Calendar is too large for Jinx to read safely')
 return icalendar.Calendar.from_ical(CALENDAR_FILE.read_bytes())

def verified(uid,title,start,end):
 events=[e for e in contents().walk('VEVENT') if str(e.get('UID',''))==uid]
 return len(events)==1 and str(events[0].get('SUMMARY',''))==title and events[0].decoded('DTSTART')==start and events[0].decoded('DTEND')==end

def run(args):
 p=subprocess.run(['konsolekalendar',*args],capture_output=True,text=True,timeout=20,
                  env={**os.environ,'LC_ALL':'C.UTF-8'})
 if p.returncode:raise ValueError('The local calendar could not complete the request.')
 return p.stdout.strip()

def calendar_id():
 config=json.loads(CONFIG.read_text())
 if config.get('preferred_app')=='morgen':
  import morgen_tools
  return morgen_tools.config()['id']
 identifier=str(config['id']);name=config['name']
 if not re.fullmatch(r'\d+',identifier):raise ValueError('Invalid calendar configuration')
 if not re.search(r'^'+identifier+r'\s+-\s+'+re.escape(name)+r'\s*$',run(['--list-calendars']),re.M):
  raise ValueError('Jinx Calendar is not available. No event was changed.')
 return identifier

def validate(fields):
 title=str(fields.get('title','')).strip()
 if not title or len(title)>300:raise ValueError('Provide an event title up to300 characters')
 start=dt.datetime.fromisoformat(str(fields.get('start','')))
 end=dt.datetime.fromisoformat(str(fields.get('end','')))
 if start.tzinfo is None or end.tzinfo is None or end<=start:raise ValueError('Provide start and end times with timezone offsets')
 if end-start>dt.timedelta(days=7):raise ValueError('Events longer than7 days need manual review')
 return title,start,end

def create(fields,proposal_id):
 if json.loads(CONFIG.read_text()).get("preferred_app")=="morgen":
  import morgen_tools
  return morgen_tools.create(fields,proposal_id)
 title,start,end=validate(fields)
 if not re.fullmatch(r'[a-f0-9]{16}',proposal_id):raise ValueError('Invalid event proposal')
 uid='jinx-'+proposal_id+'@local';cid=calendar_id()
 def esc(value):return str(value).replace('\\','\\\\').replace('\r','').replace('\n','\\n').replace(';','\\;').replace(',','\\,')
 def stamp(value):return value.astimezone(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
 lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Jinx//Calendar//EN','BEGIN:VEVENT',
        'UID:'+uid,'DTSTAMP:'+stamp(dt.datetime.now(dt.timezone.utc)),
        'DTSTART:'+stamp(start),'DTEND:'+stamp(end),'SUMMARY:'+esc(title),
        'DESCRIPTION:'+esc(str(fields.get('description',''))[:4000]),'END:VEVENT','END:VCALENDAR']
 # RFC5545 folds by UTF-8 octets, not Python character count.
 folded=[]
 for line in lines:
  part=''
  for char in line:
   if len((part+char).encode())>73:folded.append(part);part=' '
   part+=char
  folded.append(part)
 with tempfile.TemporaryDirectory(prefix='jinx-calendar-') as folder:
  file=Path(folder)/'event.ics';file.write_bytes(('\r\n'.join(folded)+'\r\n').encode())
  run(['--calendar',cid,'--import',str(file)])
 for attempt in range(16):
  if verified(uid,title,start,end):break
  if attempt==15:raise ValueError('Calendar import returned, but the saved event could not be verified. Do not retry with a new proposal until checked.')
  time.sleep(.2)
 return 'Added to Jinx Calendar: '+title+', '+start.strftime('%A %d %B at %H:%M')+' to '+end.strftime('%H:%M')+'.'

def read_calendar(args):
 try:
  if json.loads(CONFIG.read_text()).get("preferred_app")=="morgen":
   import morgen_tools
   return morgen_tools.read(args)
  start=dt.date.fromisoformat(args.get('date') or dt.date.today().isoformat())
  days=args.get('days',7)
  if type(days) is not int or not 1<=days<=31:raise ValueError('Choose1 to31 days')
  calendar_id()
  begin=dt.datetime.combine(start,dt.time(),ZONE);end=begin+dt.timedelta(days=days)
  events=recurring_ical_events.of(contents()).between(begin,end)
  def local(value):
   if isinstance(value,dt.datetime):return value.replace(tzinfo=ZONE) if value.tzinfo is None else value.astimezone(ZONE)
   return value
  result=[]
  for event in events:
   a=local(event.decoded('DTSTART'));b=local(event.decoded('DTEND',event.decoded('DTSTART')))
   result.append({'title':str(event.get('SUMMARY','Untitled'))[:300], 'start':a.isoformat(),'end':b.isoformat(),'all_day':not isinstance(a,dt.datetime)})
  result.sort(key=lambda e:e['start'])
  return {'calendar':'Jinx Calendar','timezone':str(ZONE),'from':start.isoformat(),'days':days,'events':result[:100],'truncated':len(result)>100}
 except (ValueError,OSError,subprocess.TimeoutExpired) as error:
  return {'error':str(error)[:250]}


def read(args):
 result=read_calendar(args)
 import obsidian_tools
 try:result['obsidian']=obsidian_tools.read(args)
 except (ValueError,OSError):result['obsidian']={'error':'Obsidian tasks could not be read.'}
 return result
