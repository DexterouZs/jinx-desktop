"""Small, explicit KDE desktop actions; no arbitrary paths, commands or root."""
import math,re,time,secrets,subprocess
from pathlib import Path
import system_tools as system

DBUS=['qdbus6','org.kde.Solid.PowerManagement','/org/kde/Solid/PowerManagement/Actions/BrightnessControl']
INTERFACE='org.kde.Solid.PowerManagement.Actions.BrightnessControl.'
FOLDERS={'nas':'NAS','home':None,'downloads':'DOWNLOAD','documents':'DOCUMENTS','pictures':'PICTURES','music':'MUSIC','videos':'VIDEOS','desktop':'DESKTOP'}

def command(argv):
 result=system.run(argv)
 if not result['ok']:raise ValueError(result.get('output') or 'Desktop command failed.')
 return result['output'].strip()

def audio():
 text=command(['wpctl','get-volume','@DEFAULT_AUDIO_SINK@'])
 match=re.search(r'Volume:\s*([0-9.]+)',text)
 if not match:raise ValueError('Could not read the current speaker volume.')
 return {'volume':round(float(match.group(1))*100),'muted':'MUTED' in text}

def brightness():
 current=int(command(DBUS+[INTERFACE+'brightness']))
 maximum=int(command(DBUS+[INTERFACE+'brightnessMax']))
 if maximum<=0:raise ValueError('No controllable display brightness is available.')
 return {'brightness':round(current/maximum*100),'raw':current,'maximum':maximum}

def intent(text):
 text=re.sub(r'^(?:(?:hey )?jinx[, ]+)?(?:(?:please|can you|could you|would you)\s+)*','',str(text).lower().strip()).rstrip('.!?')
 text=re.sub(r'\s+(?:for me|please)$','',text)
 text=re.sub(r'\b(?:nass?(?: storage| drive)?)\b','nas',text)
 match=re.fullmatch(r'(?:open|show)(?: me)? (?:my |the )?('+ '|'.join(FOLDERS)+r')(?: folder)?',text)
 if match:return {'action':'open_folder','folder':match.group(1)}
 match=re.fullmatch(r'(?:set|change|turn)(?: my| the)? (?:screen )?(volume|brightness)(?: (?:to|at))? (\d{1,3})(?:\s*(?:%|percent|per cent))?',text)
 if match:return {'action':'set_'+match.group(1),'percent':int(match.group(2))}
 match=re.fullmatch(r'(?:turn (?:my |the )?(volume|brightness) (up|down)|(?:make (?:the |my )?screen (brighter|dimmer)))',text)
 if match:
  control=match.group(1) or 'brightness';up=match.group(2)=='up' or match.group(3)=='brighter'
  return {'action':'adjust_'+control,'delta':10 if up else -10}
 if re.fullmatch(r'(?:mute|unmute)(?: (?:the |my )?(?:sound|speakers|audio|volume))?',text):return {'action':'mute','muted':text.startswith('mute')}
 if re.fullmatch(r'(?:what(?: is|\x27s)|check|show)(?: me)? (?:my |the |current )*(?:volume|brightness)(?: level)?',text):return {'action':'status'}
 return None

def perform(args):
 action=args.get('action')
 if action=='status':return {'audio':audio(),'display':brightness()}
 if action=='open_folder':
  folder=args.get('folder')
  if folder not in FOLDERS:raise ValueError('Choose a standard personal folder.')
  path=Path.home()/'NAS' if folder=='nas' else Path.home() if folder=='home' else Path(command(['xdg-user-dir',FOLDERS[folder]]))
  if not path.is_absolute() or not path.is_dir():raise ValueError('That folder is not available.')
  # The path comes from the user's XDG configuration, never from model text.
  unit='jinx-folder-'+secrets.token_hex(5)
  command(['systemd-run','--user','--quiet','--collect','--property=ExitType=cgroup','--unit='+unit,'/usr/bin/dolphin',str(path)])
  result={'status':'launch_requested','reply':'Opening your '+folder+' folder.'}
 elif action in ('set_volume','set_brightness','adjust_volume','adjust_brightness'):
  control='volume' if action.endswith('volume') else 'brightness'
  before=audio() if control=='volume' else brightness()
  value=args.get('percent') if action.startswith('set_') else before[control]+args.get('delta',0)
  if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):raise ValueError('Use a numerical percentage.')
  if action.startswith('adjust_'):value=max(5 if control=='brightness' else 0,min(100,value))
  if not (5 if control=='brightness' else 0)<=value<=100:raise ValueError('Use 5 to 100 percent brightness or 0 to 100 percent volume.')
  if control=='volume':command(['wpctl','set-volume','@DEFAULT_AUDIO_SINK@',str(value/100)])
  else:command(DBUS+[INTERFACE+'setBrightness',str(max(1,round(before['maximum']*value/100)))])
  after=None
  for _ in range(8):
   after=audio() if control=='volume' else brightness()
   if abs(after[control]-value)<=1:break
   time.sleep(.1)
  if abs(after[control]-value)>1:raise ValueError('The requested '+control+' did not stick; the current value is '+str(after[control])+' percent.')
  result={'status':'verified','reply':control.capitalize()+' is '+str(after[control])+' percent.'+(' Sound is still muted.' if after.get('muted') else ''),'reading':after}
 elif action=='mute':
  if type(args.get('muted')) is not bool:raise ValueError('Choose mute or unmute.')
  command(['wpctl','set-mute','@DEFAULT_AUDIO_SINK@','1' if args['muted'] else '0'])
  after=audio()
  if after['muted']!=args['muted']:raise ValueError('The audio mute setting did not stick.')
  result={'status':'verified','reply':'Sound '+('muted.' if after['muted'] else 'unmuted.'),'reading':after}
 else:raise ValueError('Choose a supported desktop action.')
 system.audit('desktop',{'action':action,'status':result['status']})
 return result

def requested(text):
 args=intent(text)
 if args is None:return None
 result=perform(args)
 if args['action']=='status':
  a=result['audio'];return {'reply':f"Volume is {a['volume']} percent{' and muted' if a['muted'] else ''}; screen brightness is {result['display']['brightness']} percent.",'_tools':['jinx_desktop']}
 return {'reply':result['reply'],'_tools':['jinx_desktop']}
