"""Local email drafting. No SMTP, account login or sending operation exists."""
from pathlib import Path
from email.message import EmailMessage
from email.policy import SMTP
import datetime,re,secrets,json,urllib.request
import request_intents
import routing

DRAFTS=Path.home()/'Documents/Jinx/Email Drafts'

def compose(request,cancelled=lambda:False):
 """One small-model writing call; model output never selects a recipient or action."""
 if cancelled():raise ValueError('Draft cancelled.')
 schema={'type':'object','additionalProperties':False,'required':['subject','body'],
         'properties':{'subject':{'type':'string'},'body':{'type':'string'}}}
 prompt=('Write the email requested by David. Return JSON with subject and body only. '
         'Use concise natural English, with the requested tone, greeting and sign-off David. '
         'Preserve all stated facts, dates, times and negations. Do not add availability, flexibility, '
         'promises, reasons, contact details or other facts that were not supplied. '
         'Do not claim anything was sent or saved. A recipient name is not an email address.')
 payload={'model':routing.FAST,'stream':False,'think':False,'keep_alive':routing.KEEP_ALIVE_FAST,
          'messages':[{'role':'system','content':prompt},{'role':'user','content':request}],
          'format':schema,'options':{'num_ctx':4096,'num_predict':600,'temperature':.2}}
 req=urllib.request.Request('http://127.0.0.1:11435/api/chat',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=30) as response:result=json.load(response)
 if cancelled():raise ValueError('Draft cancelled.')
 if result.get('done_reason')=='length':raise ValueError('Email draft was incomplete.')
 fields=json.loads(result['message']['content'])
 if set(fields)!= {'subject','body'} or not all(isinstance(v,str) and v.strip() for v in fields.values()):raise ValueError('Invalid email draft.')
 return fields

def intent(text):
 t=request_intents.command_text(text,keep_punctuation=True)
 m=re.fullmatch(r'(?:write|draft|compose|prepare|schreib(?:e)?|verfasse)\s+(?:(?:me|for me)\s+)?(?:(?:a|an|the|eine)\s+)?((?:(?:polite|formal|friendly|short|professional)\s+)*)(?:e-?mail|email draft)(?:\s+(?:for me|me))?\b[\s,:]*(.*)',t,re.I)
 if not m:return None
 rest=m[2].strip();style=(m[1] or '').strip()
 to='';body='';brief=rest
 exact=re.fullmatch(r'(?:to|an)\s+(.+?)\s+(?:saying|that says|with the text|mit dem text)\s+(.+)',rest,re.I|re.S)
 if exact:
  to=exact[1].strip();body=exact[2].strip();brief=''
  if style:brief=f'Write a {style} email to {to} conveying: {body}';body=''
 else:
  recipient=re.match(r'(?:to|an)\s+(.+?)(?=\s+(?:about|asking|to ask|explaining|telling|regarding|über)\b|$)',rest,re.I)
  if recipient:to=recipient[1].strip()
 return {'to':to,'body':body,'brief':brief,'style':style}

def save(args):
 to=str(args.get('to','')).strip();subject=str(args.get('subject','')).strip();body=str(args.get('body','')).strip()
 if not body or len(body)>18000:raise ValueError('An email draft needs a body of up to 18000 characters.')
 if any(ord(c)<32 for c in to+subject) or len(to)>200 or len(subject)>180:raise ValueError('Invalid email recipient or subject.')
 # Display names are allowed; do not fabricate a mailbox for them.
 addresses=re.findall(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}',to)
 if '@' in to and (len(addresses)!=1 or addresses[0]!=to):raise ValueError('Use one complete email address or a recipient name.')
 DRAFTS.mkdir(parents=True,exist_ok=True,mode=0o700)
 stem=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(3)
 plain=f'To: {to or "[recipient]"}\nSubject: {subject or "[subject]"}\n\n{body}\n'
 path=DRAFTS/(stem+'.txt')
 with path.open('x') as f:f.write(plain)
 path.chmod(0o600)
 message=EmailMessage(policy=SMTP);message['Subject']=subject
 if addresses:message['To']=to
 message['X-Unsent']='1';message.set_content(body)
 eml=DRAFTS/(stem+'.eml')
 with eml.open('xb') as f:f.write(message.as_bytes())
 eml.chmod(0o600)
 return {'status':'draft_saved','path':str(path),'eml':str(eml),'draft':plain,'reply':'Draft saved in Documents/Jinx/Email Drafts. Nothing has been sent.\n\n'+plain}
