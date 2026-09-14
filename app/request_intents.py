"""Recognise direct user commands without interpreting quoted/source instructions."""
import re

def command_text(text,keep_punctuation=False):
 t=str(text or '').strip() if keep_punctuation else ' '.join(str(text or '').split()).strip(' .!?')
 # Chained speech politeness: "Hey Jinx, could you please ...".
 for _ in range(8):
  next_t=re.sub(r"^(?:(?:hey|hi|ok|okay)\s+jinx|jinx|please|also|can you|could you|would you|will you|i(?:'d| would) like you to|i want you to|bitte|kannst du|könntest du|mir bitte)\b[\s,.:]*",'',t,count=1,flags=re.I)
  if next_t==t:break
  t=next_t
 return t.strip()

def search_query(text):
 t=command_text(text)
 # Return None for another task; empty string means a search with no topic.
 m=re.fullmatch(r'(?:search(?: (?:the )?(?:web|internet|online))?(?: for)?|browse (?:the )?(?:web|internet)(?: for)?|look (?:online|on the web)(?: for)?|look up|google|research|suche?(?: im internet)?(?: nach)?|recherchiere)\b[\s,:]*(.*)',t,re.I)
 if not m:return None
 query=re.sub(r'\s+(?:for me|please|bitte|online)$','',m[1],flags=re.I).strip()
 # Mixed requests go to the tool agent; never silently omit another action.
 if re.search(r'\b(?:and|then|und) (?:open|launch|start|install|send|play)\b',query,re.I):return None
 return query
