"""Fixed local ZapZap launch and DOM adapter for Jinx's reviewed messages."""
import json, os, re, socket, subprocess, sys, threading, time, urllib.request
from urllib.parse import urlsplit
import reviewed_apps

PORT=17343
ORIGIN='http://127.0.0.1:'+str(PORT)

def targets():
 with urllib.request.urlopen(ORIGIN+'/json/list',timeout=2) as response:rows=json.load(response)
 return [r for r in rows if r.get('type')=='page' and urlsplit(r.get('url','')).netloc=='web.whatsapp.com']

def open_app():
 if not reviewed_apps.verified():raise ValueError('Install the reviewed WhatsApp (ZapZap) app first.')
 # The desktop app has its own lifetime, like Discord and Spotify. Only this
 # fixed executable is started; user/model text never becomes an argument.
 state=subprocess.run(['systemctl','--user','is-active','jinx-whatsapp-app.service'],capture_output=True,text=True)
 if state.returncode==0:
  # ZapZap's upstream single-instance server raises its window on connection.
  with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as connection:
   connection.settimeout(2);connection.connect('/tmp/zapzap-application')
  return
 args=['systemd-run','--user','--collect','--quiet','--unit=jinx-whatsapp-app','--property=Type=exec','--property=ExitType=cgroup','--setenv=QTWEBENGINE_REMOTE_DEBUGGING=127.0.0.1:'+str(PORT),'--setenv=QTWEBENGINE_CHROMIUM_FLAGS=--remote-allow-origins='+ORIGIN,str(reviewed_apps.APP)]
 result=subprocess.run(args,capture_output=True,text=True)
 if result.returncode and subprocess.run(['systemctl','--user','is-active','jinx-whatsapp-app.service'],capture_output=True).returncode:raise ValueError('The WhatsApp app could not start.')

class Element:
 def __init__(self,driver,object_id):
  self.driver=driver;self.object_id=object_id
  self.id=driver.call('DOM.describeNode',{'objectId':object_id})['node']['backendNodeId']
 def __eq__(self,other):return isinstance(other,Element) and self.driver is other.driver and self.id==other.id
 def method(self,body,args=(),by_value=True):
  r=self.driver.call('Runtime.callFunctionOn',{'objectId':self.object_id,'functionDeclaration':'function(...args){'+body+'}','arguments':[{'value':v} for v in args],'returnByValue':by_value,'silent':True})
  if r.get('exceptionDetails'):raise ValueError('The WhatsApp control changed. Nothing will be retried automatically.')
  return r['result'].get('value') if by_value else r['result']
 @property
 def text(self):return self.method('return this.innerText || "";')
 def get_attribute(self,name):return self.method('return this.getAttribute(args[0]);',[name])
 def is_displayed(self):return self.method('const r=this.getBoundingClientRect();return this.isConnected && r.width>0 && r.height>0 && getComputedStyle(this).visibility!=="hidden";')
 def find_elements(self,by,selector):return self.driver.elements(selector,self)
 def send_keys(self,text):
  if not self.is_displayed():raise ValueError('The message box is not visible.')
  self.method('this.focus();')
  if not self.method('return document.activeElement===this;'):raise ValueError('Could not focus the exact message box.')
  self.driver.call('Input.insertText',{'text':text})
 def clear(self):
  self.method('this.focus();')
  if not self.method('return document.activeElement===this;'):raise ValueError('Could not focus the exact input.')
  for kind in ('keyDown','keyUp'):self.driver.call('Input.dispatchKeyEvent',{'type':kind,'key':'a','code':'KeyA','windowsVirtualKeyCode':65,'modifiers':2})
  for kind in ('keyDown','keyUp'):self.driver.call('Input.dispatchKeyEvent',{'type':kind,'key':'Backspace','code':'Backspace','windowsVirtualKeyCode':8})
 def click(self):
  point=self.method('const r=this.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};')
  if not self.is_displayed():raise ValueError('The selected WhatsApp button is not visible.')
  self.driver.call('Input.dispatchMouseEvent',{'type':'mousePressed','button':'left','clickCount':1,**point})
  self.driver.call('Input.dispatchMouseEvent',{'type':'mouseReleased','button':'left','clickCount':1,**point})
 def click_reviewed(self,text,label):
  # Check the exact composer and activate Send in one JS task, so a separate
  # input event cannot change the message between the check and the click.
  return self.method('const boxes=document.querySelectorAll("#main footer [contenteditable=true][role=textbox]");if(location.origin!=="https://web.whatsapp.com"||boxes.length!==1||boxes[0].innerText!==args[0]||boxes[0].getAttribute("aria-label")!==args[1]||!this.isConnected||this.getAttribute("aria-label")!=="Send")throw Error("Message changed");this.click();return true;',[text,label])

class AppDriver:
 def __init__(self):
  import websocket
  rows=targets()
  if len(rows)!=1:raise ValueError('Use one WhatsApp account in ZapZap while connecting Jinx.')
  endpoint=rows[0]['webSocketDebuggerUrl'];u=urlsplit(endpoint)
  if u.scheme!='ws' or u.hostname!='127.0.0.1' or u.port!=PORT:raise ValueError('Unexpected local app connection.')
  self.socket=websocket.create_connection(endpoint,timeout=5,origin=ORIGIN)
  self.sequence=0;self.mutex=threading.RLock();self.target=rows[0]['id']
 def call(self,method,params=None):
  with self.mutex:
   self.sequence+=1;identifier=self.sequence
   self.socket.send(json.dumps({'id':identifier,'method':method,'params':params or {}}))
   deadline=time.monotonic()+8
   while time.monotonic()<deadline:
    row=json.loads(self.socket.recv())
    if row.get('id')!=identifier:continue
    if 'error' in row:raise ValueError('The WhatsApp app control is unavailable or changed.')
    return row.get('result',{})
   raise ValueError('The WhatsApp app did not respond in time.')
 def evaluate(self,expression):
  row=self.call('Runtime.evaluate',{'expression':expression,'returnByValue':True,'silent':True})
  if row.get('exceptionDetails'):raise ValueError('The WhatsApp page is not ready.')
  return row['result'].get('value')
 @property
 def title(self):return self.evaluate('document.title')
 @property
 def current_url(self):return self.evaluate('location.href')
 @property
 def window_handles(self):return [r['id'] for r in targets()]
 def get(self,url):
  u=urlsplit(url)
  if u.scheme!='https' or u.netloc!='web.whatsapp.com':raise ValueError('Only the official WhatsApp app page is supported.')
  self.call('Page.navigate',{'url':url})
  deadline=time.monotonic()+30
  while time.monotonic()<deadline:
   try:
    if self.current_url==url and self.evaluate('document.readyState')=='complete':return
   except ValueError:pass
   time.sleep(.2)
  raise ValueError('WhatsApp did not finish opening the requested chat.')
 def elements(self,selector,parent=None):
  if parent:result=parent.method('return Array.from(this.querySelectorAll(args[0]));',[selector],False)
  else:
   row=self.call('Runtime.evaluate',{'expression':'Array.from(document.querySelectorAll('+json.dumps(selector)+'))','returnByValue':False,'silent':True})
   if row.get('exceptionDetails'):raise ValueError('The WhatsApp page is not ready.')
   result=row['result']
  object_id=result.get('objectId')
  if not object_id:return []
  props=self.call('Runtime.getProperties',{'objectId':object_id,'ownProperties':True})['result']
  elements=[Element(self,p['value']['objectId']) for p in props if p['name'].isdigit() and p.get('value',{}).get('objectId')]
  self.call('Runtime.releaseObject',{'objectId':object_id})
  return elements
 def find_elements(self,by,selector):
  if by!='css selector':raise ValueError('Unsupported app selector.')
  return self.elements(selector)
 def quit(self):self.socket.close()

if __name__=='__main__':
 if sys.argv[1:]!=['--open']:raise SystemExit('Use --open')
 open_app()
