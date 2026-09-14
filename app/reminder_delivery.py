from runtime_paths import state_dir, models_dir, config_dir, runtime_dir
from file_locks import fcntl
"""Short-lived desktop reminders, independent of AI/model/avatar services."""
import datetime as dt,json,os,subprocess
from pathlib import Path

def deliver(state,item):
 state=Path(state);folder=state/'notification-delivery';folder.mkdir(exist_ok=True,mode=0o700)
 # Shared ledger prevents timer/backend double delivery without rewriting AI state.
 import hashlib
 key=hashlib.sha256((str(item['id'])+'|'+str(dt.datetime.fromisoformat(item['when']).timestamp())).encode()).hexdigest()
 with (folder/'lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  done=folder/key
  if done.exists():return False
  subprocess.run(['notify-send','--app-name=Jinx','--urgency=critical','--hint=string:sound-name:alarm-clock-elapsed','--','Jinx '+item.get('kind','reminder'),str(item['text'])],check=True,timeout=5)
  done.write_text(dt.datetime.now(dt.timezone.utc).isoformat())
  return True

def due_items(state,now):
 state=Path(state);items={}
 try:
  for r in json.loads((state/'state.json').read_text()).get('reminders',[]):
   if not r.get('done'):items[(r['id'],r['when'])]=r
 except FileNotFoundError:pass
 # Only verified Jinx-created reminder markers, not arbitrary appointments.
 for p in (state/'calendar-writes').glob('*.json'):
  try:
   entry=json.loads(p.read_text());b=entry.get('body',{})
   if entry.get('state')!='verified' or b.get('freeBusyStatus')!='free' or not b.get('alerts'):continue
   from zoneinfo import ZoneInfo
   when=dt.datetime.fromisoformat(b['start'])
   if when.tzinfo is None:when=when.replace(tzinfo=ZoneInfo(b['timeZone']))
   r={'id':p.stem,'when':when.isoformat(),'text':b['title'],'kind':'reminder'}
   # Calendar markers require live revalidation before delivery (may be edited/deleted).
   if when.timestamp()>now:continue
   import morgen_tools
   event=morgen_tools.api('events',{'id':entry['id']}).get('event',{})
   if not event or event.get('status')=='cancelled':continue
   start,_=morgen_tools.times(event)
   r.update(when=start.isoformat(),text=event.get('title',r['text']))
   items[(r['id'],r['when'])]=r
  except (OSError,ValueError,KeyError):continue
 return [r for r in items.values() if dt.datetime.fromisoformat(r['when']).timestamp()<=now]

def main():
 import time
 os.umask(0o077);state=state_dir()
 for item in due_items(state,time.time()):deliver(state,item)
if __name__=='__main__':main()
