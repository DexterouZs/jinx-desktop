"""Minute task: exit immediately when nothing is due; no AI/model/avatar startup."""
from pathlib import Path
import json,os,secrets,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'app'))
from runtime_paths import state_dir,runtime_dir
import reminder_delivery

def main():
 state=state_dir()
 if not state.exists():return
 items=reminder_delivery.due_items(state,time.time())
 if not items:return
 original=subprocess
 class Delivery:
  def run(self,args,**kwargs):
   folder=runtime_dir()/'notifications';folder.mkdir(parents=True,exist_ok=True)
   path=folder/(secrets.token_hex(12)+'.json')
   path.write_text(json.dumps({'title':args[-2],'text':args[-1],'expires':time.time()+25}),encoding='utf-8')
   try:
    result=original.run([str(ROOT/'Jinx.exe'),'--notification-file',str(path)],timeout=30,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode:raise RuntimeError('Windows did not accept the notification')
    return result
   finally:path.unlink(missing_ok=True)
 reminder_delivery.subprocess=Delivery()
 for item in items:reminder_delivery.deliver(state,item)
if __name__=='__main__':main()
