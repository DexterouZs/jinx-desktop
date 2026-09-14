"""Bounded read-only decoding of Steam's existing binary shortcut catalogue.

Never executes or exposes shortcut command lines; Steam owns their launch setup.
"""
import struct
from pathlib import Path

def decode(raw):
 if len(raw)>2_000_000:raise ValueError('Shortcut catalogue too large')
 pos=0;items=0
 def string():
  nonlocal pos
  end=raw.index(b'\0',pos)
  if end-pos>8192:raise ValueError('Shortcut field too long')
  value=raw[pos:end].decode('utf-8',errors='replace');pos=end+1
  return value
 def obj(depth=0):
  nonlocal pos,items
  if depth>8:raise ValueError('Shortcut nesting too deep')
  result={}
  while pos<len(raw):
   kind=raw[pos];pos+=1
   if kind==8:return result
   items+=1
   if items>10000:raise ValueError('Too many shortcut fields')
   key=string()
   if kind==0:value=obj(depth+1)
   elif kind==1:value=string()
   elif kind==2:value=struct.unpack_from('<I',raw,pos)[0];pos+=4
   else:raise ValueError('Unsupported shortcut field type')
   result[key]=value
  raise ValueError('Incomplete shortcut catalogue')
 return obj()

def games(root=None):
 root=root or Path.home()/'.local/share/Steam/userdata'
 found={}
 for path in root.glob('*/config/shortcuts.vdf'):
  try:
   if path.stat().st_size>2_000_000:continue
   entries=decode(path.read_bytes()).get('shortcuts',{})
   for entry in entries.values():
    appid=entry.get('appid');name=entry.get('AppName',entry.get('appname',''))
    if type(appid) is not int or not 0x80000000<=appid<=0xffffffff:continue
    if not isinstance(name,str) or not name.strip() or len(name)>160:continue
    if entry.get('IsHidden'):continue
    # Use the stored ID, not an invented/hash-derived ID; Steam preserves setup.
    gameid=str((appid<<32)|0x02000000)
    found[gameid]={'appid':gameid,'name':name.strip(),'aliases':[],'shortcut':True}
  except (OSError,ValueError,KeyError,AttributeError,struct.error):continue
 return found
