"""Latency routing: which model answers, and which voice speaks.

Measured on this machine (Radeon 8060S, Vulkan, 9 September 2026), with the
1,939-token persona as the system prompt:

  qwen3.8:27b-jinx   prefill 209 tok/s   gen 18.7 tok/s
                     time to first token 9.0s cold prefix, 3.5s warm
  qwen3.5:4b         prefill 800 tok/s   gen 44.1 tok/s
                     time to first token ~2.4s cold prefix, well under 1s warm

These historical full-persona timings are workload dependent. The fast model
handles everyday conversation; the 27B is reserved for work whose quality is
worth the wait and for this application's existing vision/tool pipeline.
"""

import re
import personality
import news_briefing

FAST='qwen3.5:4b'
DEEP='qwen3.8:27b-jinx'
AI_MODES=('auto','online','local_fast','local_deep')
def validate_mode(mode):
 if not isinstance(mode,str) or mode not in AI_MODES:raise ValueError('Unknown AI model choice')
 return mode

def model_choices(online_model):
 return [
  {'id':'auto','label':'Automatic · recommended','description':'Use the configured online model, with local fallback when unavailable.'},
  {'id':'online','label':online_model+' · online','description':'Use only the configured online model. An unavailable connection produces an error instead of switching locally.'},
  {'id':'local_fast','label':'Adaptive local · everyday + Qwen 27B','description':'Fast everyday replies. Qwen 3.8 27B handles harder tasks, uncertainty, or “think carefully”.'},
  {'id':'local_deep','label':DEEP+' · local capable','description':'Always use the larger local model. More capable, but slower and uses more power.'},
 ]

def selected_local(mode,text,**context):
 validate_mode(mode)
 if mode=='local_deep':return DEEP,'selected by user'
 return model_for(text,**context)


# The existing vision/tool pipeline uses the 27B, rather than the plain 4B chat path.
# Phrases the desktop menu and David actually use for a screen capture.
VISION_TOOLS=('screen','look at my','read this page','read the page','ocr','what do you see')

# Work whose quality is worth several seconds.
DEEP_WORDS=(
 'calendar','appointment','appointments','remind','reminder','reminders','schedule','meeting',
 'open','launch','play','start the game','start a game','browse','internet',
 "you didn't","you did not",'you cant','you cannot',"you can't",'try again','öffne','starte','suche','installiere','prüfe','schreibe','übersetze','recherchiere',
 # Terminal work needs the tool-capable agent, including social-prefixed requests.
 'terminal','command','run','execute','check whether',
 "why isn't",'why is not','not working','fix','restart','kill','process',
 'service','log','install','update','disk','cpu','gpu','memory usage',
 'network','wifi','ping','port','file','folder','directory',
 "why doesn't","doesn't work",'does not work','running','processes','services',
 'files','folders','directories','logs','updates','installed','scripts','commands',
 'write','draft','rewrite','compose','essay','summarise','summarize','translate',
 'explain why','explain how','in detail','step by step','analyse','analyze',
 'compare','plan','review','debug','code','script','function','error log',
 'diagnose','troubleshoot','research','investigate','why is','why does',
 # Anything needing live information has to reach the web tools, which only
 # the agent tier can call. The 4B would otherwise answer from stale weights.
 'search','look up','google','find out','latest','news','weather','forecast',
 'who won','price of','how much does','right now online','on the web',
 # Device questions that were not handled directly need live HA state tools.
 'home assistant','smart home','humidifier','purifier','curtain','washer','c2 tv','c4 tv',
)
# Short transactional turns that must feel instant.
FAST_WORDS=(
 'hello','hi ','hey','thanks','thank you','good morning','good night',
 'what time','what is the time','how are you','are you there','never mind',
 'stop','cancel','yes','no','okay','ok',
)


def model_for(text,*,vision=False,history_turns=0,shared_document=False):
 """Pick the model for one user turn.

 Returns (model, reason). Reason is for status/telemetry, not for the user."""
 if vision:return DEEP,'vision needs the projector'
 t=' '.join(str(text or '').lower().split())
 if not t:return FAST,'empty'
 if news_briefing.requested(t):return DEEP,'current news sources'
 if deliberate(t):return DEEP,'careful thinking requested'
 if large_model_requested(t):return DEEP,'larger model requested'
 if shared_document and references_shared(t):return DEEP,'shared document work'
 if any(w in t for w in VISION_TOOLS):return DEEP,'screen request'
 # A basic definition needs no device inspection or heavyweight tool session.
 if re.match(r"^(?:what (?:is|are)|what's|define|was (?:ist|sind)) (?:a |an |the difference between |ein |eine |der unterschied zwischen )",t) and len(t)<160 and not re.search(r'\b(?:my|mine|current|latest|today|mein|meine)\b',t):
  return FAST,'short general explanation'
 if any(re.search(r'\b'+re.escape(w)+r'\b',t) for w in DEEP_WORDS):return DEEP,'reasoning or authoring'
 if any(t.startswith(w) or t==w.strip() for w in FAST_WORDS):return FAST,'social'
 # Long questions carry more context than the small model reliably tracks.
 if len(t)>220:return DEEP,'long request'
 return FAST,'everyday'

def deliberate(text):
 """An explicit request to reason longer, independent of model selection."""
 t=' '.join(str(text or '').lower().split())
 if re.search(r"\b(?:don't|do not|no need to) (?:overthink|think (?:hard|carefully|deeply))",t):return False
 return bool(re.search(r'\b(?:think (?:harder|hard|carefully|deeply|it through)|reason (?:it |this )?through|take your time|deep thinking|denk (?:gründlich|genau|gut|nach)|denke (?:gründlich|genau))\b',t))

def large_model_requested(text):
 """Choosing 27B must not silently enable its slower thinking mode."""
 t=' '.join(str(text or '').lower().split())
 return bool(re.search(r'\buse (?:the )?(?:big|large|27b|qwen 3[.]8(?: 27b)?|qwen 27b)(?: (?:model|brain))?\b',t))

def references_shared(text):
 return bool(re.search(r'\b(?:this|that|it|document|article|page|text|passage|continue|summari[sz]e|translate|das|dies|dokument|artikel|weiter)\b',str(text),re.I))

def needs_thinking(text,escalated=False):
 return deliberate(text) or escalated or bool(re.search(r'\b(?:diagnose|troubleshoot|debug|investigate|compare|analyse|analyze|explain why|plan|beweise|analysiere)\b',str(text),re.I))


# ---------------------------------------------------------------------------
# Voice routing.
#
# F5 produces David's cloned Jinx voice but is diffusion based and slow; Piper
# is an ONNX vocoder that starts in tens of milliseconds. Short confirmations
# are the ones where latency is felt, and the ones where a different timbre is
# least noticeable, so they go to Piper and everything conversational keeps the
# cloned voice.

CLONED='jinx_local'
QUICK='piper_alba'

# Phrasings that are pure acknowledgement — never worth a slow synthesis.
QUICK_STARTS=(
 'timer set','alarm set','reminder set','done','stopped','cancelled','canceled',
 'playing','paused','muted','unmuted','volume','brightness','opening','opened',
)


def voice_for(text,*,max_quick_chars=20,default=CLONED):
 """Pick the voice for one reply. Returns (voice, reason).

 Kept deliberately narrow. Jinx is told to answer everyday questions in one or
 two sentences, so a generous threshold here would route most of her ordinary
 conversation to Piper and quietly retire the cloned voice. Only genuine
 acknowledgements qualify."""
 t=' '.join(str(text or '').split())
 if not t:return default,'empty'
 if t.lower().startswith(QUICK_STARTS):return QUICK,'acknowledgement'
 if is_device_reply(t):return QUICK,'device confirmation'
 # A fragment too short to be a sentence at all ("Done.", "Stopped."). Length
 # alone is a weak signal — "It has been on since about four." is 32 characters
 # of ordinary conversation — so this stays small and the patterns do the work.
 if len(t)<=max_quick_chars and t.count('.')<=1 and not any(c in t for c in ',;:?—'):
  return QUICK,'short confirmation'
 return default,'conversational'


def is_device_reply(text):
 """Home Assistant confirmations ("Kitchen lamp on") should sound immediate."""
 t=' '.join(str(text or '').split()).lower()
 return t.endswith((' on',' off')) or '% ' in t or t.endswith('%')


# ---------------------------------------------------------------------------
# Fast-path persona.
#
# The full persona is ~1,340 tokens and describes every tool the agent can
# reach. At 800 tok/s on the 4B that is ~1.7s of prefill before a single word
# comes back — which, once the model is warm, is the entire remaining delay on
# an everyday turn. The fast model never runs those tools, so it does not need
# their instructions; it only needs to sound like Jinx and know when to hand
# over. Keep this short: every token here is latency on every quick reply.

FAST_PERSONA=(
 "You are Jinx, David's local assistant on his ASUS ROG Flow Z13 running CachyOS. "
 "Understand German and English; always reply in British English. Be mischievous and lightly teasing. Call him David. "
 "Answer everyday questions in one or two short sentences. "
 "Only claim memories supported by the supplied saved facts. Do not invent feelings or completed actions. "
 "Your host CAN open apps/games and search the web using tools. You only handle chat: "
 "pass actions to the host with HANDOFF, never say you cannot do them. "
 "Do not print filler noises or stage directions. "
 "If you are uncertain or the request needs real work — writing, diagnosing, reading his screen, "
 "searching the web, installing software, or controlling a device — reply with "
 "exactly HANDOFF and nothing else."
)

FAST_PERSONA += ' '+personality.instructions()

HANDOFF='HANDOFF'


def needs_handoff(reply):
 """The fast model saying HANDOFF means escalate to the 27B and re-answer."""
 return ' '.join(str(reply or '').split()).strip('.').upper()==HANDOFF

def handoff_prefix(reply):
 t=' '.join(str(reply or '').split()).upper().rstrip('.!?')
 return not t or HANDOFF.startswith(t) or t==HANDOFF


def persona_for(model,full_persona):
 return FAST_PERSONA if model==FAST else full_persona


# ---------------------------------------------------------------------------
# Escalation and residency.

# Keep models warm briefly between turns, then release idle GPU/UMA residency.
# Expiry is managed by Ollama after work completes; never kill an active turn.
KEEP_ALIVE_FAST='60s'
KEEP_ALIVE_DEEP='60s'

# A tiered turn escalates at most once. Fast, then deep, then stop — there is
# no path back to the fast model within a turn, so no loop is possible.
MAX_ESCALATIONS=1

# A tier-1 answer is one or two sentences. Hitting this cap means the small
# model took on something too big, which is itself a reason to escalate.
FAST_MAX_TOKENS=220
# Generous enough for a cold 4B load (3.3s measured), short enough that a
# wedged request escalates rather than hanging the turn.
FAST_TIMEOUT=25

# Above this the reply is a real answer, not a control token, even if the word
# HANDOFF appears somewhere inside it.
HANDOFF_MAX_CHARS=40


def handoff_reason(reply,*,done_reason=None,error=None):
 """Why this fast reply should be redone on the 27B, or '' to keep it.

 Deliberately generous: escalating costs seconds, but keeping a bad fast reply
 costs correctness. Anything unclear escalates."""
 if error:return 'fast model failed: '+str(error)[:80]
 if done_reason=='length':return 'fast reply hit the token cap'
 text=' '.join(str(reply or '').split()).replace('’',"'")
 if not text:return 'fast model returned nothing'
 if re.search(r"\b(?:can't|cannot|unable to|don't have|do not have|no access|i(?:'ll| will| am going to))\b.{0,110}\b(?:launch|open|start|browse|search|internet|web|tools?|games?|set|reminders?|calendar|appointments?)\b",text,re.I):
  return 'fast model made an unsupported capability/action claim'
 if needs_handoff(text) or re.search(r'(?:^|[.!?]\s*)HANDOFF[.!?]?$',text):return 'fast model asked to hand off'
 # A short reply that merely contains the token is still a hand-off; a long one
 # that mentions it is an ordinary answer.
 if len(text)<=HANDOFF_MAX_CHARS and HANDOFF in text.upper():
  return 'fast model asked to hand off'
 return ''
