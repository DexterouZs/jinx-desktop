"""Grounded personal preferences and explicit remembering, without model inference."""
import re
import request_intents
import long_memory

TOPICS={'music':'music','music genre':'music','genre':'music','artist':'artist',
        'food':'food','drink':'drink','colour':'colour','color':'colour','game':'game'}

def preference(text):
 t=text.strip().rstrip('.!')
 m=re.fullmatch(r'my favou?rite (music genre|music|genre|artist|food|drink|colou?r|game) is (.{1,160})',t,re.I)
 if m and not re.search(r'[?\n]|\b(?:and then|please|password|api key|access token)\b',m[2],re.I):
  topic=TOPICS[m[1].lower()];value=m[2].strip()
  return 'favourite_'+topic,f"David's favourite {topic} is {value}."
 m=re.fullmatch(r'I prefer (short|brief|concise|detailed|long) (?:answers|replies|responses)',t,re.I)
 if m:return 'reply_length','David prefers '+m[1].lower()+' answers.'
 return None

def requested(text,memory,automatic=True):
 t=request_intents.command_text(text,keep_punctuation=True)
 explicit=re.fullmatch(r'(?:remember that|remember this[:,]?|learn that|merke dir(?: bitte)?(?:,? dass)?)\s+(.+)',t,re.I|re.S)
 if explicit:
  value=explicit[1].strip()
  if long_memory.sensitive(value):return {'reply':'I do not store passwords, authentication keys or phone numbers in my personal memory.','_tools':[]}
  if len(value)>1000:return {'reply':'Please give me one short fact to remember.','_tools':[]}
  if value.endswith('?'):return {'reply':'Tell me the fact you want me to remember.','_tools':[]}
  item=preference(value)
  if item:identifier=memory.profile(item[0],item[1])
  else:identifier=memory.add('fact',value,source='explicit user request',semantic=False)
  return {'reply':'Remembered: '+(item[1] if item else value),'_tools':['jinx_memory_save'],'memory_saved':identifier}
 item=preference(t) if automatic else None
 if item and not long_memory.sensitive(t):
  identifier=memory.profile(item[0],item[1])
  return {'reply':"I'll remember that. "+item[1],'_tools':['jinx_memory_save'],'memory_saved':identifier}
 m=re.fullmatch(r'(?:what is|what\'s|tell me) my favou?rite (music genre|music|genre|artist|food|drink|colou?r|game)[.!?]*',t,re.I)
 if m:
  topic=TOPICS[m[1].lower()];row=memory.profile_fact('favourite_'+topic)
  return {'reply':row['text'].replace("David's ",'Your ',1) if row else 'I have not saved your favourite '+topic+' yet. Tell me and I can remember it.','_tools':['jinx_memory']}
 if re.fullmatch(r'(?:what do you (?:know|remember) about me|show (?:me )?my saved memories)[.!?]*',t,re.I):
  facts=[row['text'] for row in memory.listing()['memories'] if row['kind']=='fact'][:12]
  return {'reply':'Here is what I have saved about you:\n'+'\n'.join(facts) if facts else 'I have no personal facts saved yet.','_tools':['jinx_memory']}
 return None
