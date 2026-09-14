"""Public track discovery; verify metadata on Spotify, never use account secrets."""
import json,re,sys,subprocess,urllib.request,time
from pathlib import Path
from difflib import SequenceMatcher

def normal(text):return ' '.join(re.findall(r'\w+',text.casefold()))
def metadata(url):
 match=re.fullmatch(r'https://open\.spotify\.com/(?:intl-[a-z]+/)?track/([A-Za-z0-9]{22})(?:\?[^\s]*)?',url)
 if not match:raise ValueError('Search result is not a Spotify track')
 identifier=match[1]
 with urllib.request.urlopen('https://open.spotify.com/embed/track/'+identifier,timeout=6) as response:page=response.read(2*1024*1024).decode()
 script=re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',page,re.S)
 if not script:raise ValueError('Spotify did not provide track metadata')
 entity=json.loads(script[1])['props']['pageProps']['state']['data']['entity']
 if entity.get('type')!='track' or entity.get('uri')!='spotify:track:'+identifier:raise ValueError('Spotify track identity mismatch')
 artists=entity.get('artists',[])
 if not artists or not entity.get('name'):raise ValueError('Spotify track information is incomplete')
 return {'title':entity['name'],'artist':', '.join(a['name'] for a in artists),'uri':entity['uri'],'url':'https://open.spotify.com/track/'+identifier}

class Search:
 def __init__(self):self.cache={}
 def find(self,song,artist=''):
  song=str(song).strip();artist=str(artist).strip()
  if not song or len(song)+len(artist)>180:raise ValueError('Tell me the song title and, if possible, the artist.')
  key=(normal(song),normal(artist))
  if key in self.cache and time.monotonic()-self.cache[key][0]<3600:return dict(self.cache[key][1])
  query='site:open.spotify.com/track '+song+' '+artist
  try:
   p=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--search',query],capture_output=True,text=True,timeout=20)
   if p.returncode:raise ValueError('Public music search is unavailable right now. No API key is needed; try again shortly.')
   urls=json.loads(p.stdout)
  except (subprocess.TimeoutExpired,json.JSONDecodeError):raise ValueError('Music search timed out. Nothing was played.') from None
  candidates=[]
  for url in urls[:4]:
   try:track=metadata(url)
   except Exception:continue
   name=normal(track['title']);base=re.split(r'\s+-\s+',track['title'])[0]
   if normal(song) not in (name,normal(base)):continue
   candidates.append(track)
  # Prefer exact track title over remixes/edits unless a version was requested.
  exact=[c for c in candidates if normal(c['title'])==normal(song)]
  if exact:candidates=exact
  if artist:
   exact_artist=[c for c in candidates if normal(c['artist'])==normal(artist)]
   if exact_artist:candidates=exact_artist
   else:candidates=[c for c in candidates if SequenceMatcher(None,normal(artist),normal(c['artist'])).ratio()>=.65]
  unique={ (normal(c['title']),normal(c['artist'])):c for c in reversed(candidates)}
  if not unique:raise ValueError('I could not verify a Spotify track matching that title and artist. Could you repeat the title and artist?')
  if len(unique)>1:raise ValueError('I found more than one match: '+ '; '.join(c['title']+' by '+c['artist'] for c in list(unique.values())[:3])+'. Which artist or version did you mean?')
  track=next(iter(unique.values()));track['confirm_artist']=bool(artist and normal(track['artist'])!=normal(artist))
  self.cache[key]=(time.monotonic(),track)
  if len(self.cache)>32:self.cache.pop(next(iter(self.cache)))
  return dict(track)

if __name__=='__main__':
 from ddgs import DDGS
 if len(sys.argv)!=3 or sys.argv[1]!='--search':raise SystemExit(2)
 results=DDGS(timeout=6).text(sys.argv[2],max_results=5,backend='bing')
 print(json.dumps([r['href'] for r in results]))
