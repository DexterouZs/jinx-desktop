"""Offline English/German detection and zero-inference routine translations."""
import re
from functools import lru_cache

@lru_cache(maxsize=1)
def detector():
 from lingua import Language,LanguageDetectorBuilder
 return LanguageDetectorBuilder.from_languages(Language.ENGLISH,Language.GERMAN).with_minimum_relative_distance(.12).build()

def detect(text,fallback='en'):
 clean=re.sub(r'https?://\S+|`[^`]*`',' ',str(text))
 clean=re.sub(r'\bjinx\b',' ',clean,flags=re.I).strip(' ,.!?')
 if not clean or clean.casefold() in ('ok','okay','steam','spotify','hmm'):return fallback
 # English product titles must not outweigh a German command verb.
 if re.match(r'^(?:hallo|guten|bitte|kannst du|könntest du|erzähl|erzähle|öffne|starte|spiele|suche|zeig|zeige|wie geht|was ist|lies|danke|ja|nein)\b',clean,re.I):return 'de'
 if re.match(r'^(?:hi|hello|hey|please|can you|could you|open|start|play|search|tell me|what is|thanks|yes|no)\b',clean,re.I):return 'en'
 from lingua import Language
 result=detector().detect_language_of(clean[:1200])
 return 'de' if result==Language.GERMAN else 'en' if result==Language.ENGLISH else fallback

def reply_language(text,fallback='en',mode='auto'):
 if mode in ('de','en'):return mode
 # Explicit output-language instructions override the language of the request.
 t=str(text)
 if re.search(r'\b(?:reply|answer|respond|speak)(?: to me)? in (?:German|Deutsch)\b|\b(?:auf Deutsch antworten|antworte auf Deutsch)\b',t,re.I):return 'de'
 if re.search(r'\b(?:reply|answer|respond|speak)(?: to me)? in English\b|\b(?:auf Englisch antworten|antworte auf Englisch)\b',t,re.I):return 'en'
 return detect(t,fallback)

def instruction(lang):
 return ('Reply in German, using natural German and du. Keep app titles, URLs, code, quoted messages and identifiers unchanged.' if lang=='de' else 'Reply entirely in natural British English, even to German input. Use English greetings too: Guten Morgen means Good morning. Do not mirror the input language. Keep quoted content and identifiers unchanged.')

def localise(text,lang):
 """Only translate known host-owned templates, never message bodies or sources."""
 if lang!='de':return text
 exact={"Hi David, I'm here.":'Hallo David, ich bin da.',"I'm Jinx, your local assistant.":'Ich bin Jinx, deine lokale Assistentin.',
  'Stopped.':'Gestoppt.','Cancelled.':'Abgebrochen.','Music paused.':'Musik pausiert.',
  'Cancelled. I have not performed that action.':'Abgebrochen. Ich habe diese Aktion nicht ausgeführt.',
  'Message sending cancelled.':'Das Senden der Nachricht wurde abgebrochen.',
  'That confirmation has expired or changed. Ask me to review the pending action again. Nothing was done.':'Diese Bestätigung ist abgelaufen oder hat sich geändert. Lass mich die ausstehende Aktion noch einmal vorlesen. Es wurde nichts ausgeführt.',
  'There is no pending action.':'Es gibt keine ausstehende Aktion.',
  'I can search the web. What would you like me to look up?':'Ich kann im Internet suchen. Wonach soll ich suchen?',
  'Web access is switched off in my options. Enable Web & learning to search.':'Der Internetzugriff ist in meinen Optionen ausgeschaltet. Aktiviere Web & learning, um zu suchen.'}
 if text in exact:return exact[text]
 patterns=[(r'^Starting (.+)$','Ich starte {}.'),(r'^Opening (.+)$','Ich öffne {}.'),
  (r'^Requested (.+) to open\.$','Ich öffne {}.'),(r'^Could not start (.+)$','Ich konnte {} nicht starten.'),
  (r'^Several match: (.+)$','Mehrere passen: {}. Welchen Titel meinst du?'),
  (r'^Nothing installed called (.+)$','Ich finde keinen installierten Eintrag namens {}.'),
  (r'^Playing (.+) by (.+)\.$','Ich spiele {} von {}.'),
  (r'^Playing (.+)\.$','Ich spiele {}.'),
  (r'^Volume (.+)$','Lautstärke {}'),(r'^Brightness (.+)$','Helligkeit {}')]
 for pattern,template in patterns:
  m=re.fullmatch(pattern,text)
  if m:return template.format(*(v.rstrip('.') for v in m.groups()))
 return text

def localise_review(text,lang):
 """Translate only the fixed WhatsApp review frame; keep dictated text exact."""
 if lang!='de':return text
 m=re.fullmatch(r'To (.+?) on WhatsApp: “(.*)”\. Say yes or send to send this exact message, or cancel\.',text,re.S)
 if not m:return text
 return f'An {m[1]} auf WhatsApp: “{m[2]}”. Sage ja oder senden, um genau diese Nachricht zu senden, oder abbrechen.'

def english_greeting(text):
 """Normalize only an unquoted opening greeting, never a dictated payload."""
 for pattern,replacement in ((r'^Guten Morgen\b','Good morning'),(r'^Guten Abend\b','Good evening'),(r'^Guten Tag\b','Hello'),(r'^Gute Nacht\b','Good night'),(r'^Hallo\b','Hello')):
  text=re.sub(pattern,replacement,text,flags=re.I)
 return text
