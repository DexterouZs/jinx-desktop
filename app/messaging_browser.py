"""Visible, standalone WhatsApp app. No account tokens or chat history API."""
import json, os, re, subprocess, threading, time
from pathlib import Path
from urllib.parse import urlencode, urlsplit

class WhatsAppBrowser:
 def __init__(self, root):
  self.root=Path(root);self.driver=None;self.mutex=threading.RLock();self.staged=None;self.last_status={'connected':False,'ready':False,'message':'Connect WhatsApp and link your phone in the ZapZap app.'}
 def connect(self):
  with self.mutex:
   if self.driver:
    try:self.driver.title;return self.probe()
    except Exception:self.driver=None
   from zapzap_control import open_app, AppDriver
   open_app();deadline=time.monotonic()+25
   while time.monotonic()<deadline:
    try:self.driver=AppDriver();break
    except Exception:time.sleep(.25)
   else:raise ValueError('The WhatsApp app did not expose its local message controls.')
   return self.probe()
 def status(self):return dict(self.last_status)
 def probe(self):
  self.last_status=self._probe();return self.status()
 def _probe(self):
  with self.mutex:
   if not self.driver:return {'connected':False,'ready':False,'message':'Connect WhatsApp in Messaging, then link your phone in the ZapZap app.'}
   try:
    self._origin()
    ready=bool(self.driver.find_elements('css selector','#pane-side'))
    return {'connected':True,'ready':ready,'message':'WhatsApp is linked.' if ready else 'Link WhatsApp with your phone in the ZapZap app.'}
   except Exception:return {'connected':False,'ready':False,'message':'The WhatsApp app is closed or disconnected. Reconnect it before messaging.'}
 def _origin(self):
  if not self.driver:raise ValueError('Connect WhatsApp in Messaging first.')
  if len(self.driver.window_handles)!=1:raise ValueError('Use one WhatsApp account in ZapZap while messaging with Jinx.')
  u=urlsplit(self.driver.current_url)
  if u.scheme!='https' or u.netloc!='web.whatsapp.com':raise ValueError('The messaging browser must be on official WhatsApp Web.')
 def _editor(self):
  found=[e for e in self.driver.find_elements('css selector','#main footer [contenteditable="true"][role="textbox"]') if e.is_displayed()]
  if len(found)!=1:raise ValueError('Could not identify one WhatsApp message box. Nothing sent.')
  return found[0]
 def _header(self):
  headers=self.driver.find_elements('css selector','#main header')
  if len(headers)!=1:raise ValueError('Could not verify the selected WhatsApp recipient.')
  return headers[0]
 def _verify_number(self,phone):
  digits=phone.lstrip('+')
  # Read recipient identifiers, never previous message bodies. New WhatsApp
  # versions can use opaque LIDs; those cannot be treated as phone numbers.
  for element in self.driver.find_elements('css selector','#main [data-id]'):
   identifier=element.get_attribute('data-id') or ''
   match=re.match(r'^(?:true|false)_([0-9]+)@c\.us_',identifier)
   if match:
    if match[1]!=digits:raise ValueError('WhatsApp’s recipient number differs from the saved contact. Nothing sent.')
    return True
  for element in self._header().find_elements('css selector','[title]'):
   label=element.get_attribute('title') or ''
   if re.sub(r'[^0-9]','',label)==digits:return True
  details=self._contact_details()
  if details['phone'].lstrip('+')!=digits:raise ValueError('The contact-info phone number differs from the reviewed recipient. Nothing sent.')
  return True
 def _contact_details(self,name=None):
  button=self.driver.find_elements('css selector','#main header [aria-label="Profile details"]')
  if len(button)!=1:raise ValueError('Could not verify the recipient’s contact details.')
  existing=self.driver.find_elements('css selector','[data-testid="chat-info-drawer"]')
  opened=not existing
  if opened:button[0].click()
  try:
   deadline=time.monotonic()+5;rows=[]
   while time.monotonic()<deadline:
    rows=self.driver.find_elements('css selector','[data-testid="chat-info-drawer"]')
    if len(rows)==1:break
    time.sleep(.1)
   if len(rows)!=1:raise ValueError('No unique contact-info panel appeared.')
   drawer=rows[0]
   # Extract only the exact requested name and phone from Contact info.
   # No chat messages, profile About field, cookies or account tokens are read.
   details=drawer.method('const heading=this.querySelector("[data-testid=contact-info-header] h2");const leaves=Array.from(this.querySelectorAll("span,div")).filter(e=>e.childElementCount===0);return {contact:heading?.innerText==="Contact info",nameMatches:!args[0]||leaves.some(e=>e.textContent.trim().toLocaleLowerCase()===args[0].toLocaleLowerCase()),phones:[...new Set(leaves.map(e=>e.textContent.trim()).filter(t=>/^\\+[0-9 ()-]{7,25}$/.test(t)).map(t=>"+"+t.replace(/[^0-9]/g,"")))]};',[name])
   if not details['contact'] or not details['nameMatches'] or len(details['phones'])!=1:raise ValueError('The contact name and phone number could not be uniquely verified. Nothing sent.')
   return {'name':name,'phone':details['phones'][0]}
  finally:
   if opened and len(rows)==1:
    close=rows[0].find_elements('css selector','button[aria-label="Close"]')
    if len(close)==1:close[0].click()
 def suggest_contacts(self,name):
  from difflib import SequenceMatcher
  with self.mutex:
   if not self.probe()['ready']:return []
   names=set()
   for element in self.driver.find_elements('css selector','#pane-side [title]'):
    label=(element.get_attribute('title') or '').strip()
    if element.is_displayed() and re.fullmatch(r'[\w .\-]{1,60}',label) and SequenceMatcher(None,name.casefold(),label.casefold()).ratio()>=.8:
     names.add(label)
   return sorted(names)[:3]
 def lookup_contact(self,name):
  with self.mutex:
   if not self.probe()['ready']:raise ValueError(self.status()['message'])
   selector='#pane-side [title='+json.dumps(name,ensure_ascii=False)+' i]'
   matches=[e for e in self.driver.find_elements('css selector',selector) if e.is_displayed()]
   if len(matches)!=1:
    search=self.driver.find_elements('css selector','#side input[aria-label="Search or start a new chat"]')
    if len(search)!=1:return None
    search[0].clear();search[0].send_keys(name)
    deadline=time.monotonic()+5
    while time.monotonic()<deadline:
     matches=[e for e in self.driver.find_elements('css selector',selector) if e.is_displayed()]
     if matches:break
     time.sleep(.2)
   if len(matches)!=1:return None
   matches[0].click()
   deadline=time.monotonic()+5
   while time.monotonic()<deadline:
    try:
     label=self._editor().get_attribute('aria-label') or ''
     if label.casefold()==('Type a message to '+name).casefold():break
    except ValueError:pass
    time.sleep(.1)
   else:raise ValueError('The opened chat does not identify the exact requested recipient.')
   return self._contact_details(name)
 def owns_composer(self,editor,phone,previous):
  if previous and previous.get('phone')==phone and editor==previous['editor'] and editor.text==previous['text']:return True
  # After a backend restart, only replace a recent exact composer we wrote,
  # and only after stage() has independently verified the current phone number.
  try:
   owned=json.loads((self.root.parent/'composer-owned.json').read_text())
   return owned['phone']==phone and owned['text']==editor.text and 0<=time.time()-owned['at']<86400
  except (OSError,ValueError,KeyError,TypeError):return False
 def stage(self, draft, contact, cancelled=lambda:False):
  with self.mutex:
   if not self.probe()['ready']:raise ValueError(self.status()['message'])
   previous=self.staged;self.staged=None
   # Use WhatsApp's phone-addressed chat route; never choose a similar name.
   current=False
   try:
    if (self._editor().get_attribute('aria-label') or '').casefold()==('Type a message to '+contact['name']).casefold():
     self._verify_number(contact['phone']);current=True
   except ValueError:pass
   if not current:self.driver.get('https://web.whatsapp.com/send?'+urlencode({'phone':contact['phone'].lstrip('+')}))
   deadline=time.monotonic()+25
   while time.monotonic()<deadline:
    if cancelled():raise ValueError('Message preparation stopped. Nothing sent.')
    try:editor=self._editor();header=self._header();break
    except ValueError:time.sleep(.2)
   else:raise ValueError('WhatsApp did not open the requested contact. Check the saved number and linked phone.')
   self._origin()
   self._verify_number(contact['phone'])
   labels=[e.get_attribute('title') for e in header.find_elements('css selector','[title]')]
   norm=lambda s:re.sub(r'[^a-z0-9+]','',s.lower())
   expected={norm(contact['name']),norm(contact['phone']),norm(contact['phone'].lstrip('+'))}
   editor_label=editor.get_attribute('aria-label') or ''
   identities=[label for label in labels if norm(label or '') in expected]
   if editor_label.casefold()==('Type a message to '+contact['name']).casefold():identities.append(editor_label)
   if not identities:raise ValueError('The WhatsApp chat heading does not match the saved recipient. Check the contact name/number; nothing sent.')
   if editor.text.strip():
    if self.owns_composer(editor,contact['phone'],previous):editor.clear()
    else:raise ValueError('That chat already contains an unsent draft I cannot verify as mine. It has been preserved; finish or clear it in WhatsApp first.')
   if cancelled():raise ValueError('Message preparation stopped. Nothing sent.')
   # send_keys newline would press Enter; multiline messages are not supported.
   editor.send_keys(draft['text'])
   if editor.text!=draft['text']:raise ValueError('WhatsApp did not preserve the exact dictated wording. Nothing sent.')
   from software_installer import atomic
   atomic(self.root.parent/'composer-owned.json',{'phone':contact['phone'],'text':draft['text'],'at':time.time()})
   self.staged={'id':draft['id'],'editor':editor,'header':header,'identity':identities[0],'text':draft['text'],'phone':contact['phone']}
   return True
 def send(self, draft):
  with self.mutex:
   self._origin();staged=self.staged
   if not staged or staged['id']!=draft['id']:raise ValueError('This message is no longer staged. Prepare it and hear the read-back again.')
   self._verify_number(draft['phone'])
   editor=self._editor();header=self._header()
   labels=[e.get_attribute('title') for e in header.find_elements('css selector','[title]')]
   labels.append(editor.get_attribute('aria-label') or '')
   if editor!=staged['editor'] or header!=staged['header'] or staged['identity'] not in labels or editor.text!=draft['text']:raise ValueError('The recipient or message changed in WhatsApp. Nothing sent; review it again.')
   before={e.id for e in self.driver.find_elements('css selector','#main .message-out')}
   buttons=[e for e in self.driver.find_elements('css selector','#main footer button[aria-label="Send"]') if e.is_displayed()]
   if len(buttons)!=1:raise ValueError('Could not identify WhatsApp’s Send button. Nothing sent.')
   # Consume the browser ticket before the only external send attempt.
   self.staged=None
   try:buttons[0].click_reviewed(draft['text'],editor.get_attribute('aria-label'))
   except Exception:return {'state':'uncertain','message':'The send result is uncertain. Check WhatsApp before sending again; I will not retry automatically.'}
   deadline=time.monotonic()+15
   while time.monotonic()<deadline:
    try:
     for e in self.driver.find_elements('css selector','#main .message-out'):
      if e.id in before:continue
      bodies=e.find_elements('css selector','span.selectable-text.copyable-text')
      if not any(b.text==draft['text'] for b in bodies):continue
      if e.find_elements('css selector','[data-icon="msg-check"], [data-icon="msg-dblcheck"], [data-icon="msg-dblcheck-ack"]'):
       return {'state':'sent','message':'WhatsApp shows the message as sent to '+draft['recipient']+'.'}
    except Exception:break
    time.sleep(.25)
   return {'state':'uncertain','message':'I clicked Send, but could not verify WhatsApp’s sent indicator. Check the chat before retrying.'}
 def close(self):
  with self.mutex:
   if self.driver:
    try:self.driver.quit()
    except Exception:pass
   self.driver=None;self.staged=None
