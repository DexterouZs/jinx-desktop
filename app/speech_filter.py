"""A speech-only presentation filter; never alters answers or action payloads."""
import re

URL=re.compile(r'(?i)\b(?:https?://|www\.)[^\s<>"\u201d]+')
OPAQUE=re.compile(r'\b(?:[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}|[0-9a-fA-F]{32,128})\b')

def explicit_details(request):
 """Only a direct request for literal reading overrides normal presentation."""
 if re.search(r"\b(?:don't|do not|never|nicht|keine)\b",str(request),re.I):return False
 return bool(re.search(
  r'\b(?:read|say|speak|spell)(?:\s+\w+){0,5}\s+(?:verbatim|exactly|word for word|character by character)\b'
  r'|\b(?:read|say|speak|spell)(?:\s+(?:out|aloud|the|this|that|full|entire|complete|actual|my|please)){0,5}\s+(?:url|link|web address|file path|path|code|command|identifier|id|hash)\b'
  r'|\b(?:lies|lese|sag|buchstabiere)(?:\s+\w+){0,4}\s+(?:wörtlich|wort für wort|adresse|link|url|pfad|code|befehl)\b',
  str(request),re.I))

def for_speech(text,*,verbatim=False):
 original=str(text)
 if verbatim:return original
 text=original
 lines=[];sources=False
 for line in text.splitlines():
  if re.fullmatch(r'\s*(?:#{1,6}\s*)?(?:\*\*)?(?:sources|references|quellen)(?:\*\*)?\s*:?\s*',line,re.I):
   sources=True;continue
  if sources:
   if not line.strip() or re.match(r'\s*(?:[-*+]|\d+[.)])?\s*(?:!?\[.*\]|https?://|www\.)',line,re.I):continue
   sources=False
  lines.append(line)
 text='\n'.join(lines)
 # Code is visible in the written answer; speaking every token is rarely useful.
 text=re.sub(r'(?ms)^[ \t]*(`{3,}|~{3,})[^\n]*\n.*?^[ \t]*\1[ \t]*$',
             '\nThe code is shown on screen.\n',text)
 # Keep the human-readable title of an inline Markdown link, never its address.
 text=re.sub(r'!?\[([^\]\n]+)\]\(\s*(?:https?://|www\.)[^\s]*(?:\s+"[^"\n]*")?\s*\)',r'\1',text,flags=re.I)
 # Reference definitions and citation tokens are presentation, not prose.
 text=re.sub(r'(?m)^\s*\[[^\]\n]+\]:\s*(?:https?://|www\.)\S+[^\n]*$','',text)
 text=re.sub(r'(?:cite|filecite)[^]*','',text)
 text=re.sub(r'\[(?:\d{1,3}(?:\s*[,–-]\s*\d{1,3})*|\^\w+)\]','',text)
 def link(match):
  value=match[0];end=''
  while value and value[-1] in '.,;:!?':end=value[-1]+end;value=value[:-1]
  return 'the link shown on screen'+end
 text=URL.sub(link,text)
 # Opaque identifiers and filesystem paths stay available in the written answer.
 text=OPAQUE.sub('the identifier shown on screen',text)
 text=re.sub(r'(?<![\w:/])(?:~/(?:[^\s<>`]+)|/(?:home|usr|etc|var|run|tmp|opt|mnt|media|sys|dev)(?:/[^\s<>`]+)+)',
             lambda m:'the path shown on screen'+('.' if m[0].endswith('.') else ''),text)
 text=re.sub(r'`([^`\n]+)`',r'\1',text)
 text=re.sub(r'(?m)^\s{0,3}(?:#{1,6}\s+|[-*+]\s+)','',text)
 text=re.sub(r'\*\*([^*]+)\*\*',r'\1',text)
 text=re.sub(r'[ \t]+',' ',text)
 text=re.sub(r' +\n','\n',text)
 text=re.sub(r' +([.,;:!?])',r'\1',text)
 text=re.sub(r'\n\s*\n+', '\n', text).strip()
 return text or ('The details are shown on screen.' if original.strip() else '')
