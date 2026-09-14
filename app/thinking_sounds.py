"""Cached, interruptible thinking interjections; never synthesise on the hot path."""
import json,random,threading
class ThinkingSounds:
 def __init__(self,folder):self.folder=folder;self.bag=[];self.last=None;self.lock=threading.Lock()
 def choose(self):
  with self.lock:
   if not self.bag:
    entries=json.loads((self.folder/'manifest.json').read_text())
    self.bag=[e for e in entries if (self.folder/e['file']).is_file()]
    random.SystemRandom().shuffle(self.bag)
    if len(self.bag)>1 and self.bag[-1]['file']==self.last:self.bag[0],self.bag[-1]=self.bag[-1],self.bag[0]
   entry=self.bag.pop();self.last=entry['file'];return self.folder/entry['file'],entry['text']
 def begin(self,play,cancelled,delay=.8):return FillerSession(self,play,cancelled,delay)
class FillerSession:
 def __init__(self,bank,play,cancelled,delay):
  self.done=threading.Event();self.bank=bank;self.play=play;self.cancelled=cancelled;self.delay=delay
  self.thread=threading.Thread(target=self.run,daemon=True,name='jinx-thinking-sounds');self.thread.start()
 def stopped(self):return self.done.is_set() or self.cancelled()
 def run(self):
  try:
   if self.done.wait(self.delay) or self.stopped():return
   # At most two interjections during a slow turn, with space between them.
   for _ in range(2):
    if self.stopped():break
    path,text=self.bank.choose();self.play(path,text,self.stopped)
    if self.done.wait(7) or self.stopped():break
  except (OSError,ValueError,IndexError,RuntimeError):pass
 def cancel(self):self.done.set()
 def stop(self):
  self.cancel()
  if self.thread is not threading.current_thread():self.thread.join(timeout=2)
