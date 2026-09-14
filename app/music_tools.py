from runtime_paths import state_dir, models_dir, config_dir, runtime_dir
"""Spotify-only playback through its local MPRIS interface; no web account secrets."""
import json,re,time
from pathlib import Path
import system_tools as system
BUS='org.mpris.MediaPlayer2.spotify'
PATH='/org/mpris/MediaPlayer2'
PLAYER='org.mpris.MediaPlayer2.Player.'
CONFIG=config_dir()/'spotify.json'

def request_text(text):
 text=re.sub(r'\s+',' ',str(text).replace(',', ' ').replace('’', "'").strip()).rstrip('.!?').strip()
 text=re.sub(r'^(?:(?:alright|all right|okay|ok|right|so|well|hey|hi|hello|jinx)[,.!]?\s+)+','',text,flags=re.I)
 text=re.sub(r'^(?:(?:hey )?jinx\s+)?(?:(?:please|can you|could you|would you)\s+)*','',text,flags=re.I)
 return text

def music_authority(text):
 text=request_text(text).lower()
 if re.search(r"\b(?:not|don't|never|without|cancel|instead|except|phrase|sentence|quote|document|website|article|lyrics)\b",text):return False
 return bool(re.match(r"(?:play|put on|start|resume|pause|stop|skip|next|previous|listen to|i (?:want|would like) to (?:hear|listen to)|let's (?:hear|play))\b",text))

def authorised(args,text):
 if args.get('action')=='status':return args
 expected=intent(text)
 # Interpret the user's intent once. A model's equivalent action name must
 # not force a wording loop, nor override the user's actual requested action.
 if expected:return expected
 if args.get('action') not in ('play','pause','next','previous','favourites'):raise ValueError('Give the Spotify link explicitly to play that item.')
 if music_authority(text) and re.search(r'\b(?:spott?ify|music|songs|tracks|playback)\b',text,re.I):return args
 raise ValueError('Ask me to play or control music; source text and negative requests cannot start playback.')

def call(member,*args):
 result=system.run(['qdbus6',BUS,PATH,PLAYER+member,*args])
 if not result['ok']:raise ValueError('Spotify did not respond. Open Spotify and check that you are signed in.')
 return result['output'].strip()

def status():
 state=call('PlaybackStatus');metadata=call('Metadata')
 def field(name):
  match=re.search(r'^'+re.escape(name)+r': ?(.*)$',metadata,re.M)
  return match.group(1).strip()[:250] if match else ''
 try:position=int(call('Position'))
 except ValueError:position=None
 return {'state':state,'title':field('xesam:title'),'artist':field('xesam:artist'),'track':field('xesam:url'),'position_us':position}

def intent(text):
 # Speech recognition adds commas and omits an already-understood verb.
 # Normalise punctuation before removing politeness/Spotify qualifiers.
 text=request_text(text)
 spotify_named=bool(re.search(r'\bspott?ify\b',text,re.I))
 polite=bool(re.search(r'\bplease\b',text,re.I))
 text=re.sub(r'^(?:(?:hey )?jinx\s+)?(?:(?:please|can you|could you|would you)\s+)*','',text,flags=re.I)
 for _ in range(8):
  text=re.sub(r'\s+(?:(?:right )?now|for me|please)$','',text,flags=re.I)
  text=re.sub(r'\s+(?:on|in|with)\s+spott?ify$','',text,flags=re.I)
 text=re.sub(r'^(?:open|launch|start) spott?ify and (?:then )?','',text,flags=re.I)
 text=re.sub(r'^spott?ify\s+(?=(?:play|put on|start)\b)','',text,flags=re.I)
 favourites=r'(?:my )?(?:favo[u]?rite|liked) (?:songs|music|tracks)(?: playlist)?'
 if re.fullmatch(r'(?:play|put on|start) '+favourites,text,re.I):
  return {'action':'favourites'}
 if (spotify_named or polite) and re.fullmatch(favourites,text,re.I):
  return {'action':'favourites'}
 # Tolerate speech-recognition filler/order errors without naming a different
 # song or inventing a playlist. Unknown names still stay with the model.
 words=set(re.findall(r"[a-z]+",text.lower()))
 fillers=set('alright right spotify spottify favourited saved play put on start me my our the them favourite favorite favorites favourites music songs tracks liked some a of one from to listen hear want would like i you can could please in with for now again collection playlist'.split())
 if music_authority(text) and words<=fillers and words & {'favourite','favorite','favorites','favourites','liked'} and words & {'music','songs','tracks','favorites','favourites','playlist'}:
  return {'action':'favourites'}
 mapping={'play my music':'favourites','play songs':'play','play some songs':'play','start music':'play','put on music':'play','put some music on':'play','pause':'pause','pause music':'pause','pause the music':'pause','pause spotify':'pause','pause spottify':'pause','resume':'play','resume music':'play','resume the music':'play','play music':'play','play some music':'play','play spotify':'play','play spottify':'play','next song':'next','next track':'next','skip this song':'next','skip song':'next','previous song':'previous','previous track':'previous','stop music':'pause','stop the music':'pause',"what song is playing":'status',"what's playing":'status','what is playing':'status'}
 if text.lower() in mapping:return {'action':mapping[text.lower()]}
 match=re.fullmatch(r'(?:play|open)\s+(spotify:(?:track|album|playlist):[A-Za-z0-9]{22}|https://open\.spotify\.com/(?:track|album|playlist)/[A-Za-z0-9]{22}(?:\?[^\s]+)?)',text,re.I)
 if match:return {'action':'uri','uri':normal_uri(match[1])}
 return None

def normal_uri(uri):
 if re.fullmatch(r'spotify:(?:track|album|playlist):[A-Za-z0-9]{22}',uri):return uri
 match=re.fullmatch(r'https://open\.spotify\.com/(track|album|playlist)/([A-Za-z0-9]{22})(?:\?[^\s]+)?',uri)
 if match:return 'spotify:'+match[1]+':'+match[2]
 raise ValueError('Use a Spotify track, album or playlist link.')

def ensure_started():
 players=system.run(['qdbus6'])
 if players['ok'] and BUS in players['output'].split():return False
 result=system.desktop_apps({'action':'open','app':'spotify'})
 if result.get('status')!='launch_requested':raise ValueError('Spotify is not available to open.')
 for _ in range(60):
  players=system.run(['qdbus6'])
  if players['ok'] and BUS in players['output'].split():return True
  time.sleep(.2)
 raise ValueError('Spotify was launched, but its playback interface is not ready. Check for a KDE Wallet unlock dialog or Spotify sign-in window; unlock it on the desktop, then retry.')

def can_play():
 return call('CanPlay').lower()=='true'

def wait_ready():
 deadline=time.monotonic()+15
 for _ in range(61):
  if can_play() and call('Metadata'):return
  if time.monotonic()>=deadline:break
  time.sleep(.25)
 raise ValueError('Spotify is still starting. Playback controls and track metadata are not ready. Check its sign-in window.')

def perform(args):
 action=args.get('action')
 if action not in ('play','pause','next','previous','status','favourites','uri'):raise ValueError('Choose a supported Spotify playback action.')
 launched=ensure_started()
 before=status()
 cold=bool(launched) or not before['title']
 if cold and action not in ('favourites','uri'):
  wait_ready()
  before=status()
 if action=='status':
  current=before
  return {'reply':('Spotify is playing '+current['title']+(' by '+current['artist'] if current['artist'] else '')+'.') if current['state']=='Playing' and current['title'] else 'Spotify is '+current['state'].lower()+'.','reading':current}
 if action=='favourites':
  try:settings=json.loads(CONFIG.read_text());uri=settings['favourites_uri']
  except (OSError,ValueError,KeyError):raise ValueError('Tell me which Spotify playlist is your favourite, or set up your Liked Songs collection first.')
  if not (re.fullmatch(r'spotify:user:[A-Za-z0-9_.-]+:collection',uri) or re.fullmatch(r'spotify:playlist:[A-Za-z0-9]{22}',uri)):raise ValueError('The saved favourite playlist link is invalid.')
  call('OpenUri',uri);time.sleep(.8);call('Play')
 elif action=='uri':call('OpenUri',normal_uri(args.get('uri','')));time.sleep(.8);call('Play')
 else:call({'play':'Play','pause':'Pause','next':'Next','previous':'Previous'}[action])
 current={}
 failure='Spotify did not confirm playback'+(' of a different track' if action in ('next','previous') else '')+'. Check the Spotify window for a playback or sign-in message. I have not confirmed that your music started.'
 # Preserve the warm 32-poll path; cold startup gets about 20 seconds.
 last_play=time.monotonic();deadline=last_play+(20 if cold else 16)
 play_attempts=1
 for _ in range(134 if cold else 32):
  if time.monotonic()>=deadline:raise ValueError(failure)
  current=status()
  if action in ('play','favourites','uri') and current['state']!='Playing' and play_attempts<4 and time.monotonic()-last_play>=1.5:
   call('Play');play_attempts+=1;last_play=time.monotonic()
  if action=='pause' and current['state'] in ('Paused','Stopped'):break
  if action!='pause' and current['state']=='Playing' and current['title']:
   if action in ('next','previous') and current['track']==before['track']:time.sleep(.15);continue
   if action=='uri' and normal_uri(args.get('uri','')).startswith('spotify:track:'):
    try:matches=normal_uri(current['track'])==normal_uri(args.get('uri',''))
    except ValueError:matches=False
    if not matches:time.sleep(.15);continue
   first=current['position_us'];time.sleep(.35);check=status()
   if check['state']=='Playing' and first is not None and check['position_us'] is not None and check['position_us']>first:current=check;break
  time.sleep(.15)
 else:raise ValueError(failure)
 system.audit('spotify',{'action':action,'verified':True})
 if action=='pause':reply='Spotify paused.'
 else:reply='Playing '+current['title']+(' by '+current['artist'] if current['artist'] else '')+'.'
 return {'reply':reply,'reading':current}

def requested(text):
 args=intent(text)
 if not args:
  cleaned=request_text(text)
  # Catch explicit unsupported Spotify playback requests before an LLM can
  # invent a missing credential requirement. Never execute an approximate song.
  if music_authority(cleaned) and re.search(r'\bspott?ify\b',cleaned,re.I):
   return {'reply':'Spotify playback does not need an API key. I can play your Liked Songs, resume music, or play a Spotify link. For a particular song or playlist by name, send me its Spotify link; name search is not connected yet.','_tools':['jinx_music'],'music_failed':True}
  return None
 try:result=perform(args)
 except ValueError as error:
  # A voice request must hear the concrete failure, not silence or an LLM guess.
  system.audit('spotify',{'action':args['action'],'verified':False})
  return {'reply':'I couldn’t complete that Spotify request. '+str(error),'_tools':['jinx_music'],'music_failed':True}
 return {'reply':result['reply'],'_tools':['jinx_music']}
