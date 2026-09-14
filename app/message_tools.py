"""Dictated messages with an exact recipient, completed read-back and one send."""
import hashlib, json, re, secrets, threading, time
from pathlib import Path
from messaging_browser import WhatsAppBrowser
from software_installer import atomic

PLATFORM=r'(?:whats\s?app|zap\s?zap|discord)'
def requested(text):
 t=str(text).strip()
 t=re.sub(r'^(?:(?:hey )?jinx[, ]+)?(?:(?:please|can you|could you|would you)[, ]+)*','',t,flags=re.I)
 # Parse only an explicit messaging imperative. The body after the separator
 # is retained verbatim, including negative wording meant for the recipient.
 verb=r'(?:(?:write|send) (?:a )?'+PLATFORM+r' message to|(?:write|send)(?: me)? (?:a |the )?message to|write(?: to)?|tell|message|text)'
 pattern=verb+r'\s+([\w .\-]{1,60}?)(?:\s+(?:on|in|via|using)\s+('+PLATFORM+r'))?(?:\s+(?:that|saying|to say|and (?:then )?(?:say|saying|tell (?:her|him|them)))\s+|\s*:\s*)(.+)'
 m=re.fullmatch(pattern,t,re.I)
 if not m:return None
 name,platform,body=m.groups()
 if not platform:
  prefix=re.match(r'(?:write|send) (?:a )?('+PLATFORM+r') message to\b',t,re.I)
  if prefix:platform=prefix[1]
 tail=re.fullmatch(r'(.+?)\s+on\s+('+PLATFORM+r')[.!?]?',body,re.I)
 if not platform and tail:body,platform=tail.groups()
 if re.search(r'\b(?:do not|don.t|never|example|phrase|document|website)\b',name,re.I):return None
 platform=re.sub(r'\s','',platform.lower()) if platform else 'whatsapp'
 if platform=='zapzap':platform='whatsapp'
 # In a greeting request, 'say hi for me?' is politeness to the assistant.
 # Do not strip 'for me' from arbitrary dictated sentences or quoted wording.
 greeting=re.fullmatch(r'(hi|hello|hey) for me[.!?]?',body.strip(),re.I)
 if greeting:body=greeting[1]
 return {'recipient':name.strip(),'platform':platform,'text':body.strip()}

class Messages:
 def __init__(self,root):
  self.root=Path(root);self.path=self.root/'messages.json';self.contacts_path=self.root/'contacts.json'
  self.mutex=threading.RLock();self.browser=WhatsAppBrowser(self.root/'firefox-profile');self.armed=None
  try:self.draft=json.loads(self.path.read_text())
  except (OSError,ValueError):self.draft=None
  # Restart never recreates a spoken approval or repeats an uncertain send.
  if self.draft and self.draft['state']=='sending':self.draft['state']='uncertain';self.save()
 def save(self):
  atomic(self.path,self.draft)
  if self.draft:
   path=self.root/'events.jsonl'
   with path.open('a') as output:output.write(json.dumps({'at':time.time(),'id':self.draft['id'],'platform':self.draft['platform'],'state':self.draft['state']})+'\n')
   path.chmod(0o600)
 def contacts(self):
  try:return json.loads(self.contacts_path.read_text())
  except (OSError,ValueError):return []
 def save_contact(self,name,phone):
  name=str(name).strip();phone=re.sub(r'[ ()-]','',str(phone))
  if not re.fullmatch(r'[\w .\-]{1,60}',name):raise ValueError('Enter the exact contact name, up to 60 characters.')
  if not re.fullmatch(r'\+[1-9][0-9]{6,14}',phone):raise ValueError('Enter a WhatsApp number with + and the country code.')
  with self.mutex:
   rows=self.contacts();rows=[c for c in rows if c['name'].casefold()!=name.casefold()]
   rows.append({'name':name,'phone':phone});atomic(self.contacts_path,rows);self.armed=None
   if self.draft and self.draft['recipient'].casefold()==name.casefold() and self.draft['state'] in ('prepared','awaiting_confirmation'):
    self.draft.update(state='needs_contact',notice='Contact changed. Prepare and read back the message again.');self.save()
  return 'Contact saved locally.'
 def snapshot(self):
  # Status polling must not wait behind browser navigation or an external send.
  armed=self.armed;draft=dict(self.draft) if self.draft else None
  return {'confirmation':'read_back_then_yes_or_send','contacts':self.contacts(),'draft':draft,'awaiting_confirmation':bool(armed and time.time()-armed['at']<300),'browser':self.browser.status()}
 def disarm(self):
  self.armed=None
 def repeat(self,cancelled=lambda:False):
  with self.mutex:
   if not self.draft or self.draft['state'] in ('cancelled','sent','sending','uncertain','checked'):raise ValueError('There is no unsent message ready for read-back.')
   if self.draft['state'] in ('prepared','awaiting_confirmation'):
    self.armed=None;self.draft['state']='prepared';self.save()
    return {'reply':f'To {self.draft["recipient"]} on WhatsApp: “{self.draft["text"]}”. Say yes or send to send this exact message, or cancel.','readback_id':self.draft['id']}
   return self.prepare(self.draft,cancelled)
 def prepare(self,intent,cancelled=lambda:False):
  with self.mutex:
   self.armed=None
   body=str(intent['text']).strip()
   if not body or len(body)>1500 or any(ord(c)<32 or 0xe000<=ord(c)<=0xf8ff for c in body):raise ValueError('Dictate a single message of up to 1,500 characters, without line breaks or control keys.')
   recipient=str(intent['recipient']).strip();platform=intent['platform']
   if platform not in ('whatsapp','discord'):raise ValueError('Choose WhatsApp or Discord.')
   if self.draft and self.draft['state'] in ('sending','uncertain'):raise ValueError('Check the previous message in the app first. Its send result is uncertain; acknowledge that check in Messaging before preparing another.')
   self.draft={'id':secrets.token_hex(8),'recipient':recipient,'platform':platform,'text':body,'state':'draft','created_at':time.time(),'confirmation':'read_back_then_yes_or_send'};self.save()
   if platform=='discord':
    self.draft.update(state='manual_draft',notice='Discord personal-account draft. Sending through the supported API requires a bot account.');self.save()
    return {'reply':f'Discord draft for {recipient}: “{body}”. Personal-account sending is not connected. The draft is in Messaging; nothing has been sent.','readback_id':None}
   if not self.browser.status()['connected']:
    try:self.browser.connect()
    except Exception:
     self.draft.update(state='needs_connection',notice='Open Messaging → Connect WhatsApp and link your phone in ZapZap.');self.save()
     return {'reply':f'The draft for {recipient} is “{body}”. Connect WhatsApp in Messaging first. Nothing sent.','readback_id':None}
   contacts=[c for c in self.contacts() if c['name'].casefold()==recipient.casefold()]
   if not contacts:
    try:
     found=self.browser.lookup_contact(recipient)
     if found:contacts=[found]
    except ValueError as error:
     self.draft.update(state='needs_connection',notice=str(error));self.save()
     return {'reply':f'The draft for {recipient} is “{body}”. '+str(error),'readback_id':None}
   if len(contacts)!=1:
    try:suggestions=self.browser.suggest_contacts(recipient)
    except Exception:suggestions=[]
    if isinstance(suggestions,list) and len(suggestions)==1:
     candidate=suggestions[0]
     self.draft.update(state='needs_contact',suggested_recipient=candidate,notice='Confirm the suggested contact name before preparing the message.');self.save()
     return {'reply':f'I heard {recipient}, but found {candidate} in WhatsApp. Did you mean {candidate}? Say yes to choose that contact, or cancel. I will read the message back before sending.','readback_id':None}
    self.draft.update(state='needs_contact',notice='Save this recipient’s exact WhatsApp name and international phone number in Messaging, then ask me to read the message again.');self.save()
    return {'reply':f'The WhatsApp draft for {recipient} is “{body}”. Save {recipient}’s number in Messaging first so I can identify the right person. Nothing has been sent.','readback_id':None}
   contact=contacts[0];self.draft['recipient']=contact['name'];self.draft['phone']=contact['phone']
   try:self.browser.stage(self.draft,contact,cancelled)
   except Exception as error:
    self.draft.update(state='needs_connection',notice=str(error)[:350]);self.save();raise ValueError(str(error)[:350]) from None
   self.draft.update(state='prepared',notice='Waiting for the complete spoken read-back.');self.save()
   return {'reply':f'To {contact["name"]} on WhatsApp: “{body}”. Say yes or send to send this exact message, or cancel.','readback_id':self.draft['id']}
 def read_back_complete(self,identifier):
  with self.mutex:
   if self.draft and self.draft['id']==identifier and self.draft['state']=='prepared':
    self.armed={'id':identifier,'at':time.time(),'digest':self.digest(self.draft)}
    self.draft.update(state='awaiting_confirmation',notice='Read-back finished. Waiting for yes or send.');self.save()
 def digest(self,draft):return hashlib.sha256(json.dumps({k:draft.get(k) for k in ['id','recipient','platform','phone','text']},sort_keys=True).encode()).hexdigest()
 def send(self):
  with self.mutex:
   ticket=self.armed;self.armed=None
   if not ticket or not self.draft or ticket['id']!=self.draft['id'] or time.time()-ticket['at']>=300 or ticket['digest']!=self.digest(self.draft) or self.draft['state']!='awaiting_confirmation':raise ValueError('No current message has a completed read-back. Ask me to read the message again first.')
   self.draft.update(state='sending',notice='Checking the exact recipient and message before sending.');self.save()
   try:result=self.browser.send(self.draft)
   except ValueError as error:result={'state':'failed','message':str(error)}
   except Exception:result={'state':'uncertain','message':'The send result is uncertain. Check WhatsApp before trying again.'}
   self.draft.update(state=result['state'],notice=result['message']);self.save()
   return result['message']
 def cancel(self):
  with self.mutex:
   self.armed=None
   if self.draft and self.draft['state'] in ('sending','uncertain','sent'):return 'The message may already have been sent. Check its result in Messaging.'
   if self.draft:self.draft.update(state='cancelled',notice='Sending cancelled. Any text already in the app remains an unsent draft.');self.save()
   return 'Message sending cancelled.'
 def acknowledge_uncertain(self):
  with self.mutex:
   self.armed=None
   if self.draft and self.draft['state']=='uncertain':self.draft.update(state='checked',notice='User checked the uncertain result in WhatsApp.');self.save()
